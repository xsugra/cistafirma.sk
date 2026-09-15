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
    # property", which is NOT the same as "it never fired" -- so the other is
    # consulted, and if neither answered the gate fails closed rather than
    # assuming the friendlier of the two readings.
    if [ -n "$mono" ]; then
        if [ "$mono" = "0" ]; then triggered="no"; else triggered="yes"; fi
    elif [ -n "$last" ]; then
        case "$last" in
            n/a) triggered="no" ;;
            *) triggered="yes" ;;
        esac
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
