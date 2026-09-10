#!/usr/bin/env bash
set -Eeuo pipefail

# Machine-local off-site configuration; an already exported
# CISTAFIRMA_OFFSITE_BACKUP_DIR wins over the config file. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"

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
    echo "         make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/<volume>/cistafirmaBackups" >&2
    echo "       or pass it for a single run: make db-backup-replicate BACKUP_FILE=... CISTAFIRMA_OFFSITE_BACKUP_DIR=..." >&2
    exit 1
fi

if [ ! -d "$OFFSITE_DIR" ]; then
    echo "ERROR: off-site backup directory is not mounted or does not exist: $OFFSITE_DIR" >&2
    exit 1
fi

OFFSITE_DIR=$(cd "$OFFSITE_DIR" && pwd -P)
if [ "$(stat -f '%d' "$(dirname "$BACKUP_FILE")")" = "$(stat -f '%d' "$OFFSITE_DIR")" ]; then
    echo "ERROR: off-site backup directory must be on a different filesystem." >&2
    exit 1
fi

VOLUME_MOUNT_POINT=$(df -P "$OFFSITE_DIR" | awk 'NR == 2 { print $NF }')
if [ -z "$VOLUME_MOUNT_POINT" ]; then
    echo "ERROR: could not determine the off-site volume mount point." >&2
    exit 1
fi

if ! diskutil info "$VOLUME_MOUNT_POINT" 2>/dev/null | grep -Eq 'FileVault:.*Yes|Encrypted:.*Yes'; then
    if [ "${CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP:-false}" = "true" ]; then
        echo "WARNING: copying a database backup to an unencrypted external volume by explicit temporary override." >&2
        echo "WARNING: replace this replica after the volume is encrypted." >&2
    else
    echo "ERROR: off-site backup directory must be on an encrypted macOS volume." >&2
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

echo "Off-site replica verified: $OFFSITE_BACKUP"
