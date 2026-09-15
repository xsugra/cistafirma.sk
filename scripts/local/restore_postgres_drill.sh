#!/usr/bin/env bash
set -Eeuo pipefail

# Machine-local backup configuration; an already exported variable wins. Gives
# this script CISTAFIRMA_OFFSITE_BACKUP_DIR (to label the drill's source) and
# CISTAFIRMA_DRILL_LOG. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_env.sh"
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"
# shellcheck source=lib/backup_gpg.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_gpg.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump[.gpg]" >&2
    exit 64
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
BACKUP_FILE=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: backup file does not exist: $BACKUP_FILE" >&2
    exit 1
fi

"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$BACKUP_FILE"

# A drill of the off-site replica is a drill of the *encrypted* artifact, because
# that is the thing that exists -- the plaintext dump never leaves this machine.
# It also means the drill answers two questions at once: that the backup restores,
# and that the private key needed to read it is still available and still works.
# Key loss is the failure that a restore drill is uniquely able to catch, and it
# is invisible to every other control here.
#
# This runs into a temporary file and is removed on the way out. The plaintext is
# written to local disk briefly, which is not a new exposure -- the local backups
# are plaintext already; the only copy that had to be protected is the one that
# leaves the machine.
drill_input="$BACKUP_FILE"
decrypted_file=""
case "$BACKUP_FILE" in
    *.gpg)
        tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/cistafirma_drill.XXXXXX")
        chmod 700 "$tmpdir"
        decrypted_file="$tmpdir/input.dump"
        echo "Decrypting the off-site replica for the drill..."
        cistafirma_gpg_decrypt "$BACKUP_FILE" "$decrypted_file"
        drill_input="$decrypted_file"
        ;;
esac

container_name="cistafirma_restore_drill_$(date -u +%Y%m%dT%H%M%SZ)_$$"
drill_password=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
cleanup() {
    docker rm -f "$container_name" >/dev/null 2>&1 || true
    if [ -n "$decrypted_file" ]; then
        rm -rf -- "$(dirname "$decrypted_file")"
    fi
}
trap cleanup EXIT

docker run --pull=never --detach \
    --name "$container_name" \
    --env POSTGRES_DB=cistafirma_restore_drill \
    --env POSTGRES_USER=restore_drill \
    --env POSTGRES_PASSWORD="$drill_password" \
    postgres:16-alpine >/dev/null

for _ in $(seq 1 60); do
    if docker exec "$container_name" pg_isready -U restore_drill -d cistafirma_restore_drill >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! docker exec "$container_name" pg_isready -U restore_drill -d cistafirma_restore_drill >/dev/null 2>&1; then
    echo "ERROR: isolated restore database did not become ready." >&2
    docker logs "$container_name" --tail 100 >&2 || true
    exit 1
fi

docker cp "$drill_input" "$container_name:/tmp/input.dump"
docker exec "$container_name" sh -c \
    'exec pg_restore --clean --if-exists --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" /tmp/input.dump'

table_count=$(docker exec "$container_name" psql -U restore_drill -d cistafirma_restore_drill -Atc \
    "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';")

if [ "$table_count" -eq 0 ]; then
    echo "ERROR: restore drill completed without public tables." >&2
    exit 1
fi

# Record the drill. docs/DATA_PROTECTION.md requires a drill "at least monthly",
# but nothing recorded when one last succeeded, so the control could not be
# verified -- only assumed. One JSON object per line; `make db-offsite-status`
# reads the last entry back. A *failed* drill writes nothing: the absence of a
# recent record is itself the signal, so an old record cannot mask a failure.
DEFAULT_DRILL_LOG="$(state_dir)/restore_drills.log"
DRILL_LOG="${CISTAFIRMA_DRILL_LOG:-$DEFAULT_DRILL_LOG}"

drill_source="local"
# The question is whether the dump came from the external copy, and it needs the
# destination to be really attached first: on Linux an armed systemd automount
# keeps the directory present while its target is unreachable, and a `cd` into
# it fails with ENODEV. The reference for "different filesystem" is $HOME rather
# than the dump's own directory, because when the drill runs from the off-site
# copy that directory *is* the off-site one -- comparing it with itself would
# call a correctly attached volume part of this machine.
if [ -n "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" ] &&
    cistafirma_offsite_mount_check "$CISTAFIRMA_OFFSITE_BACKUP_DIR" "$HOME"; then
    if [ "$(cd "$(dirname "$BACKUP_FILE")" && pwd -P)" = "$(cd "$CISTAFIRMA_OFFSITE_BACKUP_DIR" && pwd -P)" ]; then
        drill_source="off-site"
    fi
fi

drill_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["sha256"])' \
    "${BACKUP_FILE}.json" 2>/dev/null || true)

# Recorded because the two drills prove different things. Restoring a local
# plaintext dump proves the backup is readable; restoring a `.gpg` replica proves
# that *and* that the private key is still in hand. A report that could not tell
# them apart would let a run of local drills look like the off-site path had been
# exercised when it never had.
drill_encrypted=false
case "$BACKUP_FILE" in
    *.gpg) drill_encrypted=true ;;
esac

umask 077
mkdir -p "$(dirname "$DRILL_LOG")"
python3 - "$DRILL_LOG" "$BACKUP_FILE" "${drill_sha:-}" "$table_count" "$drill_source" "$drill_encrypted" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

log_path, backup_file, sha, tables, source, encrypted = sys.argv[1:7]
record = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "backup": Path(backup_file).name,
    "sha256": sha,
    "public_tables": int(tables),
    "source": source,
    "encrypted": encrypted == "true",
}
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
PY

if [ "$drill_encrypted" = true ]; then
    echo "Restore drill passed: $table_count public tables restored from an ENCRYPTED replica into an isolated container."
    echo "The private key is present and usable on this machine — that is what made this drill possible."
else
    echo "Restore drill passed: $table_count public tables restored into isolated container."
fi
echo "Recorded in: $DRILL_LOG (source: $drill_source)"
