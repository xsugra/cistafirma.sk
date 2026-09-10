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
QUEUE_WARN_DEPTH="${CISTAFIRMA_QUEUE_WARN_DEPTH:-50000}"
QUEUES="${CISTAFIRMA_QUEUES:-celery ruz_full orsr financials insurance}"

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
    if [ "$depth" -gt "$QUEUE_WARN_DEPTH" ]; then
        warn "queue '$queue' holds $depth message(s), above the $QUEUE_WARN_DEPTH threshold"
    else
        ok "queue '$queue' holds $depth message(s)"
    fi
done
printf '  total queued: %s\n' "$total"

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
warnings=$((warnings + $(printf '%s\n' "$offsite_output" | grep -c '^WARN  ' || true)))

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
