#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"

DEFAULT_BACKUP_DIR="$(state_dir)/backups"
BACKUP_DIR="${CISTAFIRMA_BACKUP_DIR:-$DEFAULT_BACKUP_DIR}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
BACKUP_DIR=$(cd "$BACKUP_DIR" && pwd -P)

case "$BACKUP_DIR" in
    "$ROOT_DIR"|"$ROOT_DIR"/*)
        echo "ERROR: CISTAFIRMA_BACKUP_DIR must be outside the repository." >&2
        exit 1
        ;;
esac

cd "$ROOT_DIR"
docker compose config --quiet

if [ "$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' cistafirma_db)" != "running healthy" ]; then
    echo "ERROR: cistafirma_db must be running and healthy before backup." >&2
    exit 1
fi

timestamp=$(date -u +"%Y%m%dT%H%M%SZ")
backup_file="$BACKUP_DIR/cistafirma_${timestamp}.dump"
temporary_file=$(mktemp "$BACKUP_DIR/.cistafirma_${timestamp}.XXXXXX")
trap 'rm -f "$temporary_file"' EXIT

umask 077
docker compose exec -T db sh -c \
    'exec pg_dump --format=custom --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
    > "$temporary_file"

if [ ! -s "$temporary_file" ]; then
    echo "ERROR: PostgreSQL backup is empty." >&2
    exit 1
fi

mv "$temporary_file" "$backup_file"
trap - EXIT
chmod 600 "$backup_file"

checksum=$(sha256_of "$backup_file")
metadata_file="${backup_file}.json"

python3 - "$backup_file" "$checksum" "$metadata_file" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

backup_file = Path(sys.argv[1])
checksum = sys.argv[2]
metadata_file = Path(sys.argv[3])

metadata = {
    "format": "postgresql-custom",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "filename": backup_file.name,
    "sha256": checksum,
    "size_bytes": backup_file.stat().st_size,
}
metadata_file.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
os.chmod(metadata_file, 0o600)
PY

echo "Backup created: $backup_file"
echo "Metadata created: $metadata_file"
