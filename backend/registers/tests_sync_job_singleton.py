from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from registers.models import SyncJob, SyncProgress
from registers.services import sync_engine


class RuzSyncJobSingletonTests(TestCase):
    def test_second_ruz_request_returns_the_existing_active_job(self):
        first, first_created = sync_engine.enqueue_ruz_job(
            job_type="ruz_full",
            parameters={"reset": False},
        )
        second, second_created = sync_engine.enqueue_ruz_job(
            job_type="ruz_incremental",
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(
            SyncJob.objects.filter(concurrency_key=sync_engine.RUZ_CONCURRENCY_KEY).count(),
            1,
        )

    def test_only_one_delivery_can_claim_a_queued_ruz_job(self):
        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_incremental")

        first_claim = sync_engine.claim_ruz_job(job.pk, celery_task_id="task-1")
        second_claim = sync_engine.claim_ruz_job(job.pk, celery_task_id="task-2")

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertEqual(job.celery_task_id, "task-1")

    @patch("registers.tasks.call_command")
    def test_firmy_full_task_uses_full_resync_and_correlated_job(self, call_command):
        from registers.tasks import fetch_ruz_data_firmy_only

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full_firmy")
        fetch_ruz_data_firmy_only.apply(args=(), kwargs={"sync_job_id": job.pk})

        call_command.assert_called_once_with(
            "fetch_ruz_data",
            "--full-resync",
            "--entity-type",
            "companies",
            sync_job_id=job.pk,
        )
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")


class ResumeFullRuzSyncTests(TestCase):
    """`resume_full_ruz_sync` must actually resume the full walk.

    It could not, and the failure was silent in the way this repository keeps
    paying for: it dispatched `--resume` without `--full-resync`, so the command
    derived `sync_type='incremental'` and looked for an *incremental* progress
    row. The `full` row the task had just found and logged was never the row the
    command read. It printed "Nenájdený žiadny sync na pokračovanie" and
    returned -- leaving behind the `SyncJob` it had already enqueued and
    claimed, `running`, for ever.
    """

    def _full_progress(self, **kwargs):
        defaults = {
            "sync_type": "full",
            "status": "failed",
            "zmenene_od": date(2000, 1, 1),
            "last_processed_ruz_id": 4242,
        }
        defaults.update(kwargs)
        return SyncProgress.objects.create(**defaults)

    @patch("registers.tasks.call_command")
    def test_the_resume_carries_the_full_flag(self, call_command):
        """Without `--full-resync` the command never reads the full row, and the
        whole task is a no-op that still claims a job."""
        from registers.tasks import resume_full_ruz_sync

        self._full_progress()
        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")

        resume_full_ruz_sync.apply(args=(), kwargs={"sync_job_id": job.pk})

        call_command.assert_called_once_with(
            "fetch_ruz_data",
            "--full-resync",
            "--resume",
            sync_job_id=job.pk,
        )

    @patch("registers.tasks.call_command")
    def test_a_resumed_run_ends_as_a_completed_job_not_a_zombie(self, call_command):
        """The claimed job has to be finished by the layer that claimed it. Left
        `running`, it is indistinguishable in the admin from a live import and
        only the watchdog's 30-minute threshold would ever clear it."""
        from registers.tasks import resume_full_ruz_sync

        self._full_progress()
        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")

        resume_full_ruz_sync.apply(args=(), kwargs={"sync_job_id": job.pk})

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

    @patch("registers.tasks.call_command")
    def test_a_killed_run_is_still_resumable(self, call_command):
        """A worker that is killed writes nothing: the progress row stays
        `running`, because the process that would have written `failed` is the
        one that died. Excluding that status is what made the task useless in
        the only case that needs it."""
        from registers.tasks import resume_full_ruz_sync

        self._full_progress(status="running")
        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")

        result = resume_full_ruz_sync.apply(args=(), kwargs={"sync_job_id": job.pk})

        call_command.assert_called_once()
        self.assertIn("completed", result.get())

    @patch("registers.tasks.call_command")
    def test_without_a_full_row_nothing_is_dispatched(self, call_command):
        """An incremental row must not be mistaken for a full one -- that is the
        confusion the missing flag produced, and it has to stay impossible."""
        from registers.tasks import resume_full_ruz_sync

        SyncProgress.objects.create(
            sync_type="incremental",
            status="failed",
            zmenene_od=date(2026, 8, 4),
            last_processed_ruz_id=2624307,
        )

        result = resume_full_ruz_sync.apply(args=())

        call_command.assert_not_called()
        self.assertEqual(result.get(), "No sync to resume")

    @patch("registers.tasks.call_command")
    def test_it_does_not_start_a_second_import_beside_a_live_one(self, call_command):
        """Dispatch is idempotent, which is what lets a keeper re-dispatch it on
        every tick without ever running two imports over the same cursor."""
        from registers.tasks import resume_full_ruz_sync

        self._full_progress()
        live, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        sync_engine.claim_ruz_job(live.pk)

        result = resume_full_ruz_sync.apply(args=())

        call_command.assert_not_called()
        live.refresh_from_db()
        self.assertEqual(live.status, "running")
        self.assertIn("already running", result.get())

    @patch("registers.tasks.call_command")
    def test_the_newest_full_row_wins_over_a_dead_earlier_one(self, call_command):
        """An aborted attempt leaves its `failed` row behind, and it keeps the
        cursor it died on. Picking the older row would restart the walk from
        there -- re-reading every id between the two, which on a ~2M-id register
        is the difference between a resume and a second full run.

        Read off the task's own log line rather than off a re-run of the query:
        the cursor is not an argument to anything, it is whatever the command
        finds in the row this task chose, so the choice is the observable.
        """
        from registers.tasks import resume_full_ruz_sync

        self._full_progress(status="failed", last_processed_ruz_id=1000)
        self._full_progress(status="paused", last_processed_ruz_id=1900000)

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")

        with self.assertLogs("registers.tasks", level="INFO") as logs:
            resume_full_ruz_sync.apply(args=(), kwargs={"sync_job_id": job.pk})

        call_command.assert_called_once()
        self.assertIn("1900000", "\n".join(logs.output))


class StartFullRuzSyncFromIdTests(TestCase):
    """The sibling of the resume task, and the same defect.

    It parked a `full` progress row and then dispatched `--resume` without
    `--full-resync`, so the command derived `sync_type='incremental'`. Worse
    than a no-op: an incremental row is usually lying around, so this could
    resume the *incremental* walk from the incremental cursor instead of the
    register from the id the caller typed into the admin form.
    """

    @patch("registers.tasks.call_command")
    def test_it_carries_the_full_flag(self, call_command):
        from registers.tasks import start_full_ruz_sync_from_id

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        start_full_ruz_sync_from_id.apply(
            args=(), kwargs={"start_id": 2000000, "sync_job_id": job.pk}
        )

        call_command.assert_called_once_with(
            "fetch_ruz_data",
            "--full-resync",
            "--resume",
            sync_job_id=job.pk,
        )

    @patch("registers.tasks.call_command")
    def test_an_incremental_row_does_not_capture_the_walk(self, call_command):
        """The row that used to win: the command looked for this one, not for
        the `full` row the task had just written."""
        from registers.tasks import start_full_ruz_sync_from_id

        incremental = SyncProgress.objects.create(
            sync_type="incremental",
            status="paused",
            zmenene_od=date(2026, 9, 18),
            last_processed_ruz_id=2624307,
        )

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        start_full_ruz_sync_from_id.apply(
            args=(), kwargs={"start_id": 2000000, "sync_job_id": job.pk}
        )

        call_command.assert_called_once()
        incremental.refresh_from_db()
        self.assertEqual(incremental.last_processed_ruz_id, 2624307)

    @patch("registers.tasks.call_command")
    def test_the_cursor_lands_one_before_the_requested_id(self, call_command):
        """`start_id` has to be the *first* id read, and a resume continues from
        the stored cursor, so the stored value must be one less. Off by one here
        silently skips the id the operator asked to start from."""
        from registers.tasks import start_full_ruz_sync_from_id

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        start_full_ruz_sync_from_id.apply(
            args=(), kwargs={"start_id": 2000000, "sync_job_id": job.pk}
        )

        progress = SyncProgress.objects.get(sync_type="full")
        self.assertEqual(progress.last_processed_ruz_id, 1999999)
        self.assertEqual(progress.status, "paused")

    @patch("registers.tasks.call_command")
    def test_it_ends_as_a_completed_job(self, call_command):
        from registers.tasks import start_full_ruz_sync_from_id

        job, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        start_full_ruz_sync_from_id.apply(
            args=(), kwargs={"start_id": 2000000, "sync_job_id": job.pk}
        )

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

    def test_no_hard_time_limit_kills_the_walk(self):
        """A walk from an arbitrary id is multi-day, and `time_limit` is a hard
        kill: nothing writes `failed`, so the job sits `running` until the
        watchdog reaps it. Its two siblings carry no limit either."""
        from registers.tasks import (
            resume_full_ruz_sync,
            start_full_ruz_sync,
            start_full_ruz_sync_from_id,
        )

        for task in (start_full_ruz_sync_from_id, start_full_ruz_sync, resume_full_ruz_sync):
            self.assertIsNone(
                task.time_limit,
                f"{task.name} would be SIGKILLed mid-walk at {task.time_limit}s",
            )


class RuzFullKeeperDecisionTests(TestCase):
    """The rule the 24/7 keeper ticks on.

    A full walk runs for days, and over days it ends the ordinary way: a
    `docker compose up`, a reboot, a killed worker. The watchdog fails the job
    half an hour later and nothing restarts it, so the walk silently stops
    where it died -- which is how the register came to be missing companies in
    the first place. These pin the answer for every state a job can be in.

    The rule is a pure function of the newest `ruz_full` row and the clock, so
    it is tested directly rather than through a keeper process.
    """

    def _job(self, **kwargs):
        """A `ruz_full` job in a chosen state, with a chosen past.

        Timestamps are written with `update()` because `queued_at` is
        `auto_now_add` and `completed_at` is only ever set by the lifecycle
        helpers -- both are "now" when created, and the keeper's whole question
        is how long ago.
        """
        defaults = {"job_type": "ruz_full", "status": "failed"}
        defaults.update(kwargs)
        job = SyncJob.objects.create(**defaults)
        stamps = {}
        for field in ("started_at", "completed_at", "last_heartbeat"):
            if field in kwargs:
                stamps[field] = kwargs[field]
        if "queued_at" in kwargs:
            stamps["queued_at"] = kwargs["queued_at"]
        if stamps:
            SyncJob.objects.filter(pk=job.pk).update(**stamps)
        job.refresh_from_db()
        return job

    def _ago(self, **delta):
        return timezone.now() - timedelta(**delta)

    def test_no_full_walk_ever_means_start_one(self):
        action, job = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "start")
        self.assertIsNone(job)

    def test_a_completed_walk_ends_the_keeping(self):
        """The one terminal state. Re-dispatching here would restart a finished
        multi-day walk from the beginning, for ever."""
        self._job(status="completed", completed_at=self._ago(days=2))

        action, job = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "done")
        self.assertEqual(job.status, "completed")

    def test_a_running_walk_is_left_alone(self):
        self._job(status="running", started_at=self._ago(hours=1))

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "wait")

    def test_a_queued_walk_is_left_alone(self):
        """Dispatched and not yet claimed. The worker may be starting up, and a
        second dispatch would meet the live row on `ruz:global` anyway."""
        self._job(status="queued")

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "wait")

    def test_a_running_walk_with_a_stale_heartbeat_still_waits(self):
        """The watchdog owns "this run is dead", and it is the only owner. The
        keeper answering that question too would be a second answer to it, and
        a `running` row blocks a dispatch on the concurrency key regardless --
        so the tick would enqueue a message that can only no-op."""
        self._job(status="running", started_at=self._ago(days=1),
                  last_heartbeat=self._ago(hours=1))

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "wait")

    def test_a_failed_walk_is_resumed(self):
        self._job(status="failed", started_at=self._ago(days=3),
                  completed_at=self._ago(hours=1))

        action, job = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "resume")
        self.assertEqual(job.status, "failed")

    def test_a_paused_walk_is_resumed(self):
        """`pause_job` does not write `completed_at` -- a paused job has none --
        so the decision cannot read that column alone to know when a run ended.
        Reading it alone would leave a paused walk paused for ever."""
        job = self._job(status="paused", started_at=self._ago(days=3))
        self.assertIsNone(job.completed_at)

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "resume")

    def test_a_cancelled_walk_is_resumed(self):
        self._job(status="cancelled", started_at=self._ago(hours=5),
                  completed_at=self._ago(hours=5))

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "resume")

    def test_a_walk_that_never_started_is_still_resumed(self):
        """A job cancelled while still queued has neither `completed_at` nor
        `started_at`; `queued_at` is the only thing left to date it."""
        self._job(status="cancelled", started_at=None, completed_at=None,
                  queued_at=self._ago(hours=5))

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "resume")

    def test_a_walk_that_just_died_is_not_redispatched_yet(self):
        """The floor. `delay()` only puts a message on the broker -- the new job
        row is created by the worker that claims it -- so a stopped worker
        leaves the dead row as the newest one. Without this the keeper would
        enqueue a fresh task every tick for as long as the outage lasted."""
        self._job(status="failed", started_at=self._ago(days=3),
                  completed_at=self._ago(minutes=1))

        action, _ = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "wait")

    def test_the_newest_full_walk_is_the_one_judged(self):
        """An earlier completed walk must not end the keeping for a walk that
        came after it, and an earlier failure must not be re-resumed once a
        later run exists."""
        self._job(status="completed", completed_at=self._ago(days=10))
        newest = self._job(status="failed", started_at=self._ago(days=2),
                           completed_at=self._ago(hours=2))

        action, job = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "resume")
        self.assertEqual(job.pk, newest.pk)

    def test_a_finished_incremental_is_not_a_finished_full_walk(self):
        """The six-hourly incremental writes a SyncJob every six hours. Reading
        the newest RUZ job rather than the newest *full* one would find it
        `completed`, conclude the full walk was finished, and never start one.
        """
        SyncJob.objects.create(
            job_type="ruz_incremental", status="completed",
            concurrency_key=sync_engine.RUZ_CONCURRENCY_KEY,
        )
        SyncJob.objects.create(job_type="ruz_full_firmy", status="completed")

        action, job = sync_engine.ruz_full_keeper_decision()

        self.assertEqual(action, "start")
        self.assertIsNone(job)

    def test_every_job_status_yields_a_known_verb(self):
        """The ops script dispatches on these verbs and raises on anything else.
        Enumerated over the model's own choices so a status added later has to
        be answered here rather than falling through."""
        vocabulary = sync_engine.KEEPER_ACTIONS

        for status, _label in SyncJob.STATUS_CHOICES:
            with self.subTest(status=status):
                SyncJob.objects.all().delete()
                self._job(
                    status=status,
                    started_at=self._ago(days=3),
                    completed_at=self._ago(days=2),
                    queued_at=self._ago(days=4),
                )
                action, _ = sync_engine.ruz_full_keeper_decision()
                self.assertIn(action, vocabulary)


COMMAND = "registers.management.commands.ruz_keeper_tick"


class RuzKeeperTickCommandTests(TestCase):
    """The tick the five-minute timer runs, end to end.

    The decision is tested above; what is tested here is the half that acts on
    it -- which verb becomes which dispatch, and that `--dry-run` really is one.
    A keeper that decides correctly and dispatches nothing is the failure this
    whole mechanism exists to prevent, so the dispatch is asserted rather than
    assumed from the verb it printed.
    """

    def _run(self, *args, **kwargs):
        out = StringIO()
        call_command("ruz_keeper_tick", *args, stdout=out, **kwargs)
        return out.getvalue()

    def _job(self, **kwargs):
        defaults = {"job_type": "ruz_full", "status": "failed"}
        defaults.update(kwargs)
        job = SyncJob.objects.create(**defaults)
        stamps = {
            field: kwargs[field]
            for field in ("started_at", "completed_at", "queued_at")
            if field in kwargs
        }
        if stamps:
            SyncJob.objects.filter(pk=job.pk).update(**stamps)
        job.refresh_from_db()
        return job

    def _ago(self, **delta):
        return timezone.now() - timedelta(**delta)

    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_with_no_full_walk_ever_it_starts_one(self, start_task):
        """`reset=False`: the walk must begin at 2000-01-01 but must not wipe the
        counters of a run the keeper is watching."""
        output = self._run()

        start_task.delay.assert_called_once_with(reset=False)
        self.assertIn("RUZ_KEEPER_TICK: start", output)

    @patch(f"{COMMAND}.resume_full_ruz_sync")
    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_a_dead_walk_is_resumed_and_not_restarted(self, start_task, resume_task):
        """A restart would set the cursor back to 2000-01-01 and re-read every id
        the walk has already covered -- days of work thrown away by the one
        action meant to save it."""
        self._job(status="failed", started_at=self._ago(days=3),
                  completed_at=self._ago(hours=1))

        output = self._run()

        resume_task.delay.assert_called_once_with()
        start_task.delay.assert_not_called()
        self.assertIn("RUZ_KEEPER_TICK: resume", output)

    @patch(f"{COMMAND}.resume_full_ruz_sync")
    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_a_finished_walk_dispatches_nothing(self, start_task, resume_task):
        """The terminal state. Dispatched again, the walk would restart from the
        beginning every five minutes, for ever."""
        self._job(status="completed", completed_at=self._ago(days=1))

        output = self._run()

        start_task.delay.assert_not_called()
        resume_task.delay.assert_not_called()
        self.assertIn("RUZ_KEEPER_TICK: done", output)

    @patch(f"{COMMAND}.resume_full_ruz_sync")
    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_a_live_walk_dispatches_nothing(self, start_task, resume_task):
        self._job(status="running", started_at=self._ago(hours=2))

        output = self._run()

        start_task.delay.assert_not_called()
        resume_task.delay.assert_not_called()
        self.assertIn("RUZ_KEEPER_TICK: wait", output)

    @patch(f"{COMMAND}.resume_full_ruz_sync")
    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_dry_run_decides_without_dispatching(self, start_task, resume_task):
        """The operator's check before enabling the timer. It has to exercise the
        same decision and stop short only of the dispatch -- a dry run that
        decided differently would be worse than none."""
        self._job(status="failed", started_at=self._ago(days=3),
                  completed_at=self._ago(hours=1))

        output = self._run("--dry-run")

        resume_task.delay.assert_not_called()
        start_task.delay.assert_not_called()
        self.assertIn("RUZ_KEEPER_TICK: resume", output)
        self.assertIn("RUZ_KEEPER_DRYRUN", output)

    @patch(f"{COMMAND}.start_full_ruz_sync")
    def test_the_tick_reports_the_walk_it_is_watching(self, start_task):
        """The progress row is what an operator reads to answer "how far along is
        it?". Printed even on a tick that dispatches nothing, or the five-minute
        log would say only that something is still running."""
        SyncProgress.objects.create(
            sync_type="full", status="running", zmenene_od=date(2000, 1, 1),
            last_processed_ruz_id=1234567, total_processed=999,
        )
        self._job(status="running", started_at=self._ago(hours=1))

        output = self._run()

        self.assertIn("cursor=1234567", output)
        self.assertIn("processed=999", output)
