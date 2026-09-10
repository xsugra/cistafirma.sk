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

    def test_terminal_jobs_are_listed_but_never_fail_the_gate(self):
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
