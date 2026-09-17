from unittest.mock import patch

from django.test import TestCase

from registers.models import SyncJob
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
