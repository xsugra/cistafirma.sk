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

### Retention, status and schedule

```bash
make db-backup-prune                       # dry run: list what would be deleted
make db-backup-prune PRUNE_ARGS="--apply"  # keep the newest 7, delete older
make db-offsite-status                     # read-only readiness report
make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="<dir>"  # record the volume
make db-backup-schedule-install            # weekly launchd job (Sunday 03:17)
make db-backup-schedule-status
make db-backup-schedule-uninstall
```

`db-backup-prune` never deletes the newest backup, only touches files inside the
backup directory, and refuses a directory inside this repository. Add
`PRUNE_ARGS="--apply --offsite"` to mirror the same retention onto the off-site
volume. `db-offsite-status` writes nothing and exits non-zero when a required
control is unmet, so it is safe as a gate anywhere (CI included).

### Where the off-site path is recorded

The off-site path is machine-specific, so it must not live in the repository —
yet the weekly launchd job needs it, and launchd starts agents with an almost
empty environment. `make db-offsite-configure` therefore writes it once to a
machine-local file:

```
~/.config/cistafirma/backup.env      # chmod 600, never committed
```

```bash
make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="/Volumes/<disk>/cistafirmaBackups"
```

Every backup script sources `scripts/local/lib/backup_env.sh`, which reads that
file. Precedence is: **an already-exported variable wins**, so one-off overrides
still work (`make db-offsite-status CISTAFIRMA_OFFSITE_BACKUP_DIR=/tmp/x`), and
the same file can carry other `CISTAFIRMA_*` settings — in particular the
temporary unencrypted-volume exception below. Only `CISTAFIRMA_*` keys are ever
set, so a stray line cannot inject an unrelated variable. `db-offsite-configure`
updates the file in place; other keys already in it are preserved.

The launchd job runs `scripts/local/scheduled_backup.sh` — backup, verify, and
replicate when the off-site volume is mounted — and logs to
`~/Library/Logs/CistaFirma/backup.out.log`. When it makes no replica it says so
explicitly and distinguishes *not configured* from *configured but not mounted*,
because the two need different fixes and used to be reported identically.

## External encrypted replica

The second copy must be stored on an encrypted external macOS volume. The
replication command requires an existing target directory, verifies it is on a
different filesystem than the local backup, and refuses volumes that do not
report encryption through `diskutil`. It never creates a fallback copy on the
internal disk.

Record the destination once with `make db-offsite-configure` (see *Where the
off-site path is recorded*), then after connecting and unlocking the external
disk:

```bash
make db-backup-replicate BACKUP_FILE="/absolute/path/to/cistafirma_YYYYMMDDTHHMMSSZ.dump"
```

Passing `CISTAFIRMA_OFFSITE_BACKUP_DIR="<dir>"` on the command line still works
and overrides the recorded value for that one run.

The copied archive and manifest are checksum-verified after transfer. Keep the
disk disconnected except while making or testing a replica. Perform an isolated
restore drill from the external copy at least monthly.

### Temporary unencrypted-volume exception

An unencrypted external volume is not an acceptable long-term backup target.
Only when explicitly approved for temporary use may the copy proceed with:

```bash
make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="/Volumes/<disk>/cistafirmaBackups" \
    CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true
```

(or `export CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true` for a single
interactive run). Set it through the config file, not only an export, whenever
the **weekly job** must keep working — launchd inherits almost no environment,
so an `export` in a terminal never reaches it.

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

Every successful drill appends one JSON object to a drill log:

```text
$HOME/Library/Application Support/CistaFirma/restore_drills.log   # mode 600
```

```json
{"timestamp": "2026-09-10T10:03:39+00:00", "backup": "cistafirma_20260908T174923Z.dump",
 "sha256": "7bcb5275…", "public_tables": 38, "source": "off-site"}
```

`make db-offsite-status` reads the last entry back, so "at least monthly" is an
enforced control instead of an intention. It **fails** when no drill is
recorded, when the recorded timestamp is unreadable, or when the last drill is
older than `CISTAFIRMA_DRILL_MAX_AGE_DAYS` (default 30), and it warns when the
last drill used the local dump while an off-site copy exists. A *failed* drill
writes nothing — the absence of a recent record is itself the signal, so an old
entry cannot mask a broken one, and an unparseable trailing line falls back to
the previous readable record rather than being trusted. Set `CISTAFIRMA_DRILL_LOG`
to record somewhere else.

## Operational gate and failure alerting

`make ops-check` answers one question in one command: is everything this
document depends on actually working? It covers the stack, the database, Celery
queue depths, the local backup and its checksum, every off-site control, the
drill record, and whether the weekly job is still firing. It is read-only — it
starts no container and writes nothing — so it is safe to run at any time, and
it exits non-zero when a control is unmet.

The weekly job runs the same gate as its last step. On any failure it writes
`~/Library/Logs/CistaFirma/LAST_FAILURE`, posts a macOS notification, and exits
non-zero so launchd records it too. The marker is cleared only by a fully
successful run, so a later partial success cannot silently forgive an earlier
failure.

Two deliberate asymmetries keep that alert trustworthy:

- **A disconnected volume is not a failure there.** This document says to keep
  the external disk disconnected except while replicating, so the unattended run
  treats "not mounted" as a warning — an alert that reddens every week for a
  documented posture is an alert everyone learns to ignore. `make ops-check` and
  `make db-offsite-status` keep the strict reading: when you ask by hand, you
  want the truth rather than the policy.
- **launchd's own run counter is the only proof the job has ever fired.** The
  log cannot distinguish an unattended run from a manual one, so the gate reads
  `launchctl print … runs`. A job launchd has never launched cannot be reported
  as "ran recently" merely because someone ran the script by hand.

### Off-site replica record

`make db-backup-replicate` appends a record to

```text
$HOME/Library/Application Support/CistaFirma/replicas.log   # mode 600
```

once the copy has been checksum-verified. The staleness control reads *that
record* rather than the replica files, because the disk is normally
disconnected — its mtimes are unavailable exactly when the question "has it been
attached lately?" matters most. No recorded replica within
`CISTAFIRMA_REPLICA_MAX_AGE_DAYS` (default 14) fails the gate, and no record at
all fails it immediately: that means no off-site protection exists yet.

### Celery queue depth

The gate prints the depth of every queue, because nothing else in the stack
exposes it — a queue that has silently stopped draining looks exactly like one
that is merely busy. A large backlog is not by itself a failure (the insurance
queue is deliberately rate-limited and is normally saturated), so it only warns,
above `CISTAFIRMA_QUEUE_WARN_DEPTH` (default 50000).

### Source health

Depth measures load; it cannot measure outcome, and the two are not substitutes.
A queue can drain at exactly its configured rate forever against a source that
has stopped producing usable answers. That is not hypothetical: on 2026-09-10 the
VSZP scraper was found to have been returning `unknown` for **every** company
for at least a day — 17 969 attempts, zero successes — so no check ever completed,
every one of the 441 714 companies stayed due for re-check, and the insurance
queue held a steady, healthy-looking 30 000 messages throughout. The queue
section above reported it as `OK` the whole time.

`make ops-check` therefore also chains
`python manage.py source_health` (`backend/registers/management/commands/`),
which owns what "a source is healthy" means. It reports, per source and over a
window, how many companies were attempted and how many succeeded, and it fails
when a source with at least `CISTAFIRMA_SOURCE_MIN_ATTEMPTS` attempts (default
200) succeeded for **no one** within `CISTAFIRMA_SOURCE_WINDOW_HOURS` (default
24).

The failing condition is deliberately zero rather than a low rate: a low rate is
normal — only a few percent of companies owe the Socialná poisťovňa anything —
while zero means the parser no longer matches the page. A source with too few
attempts to judge is reported as *not judged* rather than as healthy, so silence
is never mistaken for a pass.

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

## Objectives (RPO / RTO) and ownership

- **Owner:** repository maintainer (Samuel Šugra). Backup creation, verification
  and drills are the owner's responsibility; AI agents and contributors must not
  bypass these controls.
- **RPO (Recovery Point Objective):** with the weekly launchd job installed, RPO
  is at most 7 days. Run `make db-backup` before any schema/data-changing work
  and after each meaningful sync milestone for a tighter point. Until a verified
  off-host replica exists, treat RPO as unbounded across hardware loss.
- **RTO (Recovery Time Objective):** an isolated restore drill restores 38+
  tables in roughly a minute. A production-target restore additionally requires
  a pre-restore backup, maintenance mode and post-restore integrity checks, so
  plan for tens of minutes, not seconds.
- **Minimum cadence:** a fresh verified backup before any migration or data
  change; a verified backup at least weekly; an isolated restore drill after
  each initial backup and at least monthly (from the external copy when it
  exists).

## Off-site setup runbook (required control)

An off-host replica is the only protection against loss of this computer. The
replication tooling already exists and fails closed; what is required is the
encrypted destination plus one verified retrieval.

1. Connect an external disk and encrypt its volume. On an **empty** disk, erase
   it as **APFS (Encrypted)** in Disk Utility. On a disk that already holds
   data — including one that already holds a replica — do **not** erase it;
   encrypt it in place instead (non-destructive, runs in the background, and
   the disk must stay connected until it finishes):

   ```bash
   diskutil apfs encryptVolume <apfsVolumeDisk> -user disk
   ```

   Either way the replication script refuses volumes that do not report
   encryption through `diskutil`. Save the passphrase in a password manager.
2. Create the target directory and record it on this machine:

   ```bash
   mkdir -p "/Volumes/<disk>/cistafirmaBackups"
   make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="/Volumes/<disk>/cistafirmaBackups"
   ```

3. Make and replicate a verified backup:

   ```bash
   make db-backup
   make db-backup-replicate BACKUP_FILE="/absolute/path/to/cistafirma_YYYYMMDDTHHMMSSZ.dump"
   make db-offsite-status   # must print: Off-site backup controls: SATISFIED
   ```

4. Install the weekly schedule so this repeats unattended. Do this *after*
   step 2 — the job reads the recorded path from `~/.config/cistafirma/backup.env`,
   and it cannot see an `export` from your shell:

   ```bash
   make db-backup-schedule-install
   make db-backup-schedule-status
   ```

   Afterwards, check the first unattended run in
   `~/Library/Logs/CistaFirma/backup.out.log`: it must report either
   `off-site volume detected; replicating` or an explicit warning naming what is
   missing. It must **not** be silent about the replica.

5. At least monthly, restore the newest off-site dump **from a different
   machine** (or after a simulated disk loss) with `make db-restore-drill`,
   proving retrieval from a second failure domain.

Until step 3 has produced a verified replica, the local backup is an important
first layer — not a complete disaster-recovery solution.
