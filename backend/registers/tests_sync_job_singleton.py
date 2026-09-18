from datetime import date
from unittest.mock import patch

from django.test import TestCase

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
