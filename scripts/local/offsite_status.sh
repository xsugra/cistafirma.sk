#!/usr/bin/env bash
# Read-only off-site backup readiness report.
#
# Never writes anything, never starts a container and never touches the
# database. Exits non-zero when a required control is unmet, so it can gate
# CI or a health check.
set -Eeuo pipefail

# Machine-local off-site configuration; an already exported variable wins, so
# `make db-offsite-status CISTAFIRMA_OFFSITE_BACKUP_DIR=...` still overrides.
# Must precede the CISTAFIRMA_* defaults read just below.
LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# shellcheck source=lib/backup_time.sh
. "$LIB_DIR/backup_time.sh"
# shellcheck source=lib/backup_log.sh
. "$LIB_DIR/backup_log.sh"
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/offsite_crypto.sh
. "$LIB_DIR/offsite_crypto.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
STATE_DIR=$(state_dir)
DEFAULT_BACKUP_DIR="$STATE_DIR/backups"
BACKUP_DIR="${CISTAFIRMA_BACKUP_DIR:-$DEFAULT_BACKUP_DIR}"
MAX_AGE_DAYS="${CISTAFIRMA_BACKUP_MAX_AGE_DAYS:-7}"
DRILL_LOG="${CISTAFIRMA_DRILL_LOG:-$STATE_DIR/restore_drills.log}"
MAX_DRILL_AGE_DAYS="${CISTAFIRMA_DRILL_MAX_AGE_DAYS:-30}"
REPLICA_LOG="${CISTAFIRMA_REPLICA_LOG:-$STATE_DIR/replicas.log}"
MAX_REPLICA_AGE_DAYS="${CISTAFIRMA_REPLICA_MAX_AGE_DAYS:-14}"
REQUIRE_MOUNTED="${CISTAFIRMA_OFFSITE_REQUIRE_MOUNTED:-true}"

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

# "The volume is not attached" is a documented normal state -- DATA_PROTECTION.md
# says to keep it disconnected except while replicating -- so an unattended run
# must not call it a failure, or the weekly alert turns into noise that everyone
# learns to ignore. A deliberate `make db-offsite-status` keeps the strict
# default: when you ask by hand you want the truth, not the policy.
unmounted() {
    if [ "$REQUIRE_MOUNTED" = "true" ]; then
        bad "$1"
    else
        warn "$1 (not required for an unattended run)"
    fi
}

read_sha256() {
    python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["sha256"])
PY
}

plain_checksum() {
    sha256_of "$1"
}

printf 'CistaFirma off-site backup status\n'
printf '  local backup dir : %s\n' "$BACKUP_DIR"
printf '  off-site dir     : %s\n' "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-<not set>}"
printf '  max backup age   : %s day(s)\n\n' "$MAX_AGE_DAYS"

# --- newest local backup -------------------------------------------------
newest=""
if [ -d "$BACKUP_DIR" ]; then
    newest=$(ls -1 "$BACKUP_DIR"/cistafirma_*.dump 2>/dev/null | LC_ALL=C sort | tail -n 1 || true)
fi

if [ -z "$newest" ]; then
    bad "no local backup found in $BACKUP_DIR"
else
    days=$(age_days "$newest")
    printf '  newest dump      : %s (%s day(s) old)\n' "$(basename "$newest")" "$days"
    if [ "$days" -gt "$MAX_AGE_DAYS" ]; then
        bad "newest local backup is ${days} day(s) old (limit ${MAX_AGE_DAYS})"
    else
        ok "newest local backup is fresh (${days} day(s) old)"
    fi

    manifest="${newest}.json"
    if [ ! -f "$manifest" ]; then
        bad "manifest missing: $(basename "$manifest")"
    elif [ "$(read_sha256 "$manifest")" = "$(plain_checksum "$newest")" ]; then
        ok "newest local backup checksum matches its manifest"
    else
        bad "checksum mismatch for $(basename "$newest")"
    fi
fi

# --- off-site replica ----------------------------------------------------
printf '\n'
offsite="${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}"

# The reference for "is this a different filesystem": the directory the local
# dumps are written to, with $HOME standing in when there is no local backup
# directory yet -- both are on the disk the off-site copy must not share, and a
# reference that does not exist would refuse a perfectly good destination.
offsite_reference="$BACKUP_DIR"
[ -d "$offsite_reference" ] || offsite_reference="$HOME"

if [ -z "$offsite" ]; then
    unmounted "CISTAFIRMA_OFFSITE_BACKUP_DIR is not set — no off-site replica is possible"
elif ! cistafirma_offsite_mount_check "$offsite" "$offsite_reference"; then
    # The verdict, not the path, decides. A configured destination that is not
    # attached is reported as exactly that, never silently skipped past into
    # "no replica of the newest dump" -- which reads like a stale copy rather
    # than an unreachable destination, and sends the operator after the wrong
    # problem. See cistafirma_offsite_mount_check for what is measured.
    if [ "$CISTAFIRMA_OFFSITE_MOUNT_VERDICT" = "same-filesystem" ]; then
        # Not a mounting problem: the path is real, it is simply on this
        # machine's own disk, and the fix is the configuration.
        bad "off-site directory is on the same filesystem as the local backup: $offsite"
    elif [ "$CISTAFIRMA_OS" = "macos" ]; then
        # Kept word for word: the line production has always printed.
        unmounted "off-site directory is not mounted: $offsite"
    else
        unmounted "off-site directory is configured but not mounted: $offsite (${CISTAFIRMA_OFFSITE_MOUNT_REASON})"
    fi
else
    offsite=$(cd "$offsite" && pwd -P)
    ok "off-site directory is mounted: $offsite"

    if [ -n "$newest" ] && [ "$(device_id_of "$(dirname "$newest")")" = "$(device_id_of "$offsite")" ]; then
        bad "off-site directory is on the same filesystem as the local backup"
    else
        ok "off-site directory is on a different filesystem"
    fi

    # Whether the destination counts as encrypted is per-platform and lives in
    # lib/offsite_crypto.sh, so that this report and the script that actually
    # copies a dump there can never disagree about it.
    mount_point=$(mount_point_of "$offsite")
    cistafirma_offsite_crypto_check "$offsite" "$mount_point"

    if [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" = "encrypted" ]; then
        ok "off-site volume reports encryption"
    elif cistafirma_offsite_crypto_override_active; then
        if [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" = "unknown" ]; then
            warn "off-site volume encryption could NOT be verified (${CISTAFIRMA_OFFSITE_CRYPTO_REASON}) -- explicit temporary override active"
        else
            warn "off-site volume is NOT encrypted (explicit temporary override active)"
        fi
    elif [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" = "unknown" ]; then
        # Not the same failure as an unencrypted volume, and not a milder one:
        # nothing established that the destination is safe. Reported as its own
        # verdict so it cannot be read as "checked, and it was fine".
        bad "off-site volume encryption could not be verified: ${CISTAFIRMA_OFFSITE_CRYPTO_REASON}"
    elif [ "$CISTAFIRMA_OS" = "macos" ]; then
        # Kept word for word: the line production has always printed.
        bad "off-site volume is not encrypted"
    else
        bad "off-site volume is not encrypted (${CISTAFIRMA_OFFSITE_CRYPTO_REASON})"
    fi

    if [ -n "$newest" ]; then
        replica="$offsite/$(basename "$newest")"
        if [ ! -f "$replica" ]; then
            bad "no off-site replica of the newest dump ($(basename "$newest"))"
        elif [ ! -f "${replica}.json" ]; then
            bad "off-site replica manifest missing: $(basename "$replica").json"
        elif [ "$(read_sha256 "${replica}.json")" = "$(plain_checksum "$replica")" ]; then
            ok "newest dump has a checksum-verified off-site replica"
        else
            bad "off-site replica checksum mismatch: $(basename "$replica")"
        fi
    fi
fi

# --- restore drill -------------------------------------------------------
# A backup nobody has ever restored from is a hypothesis, not a control. The
# monthly cadence in docs/DATA_PROTECTION.md is only meaningful if a drill is
# recorded when it happens, so the gate reads the drill log back.
printf '\n'
drill_record=$(last_log_fields "$DRILL_LOG" timestamp backup public_tables source)

if [ -z "$drill_record" ]; then
    bad "no restore drill has been recorded in $DRILL_LOG"
else
    IFS=$'\t' read -r drill_time drill_backup drill_tables drill_source <<EOF
$drill_record
EOF
    days=$(iso_age_days "$drill_time")

    if [ "$days" -lt 0 ]; then
        bad "last recorded drill has an unreadable timestamp: $drill_time"
    else
        printf '  last drill       : %s (%s day(s) ago, %s, %s table(s))\n' \
            "${drill_backup:-unknown}" "$days" "${drill_source:-unknown}" "${drill_tables:-?}"
        if [ "$days" -gt "$MAX_DRILL_AGE_DAYS" ]; then
            bad "last restore drill was ${days} day(s) ago (limit ${MAX_DRILL_AGE_DAYS})"
        else
            ok "restore drill is recent (${days} day(s) ago)"
        fi

        # The doc asks for the monthly drill to come from the external copy once
        # one exists -- restoring the local dump does not prove the off-site one.
        # "Once one exists" means once the destination is really attached: a
        # directory that is present but unreachable has no off-site copy to
        # drill, and telling the operator to drill it would send them after a
        # volume that is not there.
        if [ "$drill_source" != "off-site" ] &&
            cistafirma_offsite_mount_check "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" "$offsite_reference"; then
            warn "last drill used the local backup; drill the off-site copy when one is present"
        fi
    fi
fi

# --- off-site replica staleness -----------------------------------------
# Read from a local record rather than from the volume. docs/DATA_PROTECTION.md
# says to keep the disk disconnected except while replicating, so its mtimes are
# unavailable exactly when this question matters most: "has it been attached
# lately?". The newest-replica check above answers "is the current dump safe?";
# this one answers "is the whole off-site habit still alive?", and only a local
# record can answer it while the disk is away.
printf '\n'
replica_record=$(last_log_fields "$REPLICA_LOG" timestamp backup)

if [ -z "$replica_record" ]; then
    bad "no off-site replica has ever been recorded in $REPLICA_LOG"
else
    IFS=$'\t' read -r replica_time replica_backup <<EOF
$replica_record
EOF
    days=$(iso_age_days "$replica_time")

    if [ "$days" -lt 0 ]; then
        bad "last recorded replica has an unreadable timestamp: $replica_time"
    else
        printf '  last replica     : %s (%s day(s) ago)\n' "${replica_backup:-unknown}" "$days"
        if [ "$days" -gt "$MAX_REPLICA_AGE_DAYS" ]; then
            bad "no off-site replica for ${days} day(s) (limit ${MAX_REPLICA_AGE_DAYS}) -- attach the volume and replicate"
        else
            ok "off-site replication is recent (${days} day(s) ago)"
        fi
    fi
fi

printf '\n'
# Both counts are published as their own summary lines, and they are the only
# thing a caller may read. The verdict below says whether the controls hold;
# this one says how much was excused, which the verdict cannot express -- a
# caller that counted the `WARN  ` lines instead would be coupled to this
# script's spacing through a convention neither script owns, and a control
# that silently under-reports is worse than one that reports nothing, because
# it is believed. Printed before the verdict, and on both exits, so the count
# is available whether or not the controls were satisfied.
echo "Off-site backup warnings: $warnings"

if [ "$failures" -eq 0 ]; then
    echo "Off-site backup controls: SATISFIED"
    exit 0
fi

echo "Off-site backup controls: $failures unmet" >&2
exit 1
