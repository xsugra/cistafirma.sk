#!/usr/bin/env bash
set -Eeuo pipefail

LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib

# Machine-local off-site configuration; an already exported
# CISTAFIRMA_OFFSITE_BACKUP_DIR wins over the config file. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# Platform primitives (stat/checksum/mount-point/state dir) and the encryption
# verdict. Sourced after backup_env.sh so a machine-local CISTAFIRMA_* setting
# is in scope for both.
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/offsite_crypto.sh
. "$LIB_DIR/offsite_crypto.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump" >&2
    exit 64
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
BACKUP_FILE=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")
OFFSITE_DIR="${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}"

if [ -z "$OFFSITE_DIR" ]; then
    echo "ERROR: CISTAFIRMA_OFFSITE_BACKUP_DIR is not set and no machine-local" >&2
    echo "       config supplied it. Record the volume once with:" >&2
    echo "         make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=$(example_offsite_dir)" >&2
    echo "       or pass it for a single run: make db-backup-replicate BACKUP_FILE=... CISTAFIRMA_OFFSITE_BACKUP_DIR=..." >&2
    exit 1
fi

# "It is attached" is a fact about the kernel, not about the existence of a
# path. On Linux the off-site destination is typically an armed systemd
# automount, which keeps the directory -- and even a mountinfo entry -- present
# while its target is unreachable, so a test on the path alone would pass and
# rsync would write the "replica" onto the same disk as the original. See
# cistafirma_offsite_mount_check for what is actually measured.
if ! cistafirma_offsite_mount_check "$OFFSITE_DIR" "$(dirname "$BACKUP_FILE")"; then
    if [ "$CISTAFIRMA_OFFSITE_MOUNT_VERDICT" = "same-filesystem" ]; then
        echo "ERROR: off-site backup directory must be on a different filesystem." >&2
    else
        # Word for word what production has always printed.
        echo "ERROR: off-site backup directory is not mounted or does not exist: $OFFSITE_DIR" >&2
        # The reason is for the Linux host, where "the automount could not reach
        # its target" and "someone typed the wrong path" call for different
        # actions. macOS prints exactly the line it always has.
        if [ "$CISTAFIRMA_OS" != "macos" ]; then
            echo "       ${CISTAFIRMA_OFFSITE_MOUNT_REASON}" >&2
        fi
    fi
    exit 1
fi

OFFSITE_DIR=$(cd "$OFFSITE_DIR" && pwd -P)
# Kept from before the port. It re-asks a question the check above has already
# answered, once symlinks are resolved, and a mistake this expensive is worth
# refusing twice.
if [ "$(device_id_of "$(dirname "$BACKUP_FILE")")" = "$(device_id_of "$OFFSITE_DIR")" ]; then
    echo "ERROR: off-site backup directory must be on a different filesystem." >&2
    exit 1
fi

VOLUME_MOUNT_POINT=$(mount_point_of "$OFFSITE_DIR")
if [ -z "$VOLUME_MOUNT_POINT" ]; then
    echo "ERROR: could not determine the off-site volume mount point." >&2
    exit 1
fi

# The destination must be on an encrypted volume. What "encrypted" means is
# per-platform and lives in lib/offsite_crypto.sh -- on macOS the diskutil check
# this script has always run, on Linux a LUKS/dm-crypt check against the local
# block device, or the same check performed over SSH when the destination is a
# FUSE (sshfs) mount whose bytes are on the far side.
#
# Both a plain "not encrypted" and an "could not be verified" verdict stop the
# copy here: the second is not a lesser failure, it is the same one with the
# uncomfortable detail that nobody actually looked.
cistafirma_offsite_crypto_check "$OFFSITE_DIR" "$VOLUME_MOUNT_POINT"
if [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" != "encrypted" ]; then
    if cistafirma_offsite_crypto_override_active; then
        if [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" = "unknown" ]; then
            echo "WARNING: copying a database backup to a volume whose encryption could NOT be verified, by explicit temporary override." >&2
            echo "WARNING: ${CISTAFIRMA_OFFSITE_CRYPTO_REASON}" >&2
        else
            echo "WARNING: copying a database backup to an unencrypted external volume by explicit temporary override." >&2
        fi
        echo "WARNING: replace this replica after the volume is encrypted." >&2
    elif [ "$CISTAFIRMA_OS" = "macos" ]; then
        # Kept word for word: this is what production has always printed, and a
        # port may not reword the one line an operator has learned to recognise.
        # On macOS the verdict is never `unknown`, so this covers both cases.
        echo "ERROR: off-site backup directory must be on an encrypted macOS volume." >&2
        exit 1
    elif [ "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" = "unknown" ]; then
        echo "ERROR: the off-site backup directory's encryption could not be verified." >&2
        echo "       ${CISTAFIRMA_OFFSITE_CRYPTO_REASON}" >&2
        echo "       Set CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true only if that destination is deliberately accepted." >&2
        exit 1
    else
        echo "ERROR: off-site backup directory must be on an encrypted volume." >&2
        echo "       ${CISTAFIRMA_OFFSITE_CRYPTO_REASON}" >&2
        exit 1
    fi
fi

"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$BACKUP_FILE"

umask 077
rsync -a --checksum \
    "$BACKUP_FILE" \
    "${BACKUP_FILE}.json" \
    "$OFFSITE_DIR/"

OFFSITE_BACKUP="$OFFSITE_DIR/$(basename "$BACKUP_FILE")"
"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$OFFSITE_BACKUP"

# Record the replica. The volume is documented as normally disconnected, so the
# replica file's own mtime is unavailable exactly when the staleness question
# matters most -- "has the disk been attached lately?". A local record is the
# only thing that can answer that while the disk is away. Written only after
# both the source and the copy verified, so the record means a real replica.
REPLICA_LOG="${CISTAFIRMA_REPLICA_LOG:-$(state_dir)/replicas.log}"

replica_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["sha256"])' \
    "${BACKUP_FILE}.json" 2>/dev/null || true)

umask 077
mkdir -p "$(dirname "$REPLICA_LOG")"
python3 - "$REPLICA_LOG" "$OFFSITE_BACKUP" "${replica_sha:-}" "$OFFSITE_DIR" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

log_path, replica_path, sha, offsite_dir = sys.argv[1:5]
record = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "backup": Path(replica_path).name,
    "sha256": sha,
    "offsite_dir": offsite_dir,
}
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
PY

echo "Off-site replica verified: $OFFSITE_BACKUP"
echo "Recorded in: $REPLICA_LOG"
