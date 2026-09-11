from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus
from registers.services.ruz_financials_sync import ANSWERED_RETRY_AFTER
from registers.services.sync_engine import RETRY_SHARE
from registers.tasks import financials_sync_batch


def _companies(count: int, *, start: int = 1, **kwargs) -> list[Company]:
    return [
        Company.objects.create(
            ruz_id=start + index,
            ico=f"{start + index:08d}",
            nazov_UJ=f"Firma {start + index}",
            pravna_forma=kwargs.pop("pravna_forma", "112"),
            **kwargs,
        )
        for index in range(count)
    ]


def _record(company_ids, *, success=True, retry_at=None):
    """What a real attempt leaves behind. `financials_sync_batch` has no cursor."""
    for company_id in company_ids:
        CompanySyncStatus.objects.update_or_create(
            company_id=company_id,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            defaults={
                "last_attempted_at": timezone.now(),
                "consecutive_failures": 0 if success else 1,
                "next_retry_at": retry_at,
            },
        )


class FinancialsRotationTests(TestCase):
    """The batch must not choose the same companies twice.

    This is the regression the whole increment exists for. The old selection was
    `order_by('id')[:limit]` with no cursor, so 32 consecutive beat runs chose
    the same 500 companies and coverage stopped at 309 of 251 598 -- without a
    single failure, log line or alert. Nothing in the test suite noticed,
    because every other assertion about the import was about a company it had
    already reached.
    """

    def test_consecutive_batches_never_repeat_themselves(self):
        _companies(20)

        first = financials_sync_batch(5)
        self.assertEqual(len(first), 5)
        _record(first, retry_at=timezone.now() + ANSWERED_RETRY_AFTER)

        second = financials_sync_batch(5)
        self.assertEqual(len(second), 5)
        self.assertEqual(
            set(first) & set(second),
            set(),
            "the second batch returned companies the first one had just synced",
        )

    def test_the_rotation_only_advances_because_attempts_are_recorded(self):
        """The status row is not bookkeeping -- it is the cursor.

        Stated as a test because it is a real coupling a future caller can break
        by syncing without recording: the batch would then hand back the same
        companies forever, which is the original bug with one extra step.
        """
        _companies(20)

        first = financials_sync_batch(5)
        second = financials_sync_batch(5)

        self.assertEqual(first, second)

    def test_a_company_whose_retry_is_in_the_future_is_left_alone(self):
        companies = _companies(10)
        _record([companies[0].id], retry_at=timezone.now() + timedelta(hours=1))

        self.assertNotIn(companies[0].id, financials_sync_batch(10))

    def test_a_failure_that_is_due_is_retried(self):
        companies = _companies(10)
        _record([companies[0].id], retry_at=timezone.now() - timedelta(minutes=1))

        self.assertIn(companies[0].id, financials_sync_batch(10))

    def test_a_blocked_company_is_never_chosen(self):
        companies = _companies(10)
        _record([companies[0].id])
        CompanySyncStatus.objects.filter(company=companies[0]).update(
            is_blocked=True, next_retry_at=None
        )

        self.assertNotIn(companies[0].id, financials_sync_batch(10))

    def test_eligible_only_is_the_default_and_excludes_the_rest(self):
        eligible = Company.objects.create(
            ruz_id=9001, ico="00009001", nazov_UJ="Eligible s.r.o.", pravna_forma="112"
        )
        dissolved = Company.objects.create(
            ruz_id=9002,
            ico="00009002",
            nazov_UJ="Zrusena s.r.o.",
            pravna_forma="112",
            datum_zrusenia=date(2020, 1, 1),
        )
        other_form = Company.objects.create(
            ruz_id=9003, ico="00009003", nazov_UJ="Fyzicka osoba", pravna_forma="101"
        )

        default_batch = financials_sync_batch(10)
        self.assertIn(eligible.id, default_batch)
        self.assertNotIn(dissolved.id, default_batch)
        self.assertNotIn(other_form.id, default_batch)

        wide_batch = financials_sync_batch(10, eligible_only=False)
        self.assertIn(dissolved.id, wide_batch)
        self.assertIn(other_form.id, wide_batch)

    def test_retries_never_spend_more_than_their_share_of_the_batch(self):
        """A failing minority must not be able to hold the whole rotation.

        Every company here is due for a retry and none is new ground, so the
        only thing that can bound the batch is the share.
        """
        companies = _companies(40)
        _record([company.id for company in companies], retry_at=timezone.now() - timedelta(minutes=1))

        batch = financials_sync_batch(20)

        self.assertEqual(len(batch), 20 // RETRY_SHARE)
        self.assertLess(len(batch), 20)

    def test_new_ground_fills_whatever_the_retries_leave(self):
        companies = _companies(40)
        _record(
            [company.id for company in companies[:3]],
            retry_at=timezone.now() - timedelta(minutes=1),
        )

        batch = financials_sync_batch(20)

        self.assertEqual(len(batch), 20)
        self.assertEqual(set(batch[:3]), {company.id for company in companies[:3]})

    def test_a_batch_smaller_than_the_share_still_returns_new_ground(self):
        """`limit // RETRY_SHARE` is 0 for tiny batches; they must not come back empty."""
        _companies(10)

        self.assertEqual(len(financials_sync_batch(2)), 2)
