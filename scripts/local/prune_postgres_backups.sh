#!/usr/bin/env bash
# Retention for PostgreSQL backups.
#
# Keeps the N newest *.dump + *.json pairs and deletes older ones. Dry-run
# unless --apply is given. Never deletes the newest backup and only ever
# touches files inside the backup directory (fail-closed inside the repo).
set -Eeuo pipefail

# Machine-local off-site configuration; an already exported variable wins.
# This has to come before the CISTAFIRMA_* defaults below (CISTAFIRMA_BACKUP_KEEP
# is read a few lines down, well before ROOT_DIR is computed).
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"

usage() {
    cat <<'USAGE'
Usage: prune_postgres_backups.sh [--apply] [--keep=N] [--offsite]

Keeps the N newest backups and deletes older *.dump + *.json pairs.

  --apply      actually delete (default: only print what would be deleted)
  --keep=N     how many newest backups to keep (default 7, or
               CISTAFIRMA_BACKUP_KEEP)
  --offsite    also prune CISTAFIRMA_OFFSITE_BACKUP_DIR with the same rule
  -h, --help   show this help
USAGE
}

apply=false
offsite=false
keep="${CISTAFIRMA_BACKUP_KEEP:-7}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply) apply=true ;;
        --offsite) offsite=true ;;
        --keep=*) keep="${1#--keep=}" ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
    shift
done

case "$keep" in
    ''|*[!0-9]*)
        echo "ERROR: --keep must be a positive integer, got '$keep'" >&2
        exit 64
        ;;
esac

if [ "$keep" -lt 1 ]; then
    echo "ERROR: --keep must be at least 1 (the newest backup is never deleted)" >&2
    exit 64
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
DEFAULT_BACKUP_DIR="$(state_dir)/backups"
BACKUP_DIR="${CISTAFIRMA_BACKUP_DIR:-$DEFAULT_BACKUP_DIR}"

prune_dir() {
    dir=$1
    label=$2

    if [ ! -d "$dir" ]; then
        echo "SKIP  $label directory does not exist: $dir"
        return 0
    fi

    dir=$(cd "$dir" && pwd -P)
    case "$dir" in
        "$ROOT_DIR"|"$ROOT_DIR"/*)
            echo "ERROR: refusing to prune inside the repository: $dir" >&2
            return 1
            ;;
    esac

    total=0
    listing=""
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        listing="${listing}${file}"$'\n'
        total=$((total + 1))
    done < <(ls -1 "$dir"/cistafirma_*.dump 2>/dev/null | LC_ALL=C sort || true)

    echo "$label: $dir — $total backup(s) present, keeping the newest $keep"
    if [ "$total" -le "$keep" ]; then
        echo "  nothing to prune"
        return 0
    fi

    remove_count=$((total - keep))
    index=0
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        index=$((index + 1))
        [ "$index" -le "$remove_count" ] || break
        for target in "$file" "${file}.json"; do
            if [ ! -e "$target" ]; then
                continue
            fi
            if [ "$apply" = true ]; then
                rm -f -- "$target"
                echo "  deleted       $(basename "$target")"
            else
                echo "  would delete  $(basename "$target")"
            fi
        done
    done <<< "$listing"
    return 0
}

if ! prune_dir "$BACKUP_DIR" "local"; then
    exit 1
fi

if [ "$offsite" = true ]; then
    if [ -z "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ]; then
        echo "ERROR: --offsite requires CISTAFIRMA_OFFSITE_BACKUP_DIR to be set" >&2
        exit 1
    fi
    # A directory that exists but is not attached must not be pruned. This is
    # the only destructive caller of the off-site path, and the failure it
    # guards against is not a failed deletion but a successful one in the wrong
    # place: on Linux an armed systemd automount keeps the directory present
    # while its target is unreachable, and a bare local directory here would be
    # pruned as if it were the off-site copy. A destination that is simply
    # absent is left to prune_dir's own SKIP below.
    if [ -d "$CISTAFIRMA_OFFSITE_BACKUP_DIR" ] &&
        ! cistafirma_offsite_mount_check "$CISTAFIRMA_OFFSITE_BACKUP_DIR" "$BACKUP_DIR"; then
        echo "ERROR: refusing to prune the off-site directory: ${CISTAFIRMA_OFFSITE_MOUNT_REASON}" >&2
        exit 1
    fi
    if ! prune_dir "$CISTAFIRMA_OFFSITE_BACKUP_DIR" "off-site"; then
        exit 1
    fi
fi

printf '\n'
if [ "$apply" = true ]; then
    echo "Prune applied (kept the newest $keep)."
else
    echo "Dry run — re-run with --apply to delete the listed files."
fi
