#!/usr/bin/env bash
# Unattended backup entry point for the launchd schedule (and for manual runs).
#
# backup -> verify -> replica (only when the off-site volume is mounted).
# Read-only with respect to the database; never destructive.
set -Eeuo pipefail

# Machine-local off-site configuration (the volume path cannot live in the
# repo). Sourced before anything reads a CISTAFIRMA_* default; an already
# exported variable wins. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"

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

# Three distinct outcomes, reported distinctly. Collapsing them into one
# "volume not mounted" line is what hid a real defect: the scheduled job had no
# way to learn the volume path, so it printed the same message a genuinely
# unplugged drive would produce, every week, indefinitely.
if [ -z "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ]; then
    echo "[$(stamp)] WARNING: no off-site directory is configured, so NO off-site replica was made."
    echo "           Record it once with:"
    echo "             make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/<volume>/cistafirmaBackups"
    echo "           Then re-run the replica for today's dump:"
    echo "             make db-backup-replicate BACKUP_FILE='$backup_file'"
elif [ ! -d "${CISTAFIRMA_OFFSITE_BACKUP_DIR}" ]; then
    echo "[$(stamp)] WARNING: off-site directory is configured but not mounted, so NO replica was made:"
    echo "             ${CISTAFIRMA_OFFSITE_BACKUP_DIR}"
    echo "           Attach the volume and run: make db-backup-replicate BACKUP_FILE='$backup_file'"
else
    echo "[$(stamp)] off-site volume detected; replicating"
    "$ROOT_DIR/scripts/local/replicate_postgres_backup.sh" "$backup_file"
fi

echo "[$(stamp)] scheduled backup finished ($(basename "$backup_file"))"
