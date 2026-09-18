"""Keep the full RUZ walk alive until it reaches the end of the register.

A full walk over `zmenene-od=2000-01-01` covers up to ~2.6M RUZ ids at roughly
6 per second, so it runs for days -- and over days the things that end it are
ordinary: a `docker compose up`, a reboot, a killed worker, the OOM killer.
Each leaves the same fingerprint, a `running` `SyncJob` whose heartbeat stops.
The watchdog (`registers.tasks.detect_stuck_sync_jobs`) fails that job half an
hour later and then nothing restarts it, so the walk stops where it died and
stays stopped. That is not hypothetical: it is how the production register came
to be missing companies that had been in RUZ for years.

One tick answers one question -- what should happen to the full walk right now
-- and does it. The rule is `sync_engine.ruz_full_keeper_decision`, where the
test suite can reach it; this command only turns its verdict into a dispatch.

Run by `sk.cistafirma.ruz-keeper.timer` on `dell`, every five minutes:

    cd /home/sam/cistafirma
    docker compose exec -T backend python manage.py ruz_keeper_tick

Deliberately **stateless**: every tick reads the database and decides from
scratch, so there is no loop to wedge and no state file to corrupt. A tick that
never ran -- the host was down -- costs nothing; the next tick sees the same
database and does the right thing.

Deliberately **outside Celery**: a keeper exists to recover the stack from a
state Celery is already in. Putting it on the `celery` beat queue would make it
stop exactly when it is needed -- a wedged worker or an unreconciled
`PeriodicTask` row is one of the failures it is there to survive. It runs on the
host, as a systemd user timer, the same way the backup job does.

`--dry-run` decides and prints without dispatching. It is what an operator wants
before enabling the timer, and what makes "would this tick do the right thing?"
answerable without waiting five minutes to find out.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from registers.models import SyncProgress
from registers.services.sync_engine import ruz_full_keeper_decision
from registers.tasks import resume_full_ruz_sync, start_full_ruz_sync

# `reset=False`: a fresh run already sets `pokracovat_za_id = None`, so the walk
# starts at the beginning of the list without `--reset` -- and `--reset` would
# additionally wipe the counters of the run this keeper is watching.
DISPATCH = {
    "start": lambda: start_full_ruz_sync.delay(reset=False),
    "resume": lambda: resume_full_ruz_sync.delay(),
}

# The verbs that mean "the walk is fine as it is". Spelled out rather than
# inferred from `DISPATCH`, so that an unknown verb raises below instead of
# falling through: `DISPATCH.get(action)` returning None is exactly how a new
# verb would go silently unhandled, and this repository has paid for that shape
# often enough.
NO_DISPATCH = frozenset({"done", "wait"})


class Command(BaseCommand):
    help = (
        "One tick of the full-RUZ-resync keeper: read the newest `ruz_full` "
        "SyncJob and restart the walk if it ended without finishing. Run it on a "
        "timer; it is idempotent and stateless."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Decide and print, dispatch nothing. Use it to check what the next "
                "tick would do before enabling the timer."
            ),
        )

    def handle(self, *args, **options):
        action, job = ruz_full_keeper_decision()
        self.stdout.write(f"RUZ_KEEPER_TICK: {action} | {self._describe(action, job)}")
        self.stdout.write(f"RUZ_KEEPER_STATE: {self._progress_summary()}")

        if action in NO_DISPATCH:
            return action

        dispatch = DISPATCH.get(action)
        if dispatch is None:
            raise RuntimeError(
                f"keeper verb {action!r} has no dispatch: "
                f"ruz_full_keeper_decision and this command have drifted apart"
            )

        if options["dry_run"]:
            self.stdout.write(f"RUZ_KEEPER_DRYRUN: would dispatch {action}")
            return action

        dispatch()
        self.stdout.write(f"RUZ_KEEPER_DISPATCHED: {action}")
        return action

    def _describe(self, action, job) -> str:
        """The human half of the tick: what was seen, and what that means."""
        if job is None:
            return "no ruz_full job has ever run; starting from 2000-01-01"
        if action == "done":
            # The end of the list. Nothing here stops the six-hourly incremental,
            # and nothing should: from here on it is the only thing keeping the
            # register current.
            return (
                f"job #{job.pk} completed (processed={job.processed_items} "
                f"failed={job.failed_items}); nothing left to keep alive"
            )
        if action == "wait":
            return (
                f"job #{job.pk} is `{job.status}` "
                f"(heartbeat={job.last_heartbeat} processed={job.processed_items}); "
                f"waiting"
            )
        return f"job #{job.pk} ended as `{job.status}`; dispatching a resume"

    def _progress_summary(self) -> str:
        """The full-walk row, as one line. Read-only; never creates one.

        `sync_type='full'` and nothing else: `full_companies` /
        `full_individuals` belong to the Firmy-only and SZCO-only walks, and
        `incremental_companies` / `incremental_individuals` to the six-hourly
        window. Only `full` is the walk this keeper exists to finish.
        """
        progress = SyncProgress.objects.filter(sync_type="full").order_by("-id").first()
        if progress is None:
            return "no `full` SyncProgress row yet"
        return (
            f"progress #{progress.pk} {progress.status} "
            f"cursor={progress.last_processed_ruz_id} "
            f"processed={progress.total_processed} errors={progress.total_errors} "
            f"rate={progress.get_rate():.0f}/h"
        )
