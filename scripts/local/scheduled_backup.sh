#!/usr/bin/env bash
# Unattended backup entry point for the launchd schedule (and for manual runs).
#
# backup -> verify -> replica (only when the off-site volume is mounted)
#        -> operational gate.
#
# Read-only with respect to the database; never destructive.
#
# Its failure has to be *audible*. A job whose only failure signal is a line in
# a log file nobody opens is indistinguishable from a job that works -- which is
# how the missing replica survived several weeks unnoticed. Any failure below
# writes a marker, posts a notification, and exits non-zero so launchd records
# it too.
set -Eeuo pipefail

# Machine-local off-site configuration (the volume path cannot live in the
# repo). Sourced before anything reads a CISTAFIRMA_* default; an already
# exported variable wins. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd "$ROOT_DIR"

LOG_DIR="$HOME/Library/Logs/CistaFirma"
OUT_LOG="$LOG_DIR/backup.out.log"
FAILURE_MARKER="$LOG_DIR/LAST_FAILURE"

# Captured so the failure report can quote what actually failed, rather than
# only the exit code.
GATE_OUTPUT=""

stamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

say() { printf '[%s] %s\n' "$(stamp)" "$*"; }

notify() {
    # Best effort: a notification that cannot be displayed must never turn a
    # successful backup into a failed one, so every step is guarded.
    command -v osascript >/dev/null 2>&1 || return 0
    osascript -e "display notification \"$1\" with title \"CistaFirma backup\"" >/dev/null 2>&1 || true
}

# One exit path for every kind of failure -- an explicit `exit 1`, a `set -e`
# abort, a failed command substitution. An ERR trap would miss the explicit
# exits, and the whole point is that no failure escapes unrecorded.
on_exit() {
    local rc=$?

    if [ "$rc" -eq 0 ]; then
        # Only a fully successful run clears it, so a later failure can never be
        # silently forgiven by a partially successful one.
        rm -f "$FAILURE_MARKER"
        return 0
    fi

    set +e
    umask 077
    mkdir -p "$LOG_DIR"
    {
        echo "CistaFirma scheduled backup FAILED at $(stamp) (exit $rc)"
        echo
        echo "--- operational gate ---"
        if [ -n "$GATE_OUTPUT" ]; then
            printf '%s\n' "$GATE_OUTPUT"
        else
            echo "(the gate was never reached; the failure happened before it)"
        fi
        echo
        echo "--- last 20 lines of $(basename "$OUT_LOG") ---"
        tail -n 20 "$OUT_LOG" 2>/dev/null
    } > "$FAILURE_MARKER" 2>/dev/null

    # For the notification, lead with the first concrete failure rather than the
    # exit code: "off-site volume is not encrypted" is actionable, "exit 1" is not.
    first_fail=$(printf '%s\n' "$GATE_OUTPUT" | grep -m 1 '^FAIL  ' || true)
    if [ -n "$first_fail" ]; then
        notify "${first_fail#FAIL  } (exit $rc)"
    else
        notify "scheduled backup failed (exit $rc); see LAST_FAILURE in ~/Library/Logs/CistaFirma"
    fi

    say "FAILED (exit $rc) -- details in $FAILURE_MARKER" >&2
    return 0
}
trap on_exit EXIT

say "scheduled backup started (root: $ROOT_DIR)"

backup_output=$("$ROOT_DIR/scripts/local/backup_postgres.sh")
printf '%s\n' "$backup_output"

backup_file=$(printf '%s\n' "$backup_output" | awk -F': ' '/^Backup created: /{print $2}' | tail -n 1)
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
    say "ERROR: could not determine the created backup file." >&2
    exit 1
fi

"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$backup_file"

# Three distinct outcomes, reported distinctly. Collapsing them into one
# "volume not mounted" line is what hid a real defect: the scheduled job had no
# way to learn the volume path, so it printed the same message a genuinely
# unplugged drive would produce, every week, indefinitely.
if [ -z "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ]; then
    say "WARNING: no off-site directory is configured, so NO off-site replica was made."
    echo "           Record it once with:"
    echo "             make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/<volume>/cistafirmaBackups"
    echo "           Then re-run the replica for today's dump:"
    echo "             make db-backup-replicate BACKUP_FILE='$backup_file'"
elif [ ! -d "${CISTAFIRMA_OFFSITE_BACKUP_DIR}" ]; then
    say "WARNING: off-site directory is configured but not mounted, so NO replica was made:"
    echo "             ${CISTAFIRMA_OFFSITE_BACKUP_DIR}"
    echo "           Attach the volume and run: make db-backup-replicate BACKUP_FILE='$backup_file'"
else
    say "off-site volume detected; replicating"
    "$ROOT_DIR/scripts/local/replicate_postgres_backup.sh" "$backup_file"
fi

# The local backup can succeed while everything around it is broken, so the run
# ends by asking the whole question rather than only "did the dump get made?".
#
# The off-site mount is explicitly NOT required here: the volume is documented
# as normally disconnected, so a gate that failed every week for a documented
# posture would be ignored within a month. Replica *staleness* is still a
# failure -- that is the signal the off-site habit has died, and no amount of
# local success compensates for it.
say "running the operational gate"
set +e
GATE_OUTPUT=$(CISTAFIRMA_OFFSITE_REQUIRE_MOUNTED=false "$ROOT_DIR/scripts/local/ops_check.sh" 2>&1)
gate_rc=$?
set -e
printf '%s\n' "$GATE_OUTPUT"

if [ "$gate_rc" -ne 0 ]; then
    say "operational gate did not pass (exit $gate_rc)" >&2
    exit "$gate_rc"
fi

say "scheduled backup finished ($(basename "$backup_file"))"
