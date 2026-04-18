#!/usr/bin/env sh
set -eu

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: backup file not found: $BACKUP_FILE"
  exit 1
fi

export PGPASSWORD="$DB_PASSWORD"
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  "$BACKUP_FILE"
unset PGPASSWORD

echo "Restore completed from: $BACKUP_FILE"

