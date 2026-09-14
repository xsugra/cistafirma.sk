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

The default backup directory is platform-specific — a backup directory nobody
can find is only marginally better than no backup directory:

```text
macOS : $HOME/Library/Application Support/CistaFirma/backups
Linux : $HOME/.local/state/CistaFirma/backups
```

Both honour `XDG_STATE_HOME`. Everything that differs between the two platforms
— state and log directories, the checksum tool, the `stat` flavour, the
scheduler's units — is resolved in exactly one place,
`scripts/local/lib/backup_os.sh`, so a port cannot quietly grow a second opinion
about which platform it is on. Set `CISTAFIRMA_BACKUP_DIR` to use another
absolute directory outside the repository. The scripts fail closed if the
directory resolves inside this repository.

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
make db-backup-schedule-install            # weekly job, Sunday 03:17
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
yet the weekly job needs it, and a scheduler starts a job with an almost empty
environment (launchd agents on macOS, systemd user units on Linux, which get only
the `PATH` the installer writes into the unit). `make db-offsite-configure`
therefore writes it once to a machine-local file:

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

The weekly job runs `scripts/local/scheduled_backup.sh` — backup, verify, and
replicate when the off-site destination is really attached — and logs to:

```text
macOS : $HOME/Library/Logs/CistaFirma/backup.out.log
Linux : $HOME/.local/state/CistaFirma/logs/backup.out.log   (plus the journal)
```

When it makes no replica it says so explicitly and distinguishes *not configured*
from *configured but not mounted*, because the two need different fixes and used
to be reported identically.

The schedule itself is a launchd LaunchAgent on macOS and a systemd **user**
timer plus service on Linux, generated from the templates in
`scripts/local/launchd/` and `scripts/local/systemd/` into
`~/Library/LaunchAgents` and `~/.config/systemd/user`. Both run as the invoking
user (not root), weekly on Sunday at 03:17 local time; the systemd timer sets
`Persistent=true`, so a run missed while the machine was off happens after the
next boot rather than being skipped. Because the job needs `docker compose`, the
user must be able to run `docker` — on Linux that normally means membership in
the `docker` group, and `make db-backup-schedule-install` checks it (by asking
`docker info`, not by reading `id`) and refuses to install a job that could not
work. A user timer only runs while the user has a session: on a headless server
run `sudo loginctl enable-linger <user>` once, which the installer prints but
does not do, since it changes machine-wide login state rather than this
repository.

## External encrypted replica

The second copy must be stored on an encrypted volume that is a separate
filesystem from the local backup. On macOS that is an encrypted external volume;
on Linux it is a LUKS/dm-crypt filesystem — on a local block device, or on the
remote host behind an sshfs mount. The replication command requires a destination
that is really attached, verifies it is on a different filesystem than the local
backup, and refuses a destination whose encryption it cannot establish. It never
creates a fallback copy on the internal disk.

### The destination must really be attached

"The off-site directory exists" is not the question, and on Linux it is not even
a clue. When the destination is a **systemd automount** (`x-systemd.automount` in
fstab, the usual way to mount an sshfs target) and its target is unreachable —
a tailnet that is down, a server that is off — the measured state is:

```text
[ -d /mnt/cistafirma-offsite ]        -> TRUE      (says nothing)
mountpoint -q /mnt/cistafirma-offsite -> MOUNTED   (wrong)
findmnt -M /mnt/cistafirma-offsite    -> MOUNTED   (wrong, same reason)
stat -c '%d' /mnt/cistafirma-offsite  -> ENODEV    ("No such device")
df -P /mnt/cistafirma-offsite         -> ENODEV
the mount unit                        -> Active: failed
```

`mountpoint` and `findmnt` are wrong here because an *armed* automount keeps a
mount-info entry for the trigger itself for as long as the unit is armed, whether
or not the filesystem behind it ever came up. A destination that is not attached
but whose path exists is a plain directory on this machine's own disk, so a
"replica" written there sits on the same disk as the original — a second copy in
name only, which is worse than none because it is believed.

Every script therefore asks `cistafirma_offsite_mount_check` in
`scripts/local/lib/backup_os.sh` instead of testing the path, and that check
performs a real filesystem operation and judges its outcome: the path must exist,
`stat` on it must succeed, and its device id must differ from the local backup
directory's. Any failure — ENODEV, a stalled sshfs, a permission problem, an
unreadable reference — is reported as **not attached**, never as "probably fine".
A path that exists on this machine's own disk gets its own verdict
(`same-filesystem`) so the operator is told to fix the configuration rather than
the cabling. `df -P` is deliberately not part of this test: it reaches into the
filesystem, which is exactly what is unreachable in the case above, so it stays a
later check with its own error rather than the proof.

The same test guards the destructive path: `make db-backup-prune
PRUNE_ARGS="--apply --offsite"` refuses to prune a destination that is not really
attached, because the failure that matters there is not a failed deletion but a
successful one in the wrong place.

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

### What counts as encrypted, per platform

The verdict lives in one place, `scripts/local/lib/offsite_crypto.sh`, so the
script that copies a dump and the report that checks it can never disagree. Three
cases, and three verdicts (`encrypted`, `unencrypted`, `unknown`):

- **macOS, any destination** — `diskutil info <mount point>` must report
  FileVault or an encrypted volume. This is the check that has always run.
- **Linux, local volume** — the filesystem's source must show a dm-crypt/LUKS
  layer, checked with `cryptsetup status` and by walking the device stack with
  `lsblk -s -no TYPE,FSTYPE`. A disk with no LUKS layer, like an ext4 partition
  on the bare device, is `unencrypted`.
- **Linux, FUSE/sshfs** — the bytes are on the far side, so encryption cannot be
  checked locally at all: it is checked on the **remote host over SSH**
  (`findmnt`, `lsblk`, `cryptsetup`, with `BatchMode=yes` and a bounded connect
  timeout). The remote is derived from the mount source, or from
  `CISTAFIRMA_OFFSITE_SSH_TARGET=user@host:/path` when it cannot be.
- **Anything else** — `unknown`, including a FUSE mount whose remote check could
  not answer. `unknown` **fails exactly like `unencrypted`**; it is not a milder
  verdict, it is the same failure with the uncomfortable detail that nobody
  actually looked.

### Temporary unencrypted-volume exception

An unencrypted external volume is not an acceptable long-term backup target.
Only when explicitly approved for temporary use may the copy proceed with:

```bash
make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="/Volumes/<disk>/cistafirmaBackups" \
    CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true
```

(or `export CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true` for a single
interactive run). Set it through the config file, not only an export, whenever
the **weekly job** must keep working — a scheduler starts a job with almost no
environment, so an `export` in a terminal never reaches it.

The token is the one control whose meaning did not change in the port, and it
must not be widened: it accepts a destination whose encryption was **not
established**, it never makes an unencrypted destination count as encrypted. On
Linux it is currently the only way the off-site gate can pass at all, because the
known target host has no LUKS container — a destination that is honestly
unencrypted is *supposed* to fail this gate.

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
macOS : $HOME/Library/Application Support/CistaFirma/restore_drills.log
Linux : $HOME/.local/state/CistaFirma/restore_drills.log
```

(mode 600 on both).

```json
{"timestamp": "2026-09-10T10:03:39+00:00", "backup": "cistafirma_20260908T174923Z.dump",
 "sha256": "7bcb5275…", "public_tables": 38, "source": "off-site"}
```

`make db-offsite-status` reads the last entry back, so "at least monthly" is an
enforced control instead of an intention. It **fails** when no drill is
recorded, when the recorded timestamp is unreadable, or when the last drill is
older than `CISTAFIRMA_DRILL_MAX_AGE_DAYS` (default 30), and it warns when the
last drill used the local dump while an off-site copy exists — where "exists"
again means *really attached*, since an unreachable destination has no off-site
copy to drill. A *failed* drill
writes nothing — the absence of a recent record is itself the signal, so an old
entry cannot mask a broken one, and an unparseable trailing line falls back to
the previous readable record rather than being trusted. Set `CISTAFIRMA_DRILL_LOG`
to record somewhere else.

## Operational gate and failure alerting

`make ops-check` answers one question in one command: is everything this
document depends on actually working? It covers the stack, the database, Celery
queue depths, active sync jobs, the local backup and its checksum, every
off-site control, the drill record, and whether the weekly job is still firing.
It is read-only — it
starts no container and writes nothing — so it is safe to run at any time, and it
exits non-zero when a control is unmet.

The weekly job runs the same gate as its last step. On any failure it writes
`LAST_FAILURE` in the platform's log directory (`~/Library/Logs/CistaFirma` on
macOS, `~/.local/state/CistaFirma/logs` on Linux), posts a desktop notification
where one can be shown (`osascript` on macOS, `notify-send` on Linux, both
best-effort), and exits non-zero so the scheduler records it too. The marker is
cleared only by a fully successful run, so a later partial success cannot
silently forgive an earlier failure.

Two deliberate asymmetries keep that alert trustworthy:

- **A disconnected volume is not a failure there.** This document says to keep
  the external disk disconnected except while replicating, so the unattended run
  treats "not mounted" as a warning — an alert that reddens every week for a
  documented posture is an alert everyone learns to ignore. `make ops-check` and
  `make db-offsite-status` keep the strict reading: when you ask by hand, you
  want the truth rather than the policy.
- **The scheduler's own run counter is the only proof the job has ever fired.**
  The log cannot distinguish an unattended run from a manual one, so the gate
  reads `launchctl print … runs` on macOS and the timer's own last-trigger stamp
  (`systemctl --user show -p LastTriggerUSec…`) on Linux. A job the scheduler has
  never launched cannot be reported as "ran recently" merely because someone ran
  the script by hand — and on systemd the *timer's* stamp is what is read, since
  starting the service by hand leaves it untouched.

The gate does not read the off-site report's prose. `offsite_status.sh` publishes
two summary lines of its own — `Off-site backup controls: N unmet` and
`Off-site backup warnings: N` — and `ops_check.sh` parses those, failing closed if
either is unreadable. The warning count used to be derived by grepping that
script's output for `^WARN  `, which held only as long as both scripts' `warn()`
helpers kept printing exactly two spaces: a one-character edit in either file
would have made every off-site warning disappear from the total while the gate
still reported SATISFIED. A count that can silently under-report is worse than no
count, because it is believed. The same rule covers the other chained scripts,
whose own summary lines are the entire contract between them and this gate.

### Known risk: an unresponsive volume stalls the gate, it does not fail it

Nothing under `scripts/local` uses `timeout`. The off-site controls read the
external volume through unguarded I/O — `offsite_status.sh` does `cd` and
`pwd -P`, a device-id `stat` (twice, and once more inside the attachment check),
`df -P`, `diskutil info` or `cryptsetup`/`lsblk`/`ssh`, and a checksum read of
the replica — and both callers wrap that script in a bare command substitution
(`ops_check.sh`, `scheduled_backup.sh`).

So the controls can distinguish only two of the three states a backup target can
be in:

- **absent** — handled, deliberately: the staleness and drill controls read
  local records precisely because the disk is normally disconnected;
- **present and healthy** — handled;
- **present and not answering** — not handled. This is what an intermittently
  stalling USB volume produces, and an sshfs mount whose server has gone quiet
  produces the same thing over the network.

A mounted volume that stops responding blocks those calls for an unbounded
time. Nothing in that path imposes an upper bound, and that absence — not any
observed hang — is what the fix has to restore: the stalls seen on this disk so
far have all returned, some only after minutes, and nothing here guarantees the
next one will. While the gate is blocked it does not return, so
`scheduled_backup.sh` never reaches its `exit`, its `EXIT` trap never fires, and
neither `LAST_FAILURE` nor the desktop notification is
written. **The alarm goes silent in exactly the condition it exists to detect**,
and a run that is hung is indistinguishable from a run that is still working.

The port adds one more call to that list rather than removing any: the attachment
check `stat`s the destination, and a `stat` on a stalled sshfs mount blocks like
everything else there. It is still worth stating why the check is a `stat` and
not a mount-table read: the mount table answers *instantly* and answers **wrong**
for an armed-but-unreachable automount, which is a state that occurs every time
the network is down, where a stall needs a failing disk. A wrong answer that
happens daily is worse than a hang that happens rarely.

Recorded as a known risk on 2026-09-10 and deliberately left unfixed: adding a
bounded wait to every external-device call changes how the whole gate reports,
and that was judged out of scope for the increment that found it. The fix, when
it is taken up, is a bounded wait around each of those calls with the timeout
treated as a **failure** — never as a skip, which would turn a missing answer
into a passing control.

Two properties are needed, and only the first is obvious. The bound must give
the *caller* a verdict even when the blocked process cannot be reaped: a process
parked in an uninterruptible I/O wait ignores SIGTERM and SIGKILL alike, so a
watchdog that backgrounds the call and kills it will report "timed out" while
leaving the real process parked — the gate returns, but every stall leaks a
process against a job the scheduler will not re-run. If the mechanism cannot
promise
the caller a verdict regardless of whether the stuck process dies, it is the
wrong mechanism.

Until then detection is manual: a hung run writes no failure marker *and* no
success line, so read the tail of the run log and the scheduler's own run counter
(`launchctl print … runs`, or the systemd timer's last-trigger stamp), not the
marker alone.

### Off-site replica record

`make db-backup-replicate` appends a record to

```text
macOS : $HOME/Library/Application Support/CistaFirma/replicas.log
Linux : $HOME/.local/state/CistaFirma/replicas.log
```

(mode 600 on both)

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
queue is deliberately rate-limited and is normally saturated), so it only warns.

The bound is per queue, because the queues are not the same shape.
`celery`, `ruz_full`, `orsr` and `financials` drain to zero and warn above
`CISTAFIRMA_QUEUE_WARN_DEPTH` (default 50000). `insurance` warns above
`CISTAFIRMA_QUEUE_WARN_DEPTH_INSURANCE` (default 144000) instead: its dispatcher
is capped at 14 400 messages per 12 h tick — exactly what the 20/m worker drains
in the same window — so arrivals equal drain capacity, the depth is *conserved*
rather than drained, and it sawtooths by one batch around whatever it inherited
(measured 2026-09-13: ~54 000 before a dispatch, ~68 000 just after). Judged
against the flat 50000 it warned permanently about a queue behaving as designed,
which is how a gate teaches its reader to ignore it. 144000 is ten ticks, i.e.
five days of drain capacity: about twice that sawtooth's peak, and far below the
2026-09 flood of 8.4 M messages in a day.

An explicit `CISTAFIRMA_QUEUE_WARN_DEPTH` still applies to every queue,
`insurance` included; the per-queue variable is the more specific override and
wins for its own queue. Whatever the bound, it judges load only — depth has never
been able to say whether the work *achieves* anything, and Source health below is
what answers that.

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
window, how many companies were attempted, how many succeeded, and — for
sources whose answer carries an amount — how those successes split between a
reported debt and a reported absence.

A check carries only two useful answers, so a source is unmet when it loses
either one. With at least `CISTAFIRMA_SOURCE_MIN_ATTEMPTS` attempts (default
200) and `CISTAFIRMA_SOURCE_MIN_SUCCESSES` successes (default 20) inside
`CISTAFIRMA_SOURCE_WINDOW_HOURS` (default 24), that means:

- nothing succeeded at all — the parser recognises nothing;
- nothing reported a debt — every real debtor would be written as debt-free;
- nothing reported an absence — a company that owes nothing can never be marked
  checked, so it stays due for ever.

The last case is why a zero-success rule is not enough on its own. The Socialná
poisťovňa scraper was found on 2026-09-10 with 605 successes in the window and
**not one** of them an absence: it found every debtor and misread every
non-debtor as `unknown`, so most of the table stayed due and the `insurance`
queue held 30 000 messages while draining at exactly its configured rate. A
zero-success rule called that healthy.

The thresholds are counts rather than rates because only a few percent of
companies owe the Socialná poisťovňa anything: a low rate is normal, and a rate
threshold would have to be tuned per source and would drift. A source with too
few attempts, or too few successes for its split to mean anything, is reported
as *not judged* rather than as healthy, so silence is never mistaken for a pass.

The table is built from `CompanySyncStatus.SOURCE_CHOICES` — the declared
vocabulary — and not from the rows that happen to exist, so **every** source
gets a line. It used to iterate `values("source")`, which meant a source with no
rows produced no line at all: measured 2026-09-11, the gate listed `financials`,
`social` and `vszp` and said nothing whatsoever about `ruz`, `orsr` or `fs`. A
missing line reads exactly like a source that was checked and found healthy.

Silence is judged per source rather than uniformly, because it does not mean the
same thing everywhere. `orsr` and `financials` draw from due-lists that are
never empty, so attempting nothing fails them. `ruz` records only the companies
the registry reported as *changed*, so a quiet window is a reading, not a
failure — the reason is printed beside it. `vszp` and `social` are excused
*only while Focus Mode is active*, which switches their periodic tasks off by
design. `fs` is a bulk file ingest with no per-company attempt to report and is
verdict'd **`not measured`** — never `OK`, which would claim a check this
command cannot make. Nothing anywhere measures whether FS data is still fresh;
see `docs/SOURCE_DATA_INTEGRITY.md`.

### Sync jobs

Depth measures load; it cannot measure progress either. A job whose worker died
holds its `running` row and a frozen `last_heartbeat` indefinitely: the queue
looks healthy, the admin dashboard keeps counting it as an active import
(`adminapi/views/dashboard.py:35`), and nothing will ever finish it. SyncJob #3
(`ruz_full_firmy`) did exactly that for **15 days**, and neither the queue
section nor the source section above could see it — neither had ever read
`SyncJob` at all.

`make ops-check` therefore also chains `python manage.py sync_health`
(`backend/registers/management/commands/`), which owns what "an active job is
really active" means:

- a `running` job whose heartbeat is past the staleness threshold
  (`CISTAFIRMA_STUCK_HEARTBEAT_MINUTES`, default 30) — the worker is gone and no
  retry, resume or cancel will arrive for it;
- a `queued` job older than `CISTAFIRMA_QUEUED_JOB_MINUTES` (default 720) that
  was never claimed — accepted, then silently dropped;
- the **newest** run of a `triggered_via='beat_schedule'` job type that ended
  `failed`, within `CISTAFIRMA_FAILED_JOB_HOURS` (default 24) — the one failure
  with nobody in front of it.

The third is judged on the newest attempt rather than on any failed one, so a
failure the next run supersedes is history: job #11 (18:22, an `ImportError`
after a deploy) went red on the spot and job #12 (18:53, 6 850 records)
released it half an hour later. A gate that stayed red for the superseded run
would be reporting a scar rather than a state. The window bounds the complaint
as well as opening it, so a failure nothing has followed up stops counting —
and a schedule that has genuinely stopped dispatching still produces a fresh
failed row long before that. What it cannot see is a schedule that dies
*before* a job row is ever created (a task that was never registered); the
command prints an empty window instead of staying quiet about it, which is
labelled as an absence rather than a pass.

`paused` and `cancelled` runs are printed with their status but not judged:
pausing is a resumable operator action, and the admin API refuses both cancel
and resume for RUZ jobs, so neither can be a control quietly failing.

Counter values are printed but never judged, because how many items a job
*should* process depends on the run rather than on its type, so no threshold
would be honest. The command asks `is_stuck()` in
`registers/services/sync_engine.py` for the staleness verdict instead of
re-deriving it, so the gate cannot call a job healthy that the watchdog is about
to fail; the gate itself parses only the command's `Sync jobs: N unmet` summary
and fails closed if that line is ever unreadable. The reaper that acts on the
same verdict on a schedule is described in `docs/OBSERVABILITY.md`.

The queued cutoff is deliberately generous, for the same reason the unattended
run treats a disconnected disk as a warning: the `insurance` queue is normally
saturated and a long wait there is a documented normal state, so a control that
reddens for it every week is one people learn to ignore. A monitored run must
never fail on something these docs describe as normal.

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
- **RPO (Recovery Point Objective):** with the weekly job installed (launchd
  LaunchAgent or systemd user timer), RPO
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
   encrypt it in place instead. This is non-destructive and the volume stays
   readable and writable throughout, so a disk does not have to be empty — or
   to be dedicated to backups — before it can be encrypted:

   ```bash
   diskutil apfs encryptVolume <apfsVolumeDisk> -user disk
   ```

   The command returns within about a second, and `diskutil info` reports the
   volume as encrypted from that moment while the conversion continues in the
   background — **so a green off-site control is not evidence that the
   conversion has finished.** That behaviour was measured on 2026-09-10 on an
   APFS volume built on a disk image (i.e. on the internal SSD). It was *not*
   measured on an external USB disk, and whether the background pass completes
   without incident on one is Apple's design intent rather than a verified
   result: keep the disk connected and powered until the conversion is done.

   Either way the replication script refuses volumes that do not report
   encryption through `diskutil`. Save the passphrase in a password manager.

   On **Linux** there is no vendor tool to ask, so the destination must be a
   LUKS/dm-crypt filesystem and the check reads that from the device stack
   (`cryptsetup status`, `lsblk -s`). Where the destination is an **sshfs** mount
   (`user@host:/path`, normally created by an fstab entry with
   `x-systemd.automount`), the bytes are on the remote host, so the same check is
   performed there **over SSH**: unattended `ssh` to that host must work for the
   backup user (key-based, host key already known) or the verdict is `unknown`
   and the copy is refused. A destination that is honestly unencrypted fails this
   gate on Linux exactly as it does on macOS — there is no Linux exemption, and
   the only way past it is the same
   `CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true` token. The known Linux
   target is `/dev/sda3`, ext4, with no LUKS layer anywhere in its device stack
   (`lsblk -s -no NAME,TYPE,FSTYPE` → `sda3 part ext4` under `sda disk`), and the
   operator has no passwordless `sudo` to create one (`sudo -n true` → `a password
   is required`), so that gate **cannot** pass there today. Note which verdict
   that produces: `lsblk` answers, and answers *no*, so the remote check reports
   `unencrypted` — not `unknown`. The refusal is a finding about the destination,
   not a limitation of the check. That is the control working, not a bug to route
   around: the honest options are to encrypt the target, or to run with the token
   while the gap is open.
2. Create the target directory and record it on this machine:

   ```bash
   mkdir -p "/Volumes/<disk>/cistafirmaBackups"        # macOS
   mkdir -p /mnt/cistafirma-offsite                    # Linux (or the sshfs mount point)
   make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="<that directory>"
   ```

   On Linux the directory is often an automount point that exists whether or not
   the target is reachable, so the status command below is what tells the two
   apart — see *The destination must really be attached*.

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

   Afterwards, check the first unattended run in the platform's run log
   (`~/Library/Logs/CistaFirma/backup.out.log` on macOS,
   `~/.local/state/CistaFirma/logs/backup.out.log` on Linux): it must report
   either `off-site volume detected; replicating` or an explicit warning naming
   what is missing. It must **not** be silent about the replica.

5. At least monthly, restore the newest off-site dump **from a different
   machine** (or after a simulated disk loss) with `make db-restore-drill`,
   proving retrieval from a second failure domain.

Until step 3 has produced a verified replica, the local backup is an important
first layer — not a complete disaster-recovery solution.
