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
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
DEFAULT_BACKUP_DIR="${XDG_STATE_HOME:-$HOME/Library/Application Support}/CistaFirma/backups"
BACKUP_DIR="${CISTAFIRMA_BACKUP_DIR:-$DEFAULT_BACKUP_DIR}"
MAX_AGE_DAYS="${CISTAFIRMA_BACKUP_MAX_AGE_DAYS:-7}"
DEFAULT_DRILL_LOG="${XDG_STATE_HOME:-$HOME/Library/Application Support}/CistaFirma/restore_drills.log"
DRILL_LOG="${CISTAFIRMA_DRILL_LOG:-$DEFAULT_DRILL_LOG}"
MAX_DRILL_AGE_DAYS="${CISTAFIRMA_DRILL_MAX_AGE_DAYS:-30}"

failures=0
ok() { printf 'OK    %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; }
bad() {
    printf 'FAIL  %s\n' "$*"
    failures=$((failures + 1))
}

read_sha256() {
    python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["sha256"])
PY
}

age_days() {
    python3 - "$1" <<'PY'
import os
import sys
import time

print(int((time.time() - os.path.getmtime(sys.argv[1])) // 86400))
PY
}

plain_checksum() {
    shasum -a 256 "$1" | awk '{print $1}'
}

# Last recorded successful drill, as "timestamp<TAB>backup<TAB>tables<TAB>source".
# Unparseable lines are skipped rather than trusted, so a truncated append cannot
# be mistaken for evidence.
last_drill() {
    python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(0)

last = None
for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if isinstance(record, dict) and record.get("timestamp"):
        last = record

if last:
    print("{}\t{}\t{}\t{}".format(
        last.get("timestamp", ""),
        last.get("backup", ""),
        last.get("public_tables", ""),
        last.get("source", ""),
    ))
PY
}

iso_age_days() {
    python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone

try:
    stamp = datetime.fromisoformat(sys.argv[1])
except ValueError:
    print(-1)
    raise SystemExit(0)

if stamp.tzinfo is None:
    stamp = stamp.replace(tzinfo=timezone.utc)

print(int((datetime.now(timezone.utc) - stamp).total_seconds() // 86400))
PY
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

if [ -z "$offsite" ]; then
    bad "CISTAFIRMA_OFFSITE_BACKUP_DIR is not set — no off-site replica is possible"
elif [ ! -d "$offsite" ]; then
    bad "off-site directory is not mounted: $offsite"
else
    offsite=$(cd "$offsite" && pwd -P)
    ok "off-site directory is mounted: $offsite"

    if [ -n "$newest" ] && [ "$(stat -f '%d' "$(dirname "$newest")")" = "$(stat -f '%d' "$offsite")" ]; then
        bad "off-site directory is on the same filesystem as the local backup"
    else
        ok "off-site directory is on a different filesystem"
    fi

    mount_point=$(df -P "$offsite" | awk 'NR == 2 { print $NF }')
    if [ -n "$mount_point" ] && diskutil info "$mount_point" 2>/dev/null | grep -Eq 'FileVault:.*Yes|Encrypted:.*Yes'; then
        ok "off-site volume reports encryption"
    elif [ "${CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP:-false}" = "true" ]; then
        warn "off-site volume is NOT encrypted (explicit temporary override active)"
    else
        bad "off-site volume is not encrypted"
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
drill_record=$(last_drill "$DRILL_LOG")

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
        if [ "$drill_source" != "off-site" ] && [ -d "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ]; then
            warn "last drill used the local backup; drill the off-site copy when one is present"
        fi
    fi
fi

printf '\n'
if [ "$failures" -eq 0 ]; then
    echo "Off-site backup controls: SATISFIED"
    exit 0
fi

echo "Off-site backup controls: $failures unmet" >&2
exit 1
