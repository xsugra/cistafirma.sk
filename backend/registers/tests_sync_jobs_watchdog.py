"""The reaper that existed for months and had never once been called.

Job #3 sat `running` for fifteen days with its heartbeat frozen at the instant
it started, counted as an active import the whole time. Nothing was broken
except that no code path ever invoked the function written to catch exactly
that. These tests are the reason it cannot go quiet again unnoticed.
"""

import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from registers.models import AuditLog, SyncJob
from registers.services import sync_engine


def _job(**kwargs):
    """A running job, with only the timestamps a test cares about set."""
    defaults = {
        "job_type": "ruz_incremental",
        "status": "running",
        "started_at": timezone.now(),
    }
    defaults.update(kwargs)
    return SyncJob.objects.create(**defaults)


class StuckJobDetectionTests(TestCase):
    def test_a_fresh_heartbeat_is_left_alone(self):
        job = _job(last_heartbeat=timezone.now())

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_a_stale_heartbeat_is_failed_and_audited(self):
        job = _job(last_heartbeat=timezone.now() - timedelta(days=10))

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIn("watchdog", job.last_error)
        self.assertIsNotNone(job.completed_at)
        self.assertTrue(
            AuditLog.objects.filter(
                action="sync.watchdog.failed", target_id=str(job.pk)
            ).exists()
        )

    def test_a_job_that_never_beat_is_judged_on_when_it_started(self):
        """No heartbeat at all is not the same as an old one.

        A job that never wrote a heartbeat may have died before its first one;
        only `started_at` can say how long that has been true.
        """
        job = _job(last_heartbeat=None, started_at=timezone.now() - timedelta(days=10))

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")

    def test_a_job_that_never_beat_and_just_started_is_left_alone(self):
        job = _job(last_heartbeat=None, started_at=timezone.now())

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_a_job_that_never_started_is_not_judged_on_nothing(self):
        """`started_at` null and no heartbeat is not evidence of death."""
        job = _job(last_heartbeat=None, started_at=None)

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_terminal_jobs_are_never_touched(self):
        """A finished job keeps whatever it finished as, however old it looks."""
        terminal = {}
        for index, status in enumerate(["completed", "failed", "cancelled", "paused"]):
            terminal[status] = SyncJob.objects.create(
                job_type="manual",
                status=status,
                started_at=timezone.now() - timedelta(days=30),
                last_heartbeat=timezone.now() - timedelta(days=30),
            )

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 0)
        for status, job in terminal.items():
            job.refresh_from_db()
            self.assertEqual(job.status, status)

    def test_it_reaps_every_stuck_job_and_reports_how_many(self):
        stuck = [
            _job(last_heartbeat=timezone.now() - timedelta(days=2)),
            _job(last_heartbeat=None, started_at=timezone.now() - timedelta(days=2)),
        ]
        _job(last_heartbeat=timezone.now())  # healthy, must survive

        flipped = sync_engine.detect_and_fail_stuck_jobs()

        self.assertEqual(flipped, 2)
        for job in stuck:
            job.refresh_from_db()
            self.assertEqual(job.status, "failed")

    def test_the_threshold_is_configurable(self):
        """It was 10 minutes while nothing called it; the first real caller is a
        multi-hour import, so the value has to be tunable without a deploy."""
        fresh = _job(last_heartbeat=timezone.now() - timedelta(minutes=5))

        with patch.dict(os.environ, {sync_engine.STUCK_HEARTBEAT_ENV: "1"}):
            self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 1)

        fresh.refresh_from_db()
        self.assertEqual(fresh.status, "failed")

    def test_a_long_import_is_not_killed_by_the_default_threshold(self):
        """The regression this whole ordering exists for.

        A RUZ resync runs for hours; between heartbeats it may be minutes. The
        default must not reap it -- the reaper killing healthy imports would be
        worse than the stale row it was written to catch.
        """
        job = _job(last_heartbeat=timezone.now() - timedelta(minutes=5))

        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 0)

        job.refresh_from_db()
        self.assertEqual(job.status, "running")


class IsStuckRuleTests(TestCase):
    """`is_stuck` is the single owner of the rule; the gate asks it too.

    If these ever disagree with the reaper, `make ops-check` reports a job as
    healthy that the watchdog is about to fail.
    """

    def test_a_running_job_with_a_stale_heartbeat_is_stuck(self):
        job = _job(last_heartbeat=timezone.now() - timedelta(days=1))
        self.assertTrue(sync_engine.is_stuck(job))

    def test_a_running_job_with_a_fresh_heartbeat_is_not_stuck(self):
        job = _job(last_heartbeat=timezone.now())
        self.assertFalse(sync_engine.is_stuck(job))

    def test_a_non_running_job_is_never_stuck(self):
        job = SyncJob.objects.create(
            job_type="manual",
            status="completed",
            started_at=timezone.now() - timedelta(days=1),
            last_heartbeat=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(sync_engine.is_stuck(job))
