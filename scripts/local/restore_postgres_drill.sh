#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump" >&2
    exit 64
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
BACKUP_FILE=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: backup file does not exist: $BACKUP_FILE" >&2
    exit 1
fi

"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$BACKUP_FILE"

container_name="cistafirma_restore_drill_$(date -u +%Y%m%dT%H%M%SZ)_$$"
drill_password=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
cleanup() {
    docker rm -f "$container_name" >/dev/null 2>&1 || true
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

docker cp "$BACKUP_FILE" "$container_name:/tmp/input.dump"
docker exec "$container_name" sh -c \
    'exec pg_restore --clean --if-exists --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" /tmp/input.dump'

table_count=$(docker exec "$container_name" psql -U restore_drill -d cistafirma_restore_drill -Atc \
    "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';")

if [ "$table_count" -eq 0 ]; then
    echo "ERROR: restore drill completed without public tables." >&2
    exit 1
fi

echo "Restore drill passed: $table_count public tables restored into isolated container."
