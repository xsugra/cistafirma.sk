#!/usr/bin/env bash
set -Eeuo pipefail

# Only the platform primitives, not lib/backup_env.sh: this script reads no
# CISTAFIRMA_* setting, and reading the machine-local config here would give it
# a dependency on a file it has never needed.
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump" >&2
    exit 64
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: backup file does not exist or is empty: $BACKUP_FILE" >&2
    exit 1
fi

METADATA_FILE="${BACKUP_FILE}.json"
if [ ! -f "$METADATA_FILE" ]; then
    echo "ERROR: backup metadata is missing: $METADATA_FILE" >&2
    exit 1
fi

expected_checksum=$(python3 - "$METADATA_FILE" <<'PY'
import json
import sys
from pathlib import Path

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(metadata["sha256"])
PY
)
actual_checksum=$(sha256_of "$BACKUP_FILE")

if [ "$expected_checksum" != "$actual_checksum" ]; then
    echo "ERROR: checksum verification failed." >&2
    exit 1
fi

docker image inspect postgres:16-alpine >/dev/null
docker run --rm --pull=never \
    --mount "type=bind,source=$(cd "$(dirname "$BACKUP_FILE")" && pwd -P)/$(basename "$BACKUP_FILE"),target=/backup/input.dump,readonly" \
    postgres:16-alpine \
    pg_restore --list /backup/input.dump >/dev/null

echo "Backup verified: $BACKUP_FILE"
