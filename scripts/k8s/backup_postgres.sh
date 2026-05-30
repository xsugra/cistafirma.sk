#!/usr/bin/env sh
set -eu

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"

BACKUP_DIR=${BACKUP_DIR:-./backups}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

# Use a temporary .pgpass file instead of PGPASSWORD env var
# to avoid exposing the password in the process environment.
PGPASSFILE=$(mktemp)
chmod 600 "$PGPASSFILE"
printf '%s:%s:%s:%s:%s\n' "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER" "$DB_PASSWORD" > "$PGPASSFILE"
trap 'rm -f "$PGPASSFILE"' EXIT

export PGPASSFILE
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  --file "$BACKUP_FILE"

echo "Backup created: $BACKUP_FILE"
