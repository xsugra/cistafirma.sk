"""An admin-triggered batch job must end its own SyncJob row.

Four of the ten job types the trigger endpoint accepts are fan-out dispatchers:
`orsr_batch`, `financials_batch`, `insurance_batch` and `fs_update` do not walk
anything themselves -- they select a batch, hand each company to its own task and
return. `_dispatch_job` nevertheless put them through `sync_engine.start_job`, so
their row went `running` with a heartbeat nothing advanced, and `detect_and_fail_
stuck_jobs` recorded the healthy dispatch as `failed` half an hour later.

Measured on production before the fix, for the four types together: sixteen rows,
eight `cancelled` by hand and eight `failed` with "Stuck job auto-failed by
watchdog (no heartbeat)". Not one had ever reached `completed` -- a state the
same query does return for RUZ types, so the absence was real rather than an
instrument that cannot see it.

Both branches are exercised below. The happy one is not enough on its own: the
watchdog must still reap a dispatcher that genuinely died, or the fix would have
bought a green row at the price of the only control that catches a lost one.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from registers import tasks
from registers.models import SyncJob
from registers.services import sync_engine

# job_type -> the task `_dispatch_job` maps it onto.
FAN_OUT_TYPES = {
    "orsr_batch": "schedule_missing_orsr_sync",
    "financials_batch": "schedule_ruz_financials_sync",
    "insurance_batch": "schedule_insurance_debt_checks",
    "fs_update": "update_fs_data_task",
}


class CompleteDispatchJobTests(TestCase):
    def test_a_running_row_is_completed_with_its_note(self):
        job = SyncJob.objects.create(job_type="orsr_batch", status="running")

        self.assertTrue(
            sync_engine.complete_dispatch_job(job.pk, notes="Naplánovaných 12 firiem.")
        )

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.notes, "Naplánovaných 12 firiem.")
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.last_heartbeat)

    def test_a_cancelled_row_is_not_resurrected_by_a_late_dispatcher(self):
        """The guard, not politeness: the operator's answer must outrank the task's.

        A dispatcher runs for seconds, but "seconds" is not "never" -- an operator
        can cancel the row while the fan-out is still being enqueued. An
        unconditional write would flip `cancelled` back to `completed` and the
        cancelling would silently un-happen.
        """
        job = SyncJob.objects.create(job_type="orsr_batch", status="running")
        sync_engine.cancel_job(job, reason="operator changed their mind")

        self.assertFalse(sync_engine.complete_dispatch_job(job.pk, notes="x"))

        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")

    def test_no_job_id_is_not_an_error(self):
        """The beat schedule runs these same tasks and creates no row."""
        self.assertFalse(sync_engine.complete_dispatch_job(None, notes="x"))


class FanOutDispatcherClosesItsRowTests(TestCase):
    def _running_job(self, job_type: str) -> SyncJob:
        job = SyncJob.objects.create(job_type=job_type, status="queued")
        sync_engine.start_job(job)
        return SyncJob.objects.get(pk=job.pk)

    def test_each_fan_out_dispatcher_completes_the_row_it_was_handed(self):
        for job_type, task_name in FAN_OUT_TYPES.items():
            with self.subTest(job_type=job_type):
                job = self._running_job(job_type)
                # The per-company fan-out is not what is under test; the row is.
                with patch.object(tasks.sync_company_orsr_data, "delay"), patch.object(
                    tasks.sync_company_financials_from_ruz, "delay"
                ), patch.object(tasks.update_insurance_debt, "delay"), patch.object(
                    tasks, "call_command"
                ):
                    getattr(tasks, task_name)(sync_job_id=job.pk)

                job.refresh_from_db()
                self.assertEqual(
                    job.status,
                    "completed",
                    f"{job_type} must close its own row, not leave it for the watchdog",
                )

    def test_the_watchdog_still_reaps_a_dispatcher_that_really_died(self):
        """Positive control for the branch above.

        Without this, `test_each_fan_out_dispatcher_completes_...` would also pass
        if the watchdog had simply stopped reaping anything -- and a dispatcher
        lost to a dead worker would then stay `running` for ever, which is the
        fifteen-day job #3 shape this control exists to prevent.
        """
        job = SyncJob.objects.create(job_type="orsr_batch", status="running")
        SyncJob.objects.filter(pk=job.pk).update(
            last_heartbeat=timezone.now() - timedelta(hours=2)
        )

        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 1)

        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIn("watchdog", job.last_error)

    def test_a_completed_dispatcher_is_beyond_the_watchdogs_reach(self):
        """The other half of the control: the fix must not merely race the reaper."""
        job = self._running_job("insurance_batch")
        with patch.object(tasks.update_insurance_debt, "delay"):
            tasks.schedule_insurance_debt_checks(sync_job_id=job.pk)
        SyncJob.objects.filter(pk=job.pk).update(
            last_heartbeat=timezone.now() - timedelta(hours=2)
        )

        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 0)

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")


class DispatchWiringTests(TestCase):
    def test_every_fan_out_type_is_handed_the_job_it_must_close(self):
        """The wiring half of the fix, which the tests above cannot see.

        They call the tasks directly, so they would still pass if `_dispatch_job`
        stopped passing an id -- and then every row would go back to being
        watchdog-failed, exactly as before.
        """
        from adminapi.views.sync import _dispatch_job

        for job_type, task_name in FAN_OUT_TYPES.items():
            with self.subTest(job_type=job_type):
                job = SyncJob.objects.create(job_type=job_type, status="queued")
                with patch.object(
                    getattr(tasks, task_name), "apply_async", return_value=Mock(id="t")
                ) as apply_async:
                    _dispatch_job(job)

                self.assertEqual(
                    apply_async.call_args.kwargs["kwargs"]["sync_job_id"], job.pk
                )
