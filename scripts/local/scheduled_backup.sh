#!/usr/bin/env bash
# Unattended backup entry point for the launchd schedule (and for manual runs).
#
# backup -> verify -> replica (only when the off-site volume is mounted).
# Read-only with respect to the database; never destructive.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd "$ROOT_DIR"

stamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

echo "[$(stamp)] scheduled backup started (root: $ROOT_DIR)"

backup_output=$("$ROOT_DIR/scripts/local/backup_postgres.sh")
printf '%s\n' "$backup_output"

backup_file=$(printf '%s\n' "$backup_output" | awk -F': ' '/^Backup created: /{print $2}' | tail -n 1)
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
    echo "[$(stamp)] ERROR: could not determine the created backup file." >&2
    exit 1
fi

"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$backup_file"

if [ -n "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ] && [ -d "${CISTAFIRMA_OFFSITE_BACKUP_DIR}" ]; then
    echo "[$(stamp)] off-site volume detected; replicating"
    "$ROOT_DIR/scripts/local/replicate_postgres_backup.sh" "$backup_file"
else
    echo "[$(stamp)] off-site volume not mounted; replica skipped"
fi

echo "[$(stamp)] scheduled backup finished ($(basename "$backup_file"))"
