"""The gate that finally reads `registers_syncjob`.

Queue depth reports load and `source_health` reports what the sources achieve;
neither looked at sync jobs at all, so job #3 was counted as an active import
by the dashboard for fifteen days while `make ops-check` reported OK.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from registers.models import SyncJob
from registers.services import sync_engine


class SyncHealthCommandTests(TestCase):
    def _job(self, **kwargs):
        defaults = {
            "job_type": "ruz_incremental",
            "status": "running",
            "started_at": timezone.now(),
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _queued_since(self, age):
        """A job whose `queued_at` is `age` old.

        `queued_at` is `auto_now_add`, so it can only be moved after the row
        exists.
        """
        job = self._job(status="queued", started_at=None, queued_at=None)
        SyncJob.objects.filter(pk=job.pk).update(queued_at=timezone.now() - age)
        job.refresh_from_db()
        return job

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("sync_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_a_stuck_running_job_is_unmet(self):
        self._job(last_heartbeat=timezone.now() - timedelta(days=15))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("FAIL", output)
        self.assertIn("the worker is gone", output)

    def test_a_healthy_running_job_is_fine(self):
        self._job(last_heartbeat=timezone.now())

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_job_queued_past_the_threshold_is_unmet(self):
        """Accepted, then silently dropped -- nothing is picking it up."""
        self._queued_since(timedelta(hours=20))

        output, code = self._run(queued_minutes=720)

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("never claimed", output)

    def test_a_job_queued_briefly_is_not_judged(self):
        self._queued_since(timedelta(minutes=5))

        output, code = self._run(queued_minutes=720)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_the_queued_threshold_is_configurable(self):
        self._queued_since(timedelta(minutes=30))

        _, strict = self._run(queued_minutes=10)
        _, relaxed = self._run(queued_minutes=600)

        self.assertEqual(strict, 1)
        self.assertEqual(relaxed, 0)

    def test_the_queued_threshold_can_come_from_the_environment(self):
        """The container's environment is where ops sets it, not the CLI."""
        self._queued_since(timedelta(minutes=30))

        with patch.dict("os.environ", {"CISTAFIRMA_QUEUED_JOB_MINUTES": "10"}):
            output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)

    def test_a_completed_job_with_no_counters_is_reported_but_not_judged(self):
        """Job #8's shape: `completed` with zero processed items.

        How many items a job *should* process depends on the run, not on its
        type, so there is no honest threshold -- but the zero is still shown,
        because a job that reports nothing cannot be told from one that did
        nothing.
        """
        self._job(
            status="completed",
            last_heartbeat=timezone.now(),
            completed_at=timezone.now(),
            processed_items=0,
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)
        self.assertIn("not judged", output)
        self.assertIn("completed", output)

    def test_a_cancelled_job_is_listed_but_not_judged(self):
        """Cancelling is a decision somebody made, not a control that failed.

        Judging it would make the gate red for the operator's own deliberate
        action -- and for a RUZ job it cannot even happen, since the admin API
        refuses both cancel and resume for them.
        """
        self._job(
            status="cancelled",
            started_at=timezone.now() - timedelta(days=40),
            last_heartbeat=timezone.now() - timedelta(days=40),
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)
        self.assertIn("cancelled", output)

    def test_the_gate_agrees_with_the_reaper(self):
        """The property that makes the gate worth reading.

        `sync_health` must not re-derive what "stuck" means: a job it reports
        as healthy while the watchdog is about to fail it would be worse than
        no gate at all.
        """
        stuck = self._job(last_heartbeat=timezone.now() - timedelta(hours=2))
        healthy = self._job(last_heartbeat=timezone.now())

        self.assertTrue(sync_engine.is_stuck(stuck))
        self.assertFalse(sync_engine.is_stuck(healthy))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn(f"job #{stuck.pk}", output)
        self.assertNotIn(f"job #{healthy.pk} (", output)

    def test_the_reaper_clears_the_gates_only_complaint(self):
        """End to end: what the reaper failed, the gate stops reporting."""
        self._job(last_heartbeat=timezone.now() - timedelta(days=15))

        before, _ = self._run()
        self.assertIn("Sync jobs: 1 unmet", before)

        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 1)

        after, code = self._run()
        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", after)


class FailedBeatJobTests(TestCase):
    """The run nobody is watching.

    A beat-scheduled import that dies has no operator in front of it: the row
    says `failed`, the table prints it, and until 2026-09-10 the gate's verdict
    still read `Sync jobs: 0 unmet` -- so a schedule that had stopped
    delivering data looked exactly like one that was working. Job #11 (18:22,
    an `ImportError` after a deploy) and job #3 (reaped by the watchdog) were
    both on screen while the gate said zero.
    """

    def _beat_job(self, *, status, age, **kwargs):
        job = SyncJob.objects.create(
            job_type="ruz_incremental",
            status=status,
            triggered_via="beat_schedule",
            started_at=timezone.now() - age,
            last_heartbeat=timezone.now() - age,
            completed_at=timezone.now() - age,
            **kwargs,
        )
        SyncJob.objects.filter(pk=job.pk).update(queued_at=timezone.now() - age)
        job.refresh_from_db()
        return job

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("sync_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_a_failed_beat_run_is_unmet(self):
        self._beat_job(
            status="failed", age=timedelta(hours=1), last_error="ImportError: boom"
        )

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("the newest beat-scheduled run", output)
        self.assertIn("ImportError: boom", output)

    def test_a_manual_run_that_failed_is_not_the_schedules_problem(self):
        """The distinction the whole rule rests on.

        Someone starting a sync by hand is watching it; a run that dies at
        00:22 is not. Judging both would put the gate red on an operator's own
        failed experiment.
        """
        SyncJob.objects.create(
            job_type="ruz_incremental",
            status="failed",
            triggered_via="admin_ui",
            started_at=timezone.now(),
            completed_at=timezone.now(),
            last_error="operator cancelled the wrong thing",
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_later_successful_run_clears_it(self):
        """A failure the next run supersedes is history, not state.

        Otherwise the gate would stay red for a transient failure that fixed
        itself -- the alarm that stops being read.
        """
        self._beat_job(
            status="failed", age=timedelta(hours=2), last_error="ReadTimeoutError"
        )
        self._beat_job(status="completed", age=timedelta(minutes=30))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_failure_the_window_has_passed_is_not_judged(self):
        """It bounds the complaint as well as opening it.

        Past the window the job is history. A control that cannot clear is one
        nobody reads, and the failure this catches -- a schedule that has
        stopped -- will produce a fresh failed row long before the window runs
        out.
        """
        self._beat_job(status="failed", age=timedelta(days=3))

        output, code = self._run(failed_job_hours=24)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_the_failed_window_is_configurable_and_can_come_from_the_env(self):
        self._beat_job(status="failed", age=timedelta(days=3))

        _, strict = self._run(failed_job_hours=24 * 7)
        self.assertEqual(strict, 1)

        with patch.dict("os.environ", {"CISTAFIRMA_FAILED_JOB_HOURS": "168"}):
            output, code = self._run()
        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)

    def test_an_empty_window_says_so_instead_of_going_quiet(self):
        """Absence of evidence, labelled as such.

        A schedule that has stopped dispatching leaves no failed row to judge,
        so this control cannot see it -- and saying that out loud is what keeps
        `0 unmet` from being read as "the schedule is fine".
        """
        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("beat-scheduled job types", output)
        self.assertIn("none recorded in the window", output)
