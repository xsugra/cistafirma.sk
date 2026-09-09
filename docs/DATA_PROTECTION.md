# Data Protection and Recovery

The Docker PostgreSQL volume `cistafirma_postgres_data` contains durable company
data. Treat it as production data: it must never be removed, reinitialized, or
restored over without a separately verified backup and an approved maintenance
procedure.

## Non-negotiable rules

- Never run `make docker-reset`, `docker compose down -v`, `docker volume rm`, or
  `docker volume prune` against this project.
- Never run `make celery-purge`, a full RUZ resync, or a database restore as a
  routine troubleshooting action. `make celery-purge` requires the explicit
  `CONFIRM_CELERY_PURGE=DELETE_PENDING_MESSAGES` token because queued work is
  permanently lost.
- Never restore over the running `cistafirma` database. Restore drills and data
  investigations use an isolated target.
- Backups are stored outside the repository and outside Docker volumes. They are
  intentionally excluded from Git.
- This local copy protects against application and Docker-volume mistakes. It
  does not protect against loss of the computer; an encrypted off-host replica
  is required before relying on it as the only recovery mechanism.

## Local backup procedure

The default backup directory on macOS is:

```text
$HOME/Library/Application Support/CistaFirma/backups
```

Set `CISTAFIRMA_BACKUP_DIR` to use another absolute directory outside the
repository. The scripts fail closed if the directory resolves inside this
repository.

```bash
make db-backup
make db-backup-verify BACKUP_FILE="/absolute/path/to/cistafirma_YYYYMMDDTHHMMSSZ.dump"
```

Each backup is a PostgreSQL custom archive with a same-name JSON manifest
containing its SHA-256 checksum and size. The verifier checks the checksum and
uses the pinned `postgres:16-alpine` image to read the archive directory without
starting a database or changing source data.

## External encrypted replica

The second copy must be stored on an encrypted external macOS volume. The
replication command requires an existing target directory, verifies it is on a
different filesystem than the local backup, and refuses volumes that do not
report encryption through `diskutil`. It never creates a fallback copy on the
internal disk.

After connecting and unlocking the external disk:

```bash
export CISTAFIRMA_OFFSITE_BACKUP_DIR="/Verbatim/cistafirmaBackups"
make db-backup-replicate BACKUP_FILE="/absolute/path/to/cistafirma_YYYYMMDDTHHMMSSZ.dump"
```

The copied archive and manifest are checksum-verified after transfer. Keep the
disk disconnected except while making or testing a replica. Perform an isolated
restore drill from the external copy at least monthly.

### Temporary unencrypted-volume exception

An unencrypted external volume is not an acceptable long-term backup target.
Only when explicitly approved for temporary use may the copy proceed with:

```bash
export CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true
```

This exception is logged to stderr by the replication script and must be removed
after the external volume is encrypted. Treat the unencrypted disk as containing
confidential company data: keep it physically secured and disconnected when not
performing backup or recovery work.

## Isolated restore drill

Run a drill after every initial backup and at least monthly:

```bash
make db-restore-drill BACKUP_FILE="/absolute/path/to/cistafirma_YYYYMMDDTHHMMSSZ.dump"
```

The drill first verifies the archive, restores it into a temporary PostgreSQL
container named `cistafirma_restore_drill_*`, confirms public tables exist, and
removes only that temporary container. It never connects to, stops, writes to,
or removes the running Compose database or its named volume.

## Recovery incident procedure

1. Stop all data-changing operations and preserve the failed environment for
   investigation.
2. Identify a verified backup and record its filename, SHA-256 manifest, and
   creation time.
3. Restore it first into an isolated database and have the owner validate record
   counts and critical company samples.
4. Obtain explicit approval for any production-target restore. Take a fresh
   pre-restore backup, enable maintenance mode, and document the rollback
   decision.
5. Run application and data-integrity checks after recovery; do not resume
   Celery ingestion until the result is accepted.

## Remaining required control

Configure an encrypted off-host replication destination and test retrieval from
another machine or storage failure domain. Until then, the local backup is an
important first layer, not a complete disaster-recovery solution.
