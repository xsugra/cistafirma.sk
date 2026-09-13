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
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
OUT_LOG="$HOME/Library/Logs/CistaFirma/backup.out.log"

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
# i.e. five days of drain capacity. That is an order of magnitude above the
# inherited sawtooth and ~58x below the 2026-09 flood (8.4 M messages enqueued in
# a day, against 14 400 drained), so it fires on a flood or on a drain stalled
# for days -- and on nothing else. It cannot tell those two apart, and it does
# not try to: whether the drained work still *achieves* anything is Source
# health's verdict, and depth has never been able to answer it.
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
# launchd's own `runs` counter is the only trustworthy evidence that it has
# *ever* spawned the job: the log cannot distinguish an unattended run from a
# manual one, and a single manual run would otherwise read as "ran recently"
# while the schedule was in fact dead. So the log's last start is consulted
# only once launchd confirms it has launched the job at least once.
section "Weekly backup job"

if [ ! -f "$PLIST" ]; then
    bad "the launchd job is not installed (run: make db-backup-schedule-install)"
else
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
            installed_days=$(age_days "$PLIST")
            if [ "$installed_days" -lt 0 ]; then
                bad "launchd has never run the job and its install time is unreadable"
            elif [ "$installed_days" -gt "$RUN_GAP_MAX_DAYS" ]; then
                bad "launchd has never run the job although it was installed ${installed_days} day(s) ago"
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
