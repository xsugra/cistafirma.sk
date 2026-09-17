#!/usr/bin/env bash
# Aggregate operational gate: one verdict over every control this repository
# relies on.
#
# Read-only by contract -- it starts no container, writes nothing to the
# database, and never modifies the backup, drill or replica directories. That is
# what makes it safe to run from the weekly job, by hand, and from CI alike.
#
# It fails only on an *unmet control*, never on a merely noteworthy state. The
# distinction is deliberate: the off-site volume is documented as normally
# disconnected, so a gate that reddens every week for a documented posture is a
# gate everyone learns to ignore -- and an ignored gate protects nothing.
#
# Off-site truth is not re-implemented here: scripts/local/offsite_status.sh owns
# it and is chained below, so there is one place that decides what "off-site is
# fine" means.
set -Eeuo pipefail

# Machine-local backup configuration; an already exported variable wins.
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"
# shellcheck source=lib/backup_time.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_time.sh"
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)

RUN_GAP_MAX_DAYS="${CISTAFIRMA_RUN_GAP_MAX_DAYS:-8}"
# Left empty when unset on purpose: the resolver below has to tell "the operator
# set this" from "nobody set this", so that a general override keeps applying to
# every queue -- including the one with a default of its own.
QUEUE_WARN_DEPTH="${CISTAFIRMA_QUEUE_WARN_DEPTH:-}"
QUEUE_WARN_DEPTH_INSURANCE="${CISTAFIRMA_QUEUE_WARN_DEPTH_INSURANCE:-}"
QUEUES="${CISTAFIRMA_QUEUES:-celery ruz_full orsr financials insurance}"
SOURCE_WINDOW_HOURS="${CISTAFIRMA_SOURCE_WINDOW_HOURS:-24}"
SOURCE_MIN_ATTEMPTS="${CISTAFIRMA_SOURCE_MIN_ATTEMPTS:-200}"
SOURCE_MIN_SUCCESSES="${CISTAFIRMA_SOURCE_MIN_SUCCESSES:-20}"
# How long one outside-in API request may take before it counts as unmet. Ten
# times the 0.26 s the endpoint needs on production, so a slow-but-working API
# does not redden the gate; raise it on a host whose database is slower.
API_TIMEOUT="${CISTAFIRMA_API_TIMEOUT:-10}"

LABEL="sk.cistafirma.backup"
OUT_LOG="$(log_dir)/backup.out.log"

failures=0
warnings=0

ok() { printf 'OK    %s\n' "$*"; }
warn() {
    printf 'WARN  %s\n' "$*"
    warnings=$((warnings + 1))
}
bad() {
    printf 'FAIL  %s\n' "$*"
    failures=$((failures + 1))
}
section() { printf '\n== %s\n' "$*"; }

# The depth a queue may reach before the load is worth reporting. Two defaults,
# because the queues are not the same shape.
#
# `celery`, `ruz_full`, `orsr` and `financials` drain to zero: they sit at 0 in
# steady state, so a large depth means work arriving faster than it is consumed.
#
# `insurance` is the exception and it is designed to be. Its dispatcher is capped
# at `INSURANCE_BATCH_PER_TICK` -- 20/min x 60 x 12 h = 14400 per tick, exactly
# what a 20/m rate-limited worker drains over the same 12 h -- so arrivals equal
# drain capacity: the depth is *conserved*, neither growing nor clearing, and it
# sawtooths by one batch around whatever it inherited (measured 2026-09-13:
# ~54 000 before a dispatch, ~68 000 just after, mean ~61 000). The single
# 50000 default therefore warned permanently about a queue behaving exactly as
# designed, and a control that is always red is one nobody reads.
#
# So the insurance bound sits where a backlog stops being a backlog: ten ticks,
# i.e. five days of drain capacity. That is about twice the inherited sawtooth's
# peak -- and, read the other way, what a drain outage of roughly three days
# produces, since the dispatcher keeps adding 14 400 every tick while nothing
# drains. It is also ~58x below the 2026-09 flood (8.4 M messages enqueued in a
# day, against 14 400 drained). So it fires on a flood or on a drain stalled for
# days, and on nothing else. It cannot tell those two apart, and it does not try
# to: whether the drained work still *achieves* anything is Source health's
# verdict, and depth has never been able to answer it.
#
# Precedence: an explicit per-queue override, then an explicit general override
# (which has always meant "every queue", and still does), then the built-in
# default for that queue. An unset override is the empty string, never a value.
queue_warn_depth() {
    if [ "$1" = "insurance" ] && [ -n "$QUEUE_WARN_DEPTH_INSURANCE" ]; then
        printf '%s' "$QUEUE_WARN_DEPTH_INSURANCE"
    elif [ -n "$QUEUE_WARN_DEPTH" ]; then
        printf '%s' "$QUEUE_WARN_DEPTH"
    elif [ "$1" = "insurance" ]; then
        printf '%s' 144000
    else
        printf '%s' 50000
    fi
}

printf 'CistaFirma operational check\n'
printf '  host: %s   %s\n' "$(hostname -s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- stack ---------------------------------------------------------------
section "Stack"

stack=$(docker compose ps --format '{{.Service}}|{{.State}}|{{.Health}}' 2>/dev/null || true)
# The service names compose reports as running, for the sections below that have
# to know whether one particular service is up. Derived from the same call
# rather than asked again, so a service cannot come out running for one section
# and not for another.
running_services=$(printf '%s\n' "$stack" | awk -F'|' '$2 == "running" { print $1 }')
if [ -z "$stack" ]; then
    bad "no compose services are running (start the stack with: make docker-up)"
else
    running=0
    while IFS='|' read -r service state health; do
        [ -n "$service" ] || continue
        if [ "$state" != "running" ]; then
            bad "service '$service' is $state"
        elif [ -n "$health" ] && [ "$health" != "healthy" ]; then
            bad "service '$service' is running but $health"
        else
            running=$((running + 1))
        fi
    done <<EOF
$stack
EOF
    if [ "$running" -gt 0 ]; then
        ok "$running compose service(s) running and healthy"
    fi
fi

if docker compose exec -T db pg_isready -q >/dev/null 2>&1; then
    ok "database is accepting connections"
else
    bad "database is not accepting connections"
fi

# --- API availability ----------------------------------------------------
# Every other section judges a *component*. This one judges the thing the
# components exist for: a real API request, from outside, answered the way a
# browser asks for it.
#
# The 2026-09-17 outage is why it is here. nginx had resolved the backend's
# address once, at its own start; the backend container was recreated 22 seconds
# later and its old address went to celery_beat, which listens on nothing -- so
# every /api/ call answered 502 for 3 h 43 min. Nothing noticed. The frontend
# container was up the whole time, its healthcheck passed, and `/healthz` on the
# very port probed below answered 200 throughout, because that endpoint is a
# LIVENESS probe and is blind to the backend by design. A gate that only ever
# asks "is the process running?" cannot see an answer that stopped being right.
#
# So this asks the real question against the real published port. `/api/stats/landing/`
# is chosen for being `AllowAny`, cheap (three COUNTs; measured 0.26 s on
# production) and downstream of everything: nginx, gunicorn, Django, Postgres.
#
# It is also the only check here that a *restart of the stack itself* does not
# invalidate -- it needs no shell inside any container, so it still answers when
# `docker compose exec` cannot.

# The address the frontend is published on, as "host:port", or the empty string
# when compose does not report one.
#
# Taken from compose rather than from `.env`: `FRONTEND_PORT` and `BIND_HOST`
# live in a file this script deliberately does not read, and the two compose
# variants publish different *container* ports -- 5173 for the Vite dev server,
# 80 for the production nginx -- so the container-side number is not a constant
# either. `{{.Ports}}` is the one place that already carries both halves.
frontend_published_address() {
    local mapping host
    mapping=$(docker compose ps --format '{{.Ports}}' frontend 2>/dev/null || true)
    # "127.0.0.1:5173->80/tcp, [::1]:5173->80/tcp": the first mapping is the
    # IPv4 one, and the right-hand side is the container's own port, which is
    # the half that differs between the two variants.
    mapping=${mapping%%,*}
    # A mapping without "->" is a container port that was never published --
    # compose lists those the same way (`8000/tcp`, as every worker does above).
    # There is no host address to probe in that case, and reporting one is this
    # function's whole job, so it reports none rather than inventing a URL from
    # it.
    case "$mapping" in
        *"->"*) host=${mapping%%->*} ;;
        *) host= ;;
    esac
    # A wildcard bind answers on loopback too (`BIND_HOST=0.0.0.0` is documented
    # as deliberate). Normalising it keeps curl from being handed an address
    # form it will not accept.
    case "$host" in
        0.0.0.0:* | "[::]:"*) host="127.0.0.1:${host##*:}" ;;
    esac
    printf '%s' "$host"
}

section "API availability"

if [ -z "$stack" ]; then
    # Deliberately not a failure. A host with no stack is documented here as
    # having nothing to serve -- the retired Mac keeps its volume and runs
    # nothing -- and the Stack section above has already said so. What the skip
    # must not be is silent: a check that quietly does nothing when it cannot run
    # is indistinguishable from one that ran and passed, which is the failure
    # mode this whole script exists to avoid.
    printf 'SKIP  %s\n' "no stack on this host, so there is no published port to probe"
elif ! printf '%s\n' "$running_services" | grep -qx frontend; then
    # Fail closed, like the source and sync sections do when the backend is
    # missing: the frontend is what publishes /api/ on this host, so without it
    # there is no entry point at all -- and a stack deliberately brought up
    # without it is a state that should be looked at, not one that passes.
    bad "the frontend is not running, so nothing serves /api/ from outside"
elif ! command -v curl >/dev/null 2>&1; then
    # Fail closed rather than skip: an unprobeable API is not a working one, and
    # a silent skip here would read as a pass.
    bad "curl is not installed, so /api/ cannot be probed from outside"
else
    api_host=$(frontend_published_address)
    if [ -z "$api_host" ]; then
        bad "compose reports no published port for frontend, so /api/ cannot be probed"
    else
        api_url="http://$api_host/api/stats/landing/"
        set +e
        api_status=$(curl -s -o /dev/null -w '%{http_code}' \
            --max-time "$API_TIMEOUT" "$api_url" 2>/dev/null)
        api_rc=$?
        set -e
        case "$api_status" in
            200)
                ok "GET $api_url answered 200 through the published frontend port"
                ;;
            502 | 504)
                # Named separately because the status alone does not say why it
                # matters: nginx answering for an upstream it cannot reach is
                # exactly what the 3 h 43 min outage looked like, and it is the
                # one failure here that a running, healthy frontend does not
                # rule out.
                bad "GET $api_url answered $api_status -- the frontend is up but cannot reach the backend, which is the 2026-09-17 outage exactly"
                ;;
            *)
                # curl's own exit code is the useful half when it never got an
                # answer (7 = refused, 28 = timed out); when it did get one, the
                # status is, and printing "curl exit 0" next to a 404 would only
                # invite the reader to look for meaning in it.
                if [ "$api_rc" -eq 0 ]; then
                    bad "GET $api_url answered $api_status, not 200"
                else
                    bad "GET $api_url did not complete (curl exit $api_rc), so nothing answered"
                fi
                ;;
        esac
    fi
fi

# --- celery queues -------------------------------------------------------
# Depths are reported, not judged, except past a deliberately generous
# threshold: a large backlog can be the intended steady state of a rate-limited
# rolling refresh, but it should never be invisible. Nothing else in the stack
# exposes queue depth at all, so a stalled or drowning queue is otherwise only
# detectable by its absence of output.
section "Celery queues"

total=0
for queue in $QUEUES; do
    depth=$(docker compose exec -T redis redis-cli LLEN "$queue" 2>/dev/null | tr -d '\r' || true)
    case "$depth" in
        '' | *[!0-9]*)
            bad "could not read the depth of queue '$queue'"
            continue
            ;;
    esac
    total=$((total + depth))
    bound=$(queue_warn_depth "$queue")
    if [ "$depth" -gt "$bound" ]; then
        case "$queue" in
            insurance)
                warn "queue '$queue' holds $depth message(s), above the $bound threshold -- a flood (dispatched far faster than the 20/m drain) or a drain stalled for days; whether the work still achieves anything is Source health's verdict, not this one"
                ;;
            *)
                warn "queue '$queue' holds $depth message(s), above the $bound threshold"
                ;;
        esac
    else
        # The bound is printed even when it passes: the insurance backlog is
        # large by design, and a bare "holds 61000 message(s)" reads as a
        # problem to anyone who does not know the number it is being judged
        # against.
        ok "queue '$queue' holds $depth message(s), within the $bound threshold"
    fi
done
printf '  total queued: %s\n' "$total"

# --- source health -------------------------------------------------------
# The section above reports *load*; this one reports *outcome*. They are not
# substitutes: a queue can drain at its configured rate indefinitely against a
# source that no longer answers usefully. The VSZP scraper spent at least a day
# returning "unknown" for every company -- so nothing was ever written, the
# whole table stayed due for re-check, and the queue kept its healthy-looking
# depth the entire time.
#
# `source_health` owns what "a source is healthy" means, so it is chained here
# rather than re-implemented, exactly as offsite_status.sh owns the off-site
# verdict below.
section "Source health"

if docker compose ps --status running --services 2>/dev/null | grep -qx 'backend'; then
    # The thresholds are forwarded explicitly: `exec` does not inherit the
    # caller's environment, so an exported override would otherwise be silently
    # ignored and the run would look stricter or looser than it was asked to be.
    set +e
    source_output=$(docker compose exec -T \
        -e "CISTAFIRMA_SOURCE_WINDOW_HOURS=$SOURCE_WINDOW_HOURS" \
        -e "CISTAFIRMA_SOURCE_MIN_ATTEMPTS=$SOURCE_MIN_ATTEMPTS" \
        -e "CISTAFIRMA_SOURCE_MIN_SUCCESSES=$SOURCE_MIN_SUCCESSES" \
        backend python manage.py source_health --skip-checks 2>&1)
    source_rc=$?
    set -e
    printf '%s\n' "$source_output" | sed 's/^/  /'

    if [ "$source_rc" -eq 0 ]; then
        ok "every source with enough attempts produced a result"
    else
        # Reuse the count rather than the FAIL lines, so the command stays the
        # single owner of what its failures are -- and fail closed if its
        # summary is ever unreadable, since a changed format must not read as
        # success.
        unmet=$(printf '%s\n' "$source_output" \
            | sed -n 's/^Source health: \([0-9][0-9]*\) unmet$/\1/p' | tail -n 1)
        if [ -z "$unmet" ]; then
            bad "source_health exited $source_rc without a readable verdict"
        else
            failures=$((failures + unmet))
        fi
    fi
else
    bad "the backend is not running, so no source can be judged"
fi

# --- sync jobs -----------------------------------------------------------
# The queue section reports load and the one above reports what the sources
# achieve. Neither reads `registers_syncjob`, so an import whose worker died
# keeps its `running` status forever and the dashboard counts it as active --
# job #3 did that for fifteen days. `sync_health` owns what "an active job is
# really active" means, so it is chained here rather than re-implemented,
# exactly as offsite_status.sh owns the off-site verdict below.
section "Sync jobs"

if docker compose ps --status running --services 2>/dev/null | grep -qx 'backend'; then
    set +e
    sync_output=$(docker compose exec -T backend python manage.py sync_health --skip-checks 2>&1)
    sync_rc=$?
    set -e
    printf '%s\n' "$sync_output" | sed 's/^/  /'

    if [ "$sync_rc" -eq 0 ]; then
        ok "no active sync job is stuck or abandoned"
    else
        # Reuse the count rather than the FAIL lines, so the command stays the
        # single owner of what its failures are -- and fail closed if its
        # summary is ever unreadable, since a changed format must not read as
        # success.
        unmet=$(printf '%s\n' "$sync_output" \
            | sed -n 's/^Sync jobs: \([0-9][0-9]*\) unmet$/\1/p' | tail -n 1)
        if [ -z "$unmet" ]; then
            bad "sync_health exited $sync_rc without a readable verdict"
        else
            failures=$((failures + unmet))
        fi
    fi
else
    bad "the backend is not running, so no sync job can be judged"
fi

# --- backup and off-site controls ---------------------------------------
section "Backup and off-site controls"

set +e
offsite_output=$("$ROOT_DIR/scripts/local/offsite_status.sh" 2>&1)
offsite_rc=$?
set -e
printf '%s\n' "$offsite_output" | sed 's/^/  /'

if [ "$offsite_rc" -eq 0 ]; then
    ok "off-site controls are satisfied"
else
    # Reuse the count rather than the individual lines, so the off-site script
    # stays the single owner of what its failures are. If its summary line is
    # ever unreadable, fail closed -- a changed format must not read as success.
    unmet=$(printf '%s\n' "$offsite_output" \
        | sed -n 's/^Off-site backup controls: \([0-9][0-9]*\) unmet$/\1/p' | tail -n 1)
    if [ -z "$unmet" ]; then
        bad "offsite_status.sh exited $offsite_rc without a readable verdict"
    else
        failures=$((failures + unmet))
    fi
fi
# Read from the off-site script's own summary line for the same reason the unmet
# count is: the two scripts must not be coupled by the shape of its prose. This
# used to be `grep -c '^WARN  '` against that output, which counted warnings only
# as long as both `warn()` helpers kept printing exactly two spaces -- so a
# one-character edit in either file would have made every off-site warning vanish
# from this total, silently, with the gate still reporting SATISFIED. Unreadable
# is not zero, and it fails closed exactly as the unmet count above does.
offsite_warnings=$(printf '%s\n' "$offsite_output" \
    | sed -n 's/^Off-site backup warnings: \([0-9][0-9]*\)$/\1/p' | tail -n 1)
if [ -z "$offsite_warnings" ]; then
    bad "offsite_status.sh did not report a readable warning count"
else
    warnings=$((warnings + offsite_warnings))
fi

# --- weekly job ----------------------------------------------------------
# A control that never runs looks exactly like a control that always passes.
# The *scheduler's* own trigger evidence is the only trustworthy proof that it
# has ever fired the job: the log cannot distinguish an unattended run from a
# manual one, and a single manual run would otherwise read as "ran recently"
# while the schedule was in fact dead. So the log's last start is consulted only
# once the scheduler confirms it has fired the job at least once.
#
# On macOS that evidence is launchd's `runs` counter, which counts starts since
# the job was *loaded* -- not since it was installed. A reboot reloads every
# LaunchAgent and takes the counter back to 0, so 0 means "has not fired since
# this machine last booted", which is not the same claim as "never fired". On
# Linux it is the *timer's* last-trigger stamp, not its service's start time,
# for the same reason: a manual `systemctl --user start` of the service must not
# be able to read as proof that the schedule is alive.
section "Weekly backup job"

weekly_job_launchd() {
    local plist="$HOME/Library/LaunchAgents/$LABEL.plist"
    local launchctl_out launchctl_rc runs installed_days last_start days

    if [ ! -f "$plist" ]; then
        bad "the launchd job is not installed (run: make db-backup-schedule-install)"
        return 0
    fi

    ok "launchd plist is installed"

    # Captured in one call rather than `launchctl print | sed | head`: a `head`
    # that exits early can hand sed a SIGPIPE, and under `pipefail` that would
    # abort the whole gate mid-report with no verdict at all -- the one outcome
    # worse than a FAIL line.
    set +e
    launchctl_out=$(launchctl print "gui/$(id -u)/$LABEL" 2>&1)
    launchctl_rc=$?
    set -e

    if [ "$launchctl_rc" -eq 0 ]; then
        ok "job is loaded in launchd"
        runs=$(printf '%s\n' "$launchctl_out" \
            | sed -n 's/^[[:space:]]*runs = \([0-9][0-9]*\)$/\1/p' | tail -n 1)
    else
        bad "the launchd job is installed but not loaded (re-run: make db-backup-schedule-install)"
        runs=""
    fi

    if [ "$launchctl_rc" -eq 0 ] && [ -z "$runs" ]; then
        # Fail closed: launchd answered but its format was not what we parse.
        # Skipping the check here would report a dead control as a live one.
        bad "could not read launchd's run counter for the job"
    elif [ -n "$runs" ]; then
        printf '  launchd runs     : %s\n' "$runs"

        if [ "$runs" -eq 0 ]; then
            # A zero counter cannot distinguish a fresh install from a healthy
            # job that simply has not fired since the last reboot, and reading
            # it as "never" failed the gate on a Mac that was working perfectly
            # -- the plist's age says nothing about whether launchd ever fired
            # it. The log is the only other evidence there is. It cannot prove
            # the *scheduler* fired, because a manual run writes it too, so a
            # recent entry buys a warning rather than an OK: it rules out "this
            # has never worked", it does not establish "the schedule is alive".
            # The unattended run judges itself on the way out, and by then the
            # counter is at least 1, so it still gets the strict verdict below.
            local prior_start prior_days boot_secs boot_note
            prior_start=$(grep -h 'scheduled backup started' "$OUT_LOG" 2>/dev/null \
                | tail -n 1 | sed -n 's/^\[\([^]]*\)\].*/\1/p' || true)
            prior_days=""
            if [ -n "$prior_start" ]; then
                prior_days=$(iso_age_days "$prior_start")
            fi

            # When the boot time is what separates "reset by a reboot" from
            # "this schedule is dead", print it and let the operator make the
            # call. Deciding it here would need the plist's calendar rule: a
            # start recorded after the boot proves launchd did *not* make it,
            # but not that a fire has come due since, so a verdict would be a
            # guess. The strict judgement is not lost -- the weekly run reaches
            # the branch below with a non-zero counter and is judged there.
            boot_note=""
            # `[{,] *sec` and not `.*sec`, which would match the `usec` field
            # that follows it and report a boot in 1970.
            boot_secs=$(sysctl -n kern.boottime 2>/dev/null \
                | sed -n 's/.*[{,] *sec = \([0-9][0-9]*\).*/\1/p' || true)
            if [ -n "$boot_secs" ]; then
                boot_note=" (machine last booted $(date -r "$boot_secs" -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || printf 'at an unreadable time'))"
            fi

            installed_days=$(age_days "$plist")
            if [ -n "$prior_days" ] && [ "$prior_days" -ge 0 ] \
                && [ "$prior_days" -le "$RUN_GAP_MAX_DAYS" ]; then
                warn "launchd has not fired the job since this machine last booted, but $OUT_LOG records a start ${prior_days} day(s) ago${boot_note} -- a manual run or one from before the reboot, so the schedule itself is still unproven"
            elif [ "$installed_days" -lt 0 ]; then
                bad "launchd has never run the job and its install time is unreadable"
            elif [ "$installed_days" -gt "$RUN_GAP_MAX_DAYS" ]; then
                bad "launchd has not run the job since this machine last booted, and it was installed ${installed_days} day(s) ago"
            else
                warn "launchd has not run the job yet (installed ${installed_days} day(s) ago) -- its first unattended run is still pending"
            fi
        else
            last_start=$(grep -h 'scheduled backup started' "$OUT_LOG" 2>/dev/null \
                | tail -n 1 | sed -n 's/^\[\([^]]*\)\].*/\1/p' || true)

            if [ -z "$last_start" ]; then
                bad "launchd has run the job $runs time(s) but $OUT_LOG records no start"
            else
                days=$(iso_age_days "$last_start")
                if [ "$days" -lt 0 ]; then
                    bad "the job's last start time is unreadable: $last_start"
                else
                    printf '  last start       : %s (%s day(s) ago)\n' "$last_start" "$days"
                    if [ "$days" -gt "$RUN_GAP_MAX_DAYS" ]; then
                        bad "the weekly job last started ${days} day(s) ago (limit ${RUN_GAP_MAX_DAYS}) -- it may have stopped firing"
                    else
                        ok "the weekly job started recently (${days} day(s) ago)"
                    fi
                fi
            fi
        fi
    fi
}

weekly_job_systemd() {
    local unit_dir timer_unit service_unit
    local systemd_out systemd_rc
    local load unitfile active mono last triggered
    local installed_days last_start days

    unit_dir=$(scheduler_unit_dir)
    timer_unit="$unit_dir/$LABEL.timer"
    service_unit="$unit_dir/$LABEL.service"

    if [ ! -f "$timer_unit" ]; then
        bad "the systemd timer is not installed (run: make db-backup-schedule-install)"
        return 0
    fi

    ok "systemd timer unit is installed"

    if [ ! -f "$service_unit" ]; then
        bad "the timer is installed but its service unit is missing: $service_unit"
        return 0
    fi

    # Captured in one call for the same reason the launchd branch captures
    # rather than pipes: a filter that exits early can SIGPIPE the producer and
    # abort the gate mid-report under `pipefail`.
    set +e
    systemd_out=$(systemctl --user show \
        -p LoadState -p UnitFileState -p ActiveState \
        -p LastTriggerUSecMonotonic -p LastTriggerUSec \
        "$LABEL.timer" 2>&1)
    systemd_rc=$?
    set -e

    if [ "$systemd_rc" -ne 0 ]; then
        # Fail closed. Not being able to ask is not evidence that it is fine --
        # and an unreachable user manager is exactly what a job installed from a
        # session that no longer exists looks like.
        bad "the timer is installed but 'systemctl --user' cannot report on it (is a user manager running?)"
        return 0
    fi

    load=$(printf '%s\n' "$systemd_out" | sed -n 's/^LoadState=//p' | tail -n 1)
    unitfile=$(printf '%s\n' "$systemd_out" | sed -n 's/^UnitFileState=//p' | tail -n 1)
    active=$(printf '%s\n' "$systemd_out" | sed -n 's/^ActiveState=//p' | tail -n 1)
    mono=$(printf '%s\n' "$systemd_out" | sed -n 's/^LastTriggerUSecMonotonic=//p' | tail -n 1)
    last=$(printf '%s\n' "$systemd_out" | sed -n 's/^LastTriggerUSec=//p' | tail -n 1)

    if [ "$load" != "loaded" ]; then
        bad "the timer unit is not loaded (re-run: make db-backup-schedule-install)"
        return 0
    fi
    if [ "$unitfile" != "enabled" ] && [ "$unitfile" != "enabled-runtime" ]; then
        bad "the timer is installed but not enabled (re-run: make db-backup-schedule-install)"
        return 0
    fi
    if [ "$active" != "active" ]; then
        bad "the timer is enabled but not active (re-run: make db-backup-schedule-install)"
        return 0
    fi
    ok "the timer is enabled and active"

    # Two readings of one fact, because the property names have moved across
    # systemd versions. An empty value means "this systemd does not report that
    # property", which is NOT the same as "it never fired".
    #
    # The two can also *disagree*, and that is the case this host was in: a timer
    # that caught up a missed window at install time (`Persistent=true`) reports
    # `LastTriggerUSec` as the real wall-clock moment of that run -- 2026-09-15
    # 11:36:56 here -- while `LastTriggerUSecMonotonic` is 0. Reading the
    # monotonic stamp first called that "has not fired yet", and because that
    # branch returns early the run-age check below it never ran either: for the
    # whole first interval after an install, the gate could not report a weekly
    # job that had stopped. A "yes" from either reading therefore wins.
    #
    # That is the safe direction rather than the lenient one. Everything past
    # this point requires the log to record a start and a recent one, so a wrong
    # "yes" is caught by the next check and fails closed -- while a wrong "no" is
    # the one with nothing behind it, which is how a fired timer with a failed
    # run behind it came to be reported as a first run still pending.
    mono_says=""
    last_says=""
    if [ -n "$mono" ]; then
        if [ "$mono" = "0" ]; then mono_says="no"; else mono_says="yes"; fi
    fi
    if [ -n "$last" ]; then
        case "$last" in
            n/a) last_says="no" ;;
            *) last_says="yes" ;;
        esac
    fi

    if [ "$mono_says" = "yes" ] || [ "$last_says" = "yes" ]; then
        triggered="yes"
    elif [ "$mono_says" = "no" ] || [ "$last_says" = "no" ]; then
        triggered="no"
    else
        triggered=""
    fi

    if [ -z "$triggered" ]; then
        bad "could not read systemd's timer trigger stamp for the job"
        return 0
    fi

    if [ "$triggered" = "no" ]; then
        installed_days=$(age_days "$timer_unit")
        if [ "$installed_days" -lt 0 ]; then
            bad "the timer has never fired and its install time is unreadable"
        elif [ "$installed_days" -gt "$RUN_GAP_MAX_DAYS" ]; then
            bad "the timer has never fired although it was installed ${installed_days} day(s) ago"
        else
            warn "the timer has not fired yet (installed ${installed_days} day(s) ago) -- its first unattended run is still pending"
        fi
        return 0
    fi

    printf '  timer            : has fired at least once\n'

    last_start=$(grep -h 'scheduled backup started' "$OUT_LOG" 2>/dev/null \
        | tail -n 1 | sed -n 's/^\[\([^]]*\)\].*/\1/p' || true)

    if [ -z "$last_start" ]; then
        bad "the timer has fired but $OUT_LOG records no start"
        return 0
    fi

    days=$(iso_age_days "$last_start")
    if [ "$days" -lt 0 ]; then
        bad "the job's last start time is unreadable: $last_start"
        return 0
    fi

    printf '  last start       : %s (%s day(s) ago)\n' "$last_start" "$days"
    if [ "$days" -gt "$RUN_GAP_MAX_DAYS" ]; then
        bad "the weekly job last started ${days} day(s) ago (limit ${RUN_GAP_MAX_DAYS}) -- it may have stopped firing"
    else
        ok "the weekly job started recently (${days} day(s) ago)"
    fi
}

case "$CISTAFIRMA_OS" in
    macos) weekly_job_launchd ;;
    linux) weekly_job_systemd ;;
    *) bad "no weekly-job check exists for platform '$CISTAFIRMA_OS'" ;;
esac

# --- the last scheduled run's own verdict --------------------------------
#
# `scheduled_backup.sh` writes this marker whenever it exits non-zero and removes
# it only on a fully successful run, so its presence says exactly one thing: no
# scheduled run has succeeded since the failure it records. That makes it worth
# reading here rather than only writing there -- and on this host it is the whole
# of the alarm. `notify-send` is not installed (a headless server normally has
# no desktop session to show one), the scheduler's own record is the exit code
# nobody looks at, and a failure whose only signal is a file nobody opens is the
# silent failure this gate exists to prevent.
#
# A warning, never a failure -- and not as a softer verdict on the same fact, but
# because a marker that could fail the gate would keep failing it. The weekly job
# ends by running this gate and writes the marker when the gate fails, so a
# marker able to fail the gate would outlive the condition it records with no run
# able to clear it. The failure channel stays the job's own non-zero exit.
FAILURE_MARKER="$(log_dir)/LAST_FAILURE"
if [ -f "$FAILURE_MARKER" ]; then
    marker_head=$(head -n 1 "$FAILURE_MARKER" 2>/dev/null || true)
    marker_fail=$(grep -m 1 '^FAIL  ' "$FAILURE_MARKER" 2>/dev/null || true)
    if [ -n "$marker_fail" ]; then
        # The gate's own first concrete failure is more actionable than the
        # marker's header, which says only that something failed and when.
        marker_head="${marker_fail#FAIL  }"
    fi
    warn "the last scheduled backup run failed: ${marker_head:-see $FAILURE_MARKER}"
fi

# --- verdict -------------------------------------------------------------
printf '\n'
if [ "$failures" -eq 0 ] && [ "$warnings" -eq 0 ]; then
    echo "Operational controls: SATISFIED"
    exit 0
fi

if [ "$failures" -eq 0 ]; then
    echo "Operational controls: SATISFIED ($warnings warning(s))"
    exit 0
fi

echo "Operational controls: $failures unmet, $warnings warning(s)" >&2
exit 1
