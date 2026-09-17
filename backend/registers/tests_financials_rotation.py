from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus
from registers.services.ruz_financials_sync import ANSWERED_RETRY_AFTER, PARSER_REVISION
from registers.services.sync_engine import RETRY_SHARE, update_company_status
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


class FinancialsParserRevisionTests(TestCase):
    """A parser fix must reach the rows already stored, not only the new ones.

    A successful read sets `next_retry_at` a year out, so before this the only
    companies a fix could reach were the ones the rotation had not yet read --
    and a company read once was out of reach for a year. Measured 2026-09-13:
    the accrual asymmetry collapsed by a factor of 28 (24 323 -> 864) on the
    companies a manual re-read happened to cover, and nothing would have
    covered the rest. The vintage of a stored row was not recorded anywhere, so
    there was no way to say which rows had been read by the parser that was
    fixed and which had not.
    """

    def _record_success(self, company_ids, *, revision, retry_at=None):
        """What `update_company_status(success=True, ...)` actually leaves.

        Distinct from the module-level `_record`, which writes a status row
        without `last_succeeded_at` -- a shape no real attempt produces, and one
        that the stale rule deliberately ignores.
        """
        now = timezone.now()
        for company_id in company_ids:
            CompanySyncStatus.objects.update_or_create(
                company_id=company_id,
                source=CompanySyncStatus.SOURCE_FINANCIALS,
                defaults={
                    "last_attempted_at": now,
                    "last_succeeded_at": now,
                    "consecutive_failures": 0,
                    "next_retry_at": (
                        retry_at
                        if retry_at is not None
                        else now + ANSWERED_RETRY_AFTER
                    ),
                    "parser_revision": revision,
                },
            )

    def test_a_row_read_by_an_older_parser_is_due_again(self):
        companies = _companies(10)
        self._record_success([companies[0].id], revision=PARSER_REVISION - 1)

        self.assertIn(companies[0].id, financials_sync_batch(10))

    def test_a_row_read_by_the_current_parser_is_left_alone(self):
        """The other half: once re-read, the row must stop being drawn.

        Without this the stale rule would re-dispatch the same companies every
        batch forever, which is the original "looks alive and never advances"
        defect with the sign flipped.
        """
        companies = _companies(10)
        self._record_success([companies[0].id], revision=PARSER_REVISION)

        self.assertNotIn(companies[0].id, financials_sync_batch(10))

    def test_a_row_from_before_the_field_existed_is_stale(self):
        """NULL means "written before this existed", and that is stale.

        This is what makes the deploy itself the first self-heal: every row
        already stored was read by a parser that has since been fixed, and NULL
        is how the rotation finds them.
        """
        companies = _companies(10)
        self._record_success([companies[0].id], revision=None)

        self.assertIn(companies[0].id, financials_sync_batch(10))

    def test_a_failure_is_not_pulled_in_by_the_stale_rule(self):
        """A row that never succeeded keeps its backoff.

        A failed row carries no revision, so a rule keyed on `parser_revision`
        alone reads it as stale -- and it would then be drawn every batch,
        bypassing `compute_next_retry` and turning exponential backoff into a
        no-op for exactly the companies that need it most.
        """
        companies = _companies(10)
        CompanySyncStatus.objects.create(
            company=companies[0],
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            last_attempted_at=timezone.now(),
            last_succeeded_at=None,
            consecutive_failures=3,
            parser_revision=None,
            next_retry_at=timezone.now() + timedelta(hours=4),
        )

        self.assertNotIn(companies[0].id, financials_sync_batch(10))

    def test_a_revision_bump_is_bounded_by_the_retry_share(self):
        """A bump re-reads the corpus at the rotation's cadence, not at once.

        The stale population enters through the *retry* budget, so a revision
        bump can never dispatch more of the corpus in one batch than a retry
        gets -- which is what keeps this a self-healing rotation rather than the
        queue flood the insurance scheduler used to produce.
        """
        companies = _companies(40)
        self._record_success(
            [company.id for company in companies], revision=PARSER_REVISION - 1
        )

        batch = financials_sync_batch(20)

        self.assertEqual(len(batch), 20 // RETRY_SHARE)

    def test_a_revision_bump_reaches_the_rows_and_not_only_the_status(self):
        """`update_company_status` stamps the revision, and only when told to.

        `None` must leave the column alone: a transport failure read nothing, so
        stamping it there would claim a re-reading that did not happen and take
        the company out of the stale population without replacing its rows.
        """
        company = _companies(1)[0]

        update_company_status(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            success=True,
            parser_revision=PARSER_REVISION,
        )
        status = CompanySyncStatus.objects.get(company=company)
        self.assertEqual(status.parser_revision, PARSER_REVISION)

        update_company_status(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            success=False,
            error="unreachable",
            error_type="network",
        )
        status.refresh_from_db()
        self.assertEqual(status.parser_revision, PARSER_REVISION)
