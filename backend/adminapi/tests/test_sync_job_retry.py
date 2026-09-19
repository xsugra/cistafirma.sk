"""A retried RUZ job must be claimable, and only one RUZ job may be active.

`SyncJobViewSet.retry_failed` enqueued through `sync_engine.enqueue_job`, which
does not set `concurrency_key` — the column defaults to `""`. Every RUZ job type
is claimed by `claim_ruz_job`, which filters on
`concurrency_key=RUZ_CONCURRENCY_KEY`, so the row this endpoint created could
never be claimed: the task ran, found nothing to claim, logged "not runnable"
and returned. Nothing imported anything.

Three consequences made it worse than a no-op:

- the row stayed `queued` for ever, and `SyncJobViewSet.cancel` refuses RUZ job
  types (409, "cannot be terminated"), so no screen could clear it;
- after `DEFAULT_QUEUED_MINUTES` (720) `sync_health` counts a `queued` job that
  was never claimed as an unmet control, so the phantom fails `make ops-check`
  for ever — the alert that teaches its reader to stop reading it;
- the operator who clicked "Retry Failed" was shown a job that never ran.

The unique constraint does not cover the phantom (`reg_one_active_ruz_job` only
matches `concurrency_key="ruz:global"`), so it did not also wedge every later
RUZ run — it just sat there. The fix mirrors `create()`, which already branched
on `RUZ_JOB_TYPES` for exactly this reason.

These go through the real endpoint, because the claim is about what the button
does.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from registers.models import SyncJob
from registers.services.sync_engine import (
    RUZ_CONCURRENCY_KEY,
    claim_ruz_job,
    enqueue_ruz_job,
)
from users.models import User


class SyncJobRetryFailedTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="admin@example.com", password="testpass123", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def _retry(self, job: SyncJob):
        return self.client.post(f"/api/admin/sync/jobs/{job.pk}/retry-failed/")

    def test_a_retried_ruz_job_can_actually_be_claimed(self):
        """The positive control: the row this endpoint creates is claimable.

        Asserting the status alone would not have caught the bug — the phantom
        was `queued` too, which is precisely what made it look healthy. The
        claim is what separates a job that will run from one that never can.
        """
        failed = SyncJob.objects.create(job_type="ruz_full", status="failed")

        with patch("adminapi.views.sync._dispatch_job"):
            response = self._retry(failed)

        self.assertEqual(response.status_code, 201)
        new = SyncJob.objects.exclude(pk=failed.pk).get()
        self.assertEqual(new.concurrency_key, RUZ_CONCURRENCY_KEY)
        self.assertIsNotNone(
            claim_ruz_job(new.pk),
            "the retried RUZ job must be claimable, not a queued phantom",
        )

    def test_a_retry_during_a_walk_returns_the_active_job_and_creates_nothing(self):
        walk, _ = enqueue_ruz_job(job_type="ruz_full", triggered_via="beat_schedule")
        claim_ruz_job(walk.pk)
        failed = SyncJob.objects.create(job_type="ruz_incremental", status="failed")

        with patch("adminapi.views.sync._dispatch_job") as dispatch:
            response = self._retry(failed)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], walk.pk)
        self.assertEqual(SyncJob.objects.count(), 2)
        dispatch.assert_not_called()

    def test_a_non_ruz_job_still_routes_through_enqueue_job(self):
        """The RUZ branch must not swallow the other job types."""
        failed = SyncJob.objects.create(job_type="orsr_batch", status="failed")

        with patch("adminapi.views.sync._dispatch_job") as dispatch:
            response = self._retry(failed)

        self.assertEqual(response.status_code, 201)
        new = SyncJob.objects.exclude(pk=failed.pk).get()
        self.assertEqual(new.job_type, "orsr_batch")
        self.assertEqual(new.concurrency_key, "")
        dispatch.assert_called_once()
