#!/usr/bin/env bash
# Retention for PostgreSQL backups.
#
# Keeps the N newest backup artifacts and deletes older ones. Dry-run unless
# --apply is given. Never deletes the newest artifact and only ever touches files
# inside the backup directory (fail-closed inside the repo).
#
# Two directories, two artifact shapes, one rule. Locally the artifact is
# `cistafirma_<ts>.dump`; off-site it is `cistafirma_<ts>.dump.gpg`, because the
# replica is encrypted at source. Retention has to know which is which: a rule
# that counted `.dump` files off-site would find none, report "nothing to prune"
# for ever, and grow without bound -- a retention control that silently does
# nothing is worse than none, because the space it was meant to free is believed
# freed.
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

Keeps the N newest artifacts and deletes older ones, with their manifests.

  --apply      actually delete (default: only print what would be deleted)
  --keep=N     how many newest backups to keep (default 7, or
               CISTAFIRMA_BACKUP_KEEP)
  --offsite    also prune CISTAFIRMA_OFFSITE_BACKUP_DIR by the same rule

With --offsite, any unencrypted `cistafirma_*.dump` left there by a version of
the tooling that predates encryption-at-source is listed as well, and removed
under --apply. Those files are the database in the clear and are the one thing
on that volume that should not exist; `make db-offsite-status` fails while any
of them is present.
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

# Shared by every destructive path below. Pruning inside the repository would
# delete the working tree's own files, and this script is the only thing here
# that deletes anything, so the refusal lives in one place rather than in each
# caller's memory. Prints the resolved path on success.
assert_prunable_dir() {
    local dir="$1"

    dir=$(cd "$dir" && pwd -P) || return 1

    case "$dir" in
        "$ROOT_DIR"|"$ROOT_DIR"/*)
            echo "ERROR: refusing to prune inside the repository: $dir" >&2
            return 1
            ;;
    esac

    printf '%s' "$dir"
}

remove_or_report() {
    local target="$1"

    if [ "$apply" = true ]; then
        rm -f -- "$target"
        echo "  deleted       $(basename "$target")"
    else
        echo "  would delete  $(basename "$target")"
    fi
}

# prune_dir <dir> <label> <glob>
#
# The glob is the artifact's shape in that directory and nothing else: `.dump`
# locally, `.dump.gpg` off-site. The manifest is always `<artifact>.json`, so one
# rule covers both.
#
# shellcheck disable=SC2086  # $glob is a glob and must stay unquoted
prune_dir() {
    local dir="$1"
    local label="$2"
    local glob="$3"
    local total=0 listing="" file remove_count index

    if [ ! -d "$dir" ]; then
        echo "SKIP  $label directory does not exist: $dir"
        return 0
    fi

    dir=$(assert_prunable_dir "$dir") || return 1

    while IFS= read -r file; do
        [ -n "$file" ] || continue
        listing="${listing}${file}"$'\n'
        total=$((total + 1))
    done < <(ls -1 "$dir"/$glob 2>/dev/null | LC_ALL=C sort || true)

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
        if [ -e "$file" ]; then
            remove_or_report "$file"
        fi
        if [ -e "${file}.json" ]; then
            remove_or_report "${file}.json"
        fi
    done <<< "$listing"
    return 0
}

# Anything on the off-site volume that is not a ciphertext: an older replica
# written in the clear, or a half-written artifact from an encryption that died
# partway. None of it belongs there. Off-site only -- locally a `.dump` is the
# normal, intended shape.
#
# Announced before it lists anything. These files are deleted by a different rule
# from the retention prune above -- "not an artifact of the current shape", not
# "older than the newest N" -- and a bare list of paths under a `--keep` heading
# reads as if the retention count had decided them. An operator who believes a
# deletion came from retention will re-derive it from the wrong rule.
#
# shellcheck disable=SC2086  # the patterns are globs and must stay unquoted
purge_offsite_plaintext() {
    local dir="$1"
    local patterns="cistafirma_*.dump cistafirma_*.dump.json cistafirma_*.partial.*"
    local pattern target found=0

    dir=$(assert_prunable_dir "$dir") || return 1

    echo "  not an artifact of the current shape — never kept, whatever --keep says:"
    for pattern in $patterns; do
        for target in "$dir"/$pattern; do
            [ -f "$target" ] || continue
            found=$((found + 1))
            remove_or_report "$target"
        done
    done

    if [ "$found" -eq 0 ]; then
        echo "    none"
    else
        echo "  unencrypted leftovers: $found file(s) that should not be on this volume"
    fi
    return 0
}

if ! prune_dir "$BACKUP_DIR" "local" "cistafirma_*.dump"; then
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
    printf '\n'
    if ! prune_dir "$CISTAFIRMA_OFFSITE_BACKUP_DIR" "off-site" "cistafirma_*.dump.gpg"; then
        exit 1
    fi
    if [ -d "$CISTAFIRMA_OFFSITE_BACKUP_DIR" ]; then
        purge_offsite_plaintext "$CISTAFIRMA_OFFSITE_BACKUP_DIR" || exit 1
    fi
fi

printf '\n'
if [ "$apply" = true ]; then
    echo "Prune applied (kept the newest $keep)."
else
    echo "Dry run — re-run with --apply to delete the listed files."
fi
