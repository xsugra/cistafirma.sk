from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.integrations.rpo_client import RpoApiError
from registers.models import CompanySyncStatus, OrsrCompanyProfile
from registers.scrapers.orsr_scraper import OrsrScraperError
from registers.services.sync_engine import (
    ANSWERED_RETRY_AFTER,
    RETRY_SHARE,
    companies_due_for_sync,
)
from registers.tasks import orsr_sync_batch, schedule_missing_orsr_sync


def _profile(fetch_ok=True, last_error="", oddiel="Sro", vlozka_cislo="12345/B"):
    """What `RpoSyncService.sync_company` returns, narrowed to what callers read.

    The task reads `fetch_ok` and `last_error`; `fetch_orsr_data` also prints
    the oddiel and the vlozka, so those are here too rather than left to blow up
    as an `AttributeError` in a test that is about something else.
    """
    return SimpleNamespace(
        fetch_ok=fetch_ok,
        last_error=last_error,
        oddiel=oddiel,
        vlozka_cislo=vlozka_cislo,
    )


class OrsrOutcomeRecordingTests(TestCase):
    """ORSR's only writer, and the reason it needed one.

    Measured 2026-09-11: `CompanySyncStatus` held **zero** rows with
    `source='orsr'`, and no code path was able to create one. Every reader of
    that table therefore covered a population that silently excluded ORSR --
    `source_health` could not name it, the per-source dashboard card, the
    `sync_state=failing` filter and `lead_scoring`'s average. ORSR also had no
    backoff: `BaseSyncTask`'s three retries over a few minutes were the only
    attempts a failing company would ever get.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=7701,
            ico="77010000",
            nazov_UJ="Orsr Zapísaná s.r.o.",
            pravna_forma="112",
        )

    def _status(self):
        return CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_ORSR
        )

    def _run(self, **service_kwargs):
        """Run the real task against a scripted RPO service."""
        from registers.tasks import sync_company_orsr_data

        service = SimpleNamespace(
            sync_company=lambda company: _profile(**service_kwargs)
        )
        with patch("registers.tasks.RpoSyncService", return_value=service):
            return sync_company_orsr_data(self.company.id)

    def test_a_fetched_profile_is_recorded_as_a_success(self):
        self._run()

        status = self._status()
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNotNone(status.last_succeeded_at)
        self.assertEqual(status.last_error, "")
        self.assertIsNotNone(status.last_attempted_at)

    def test_a_recorded_success_is_scheduled_far_out_not_left_due_now(self):
        """`next_retry_at = NULL` reads as "due now" and would starve the retry lane.

        This is not hypothetical for ORSR: the rotation's retry lane is
        `companies_due_for_sync('orsr')`, so a success that cleared the field
        would put every company ever fetched into a lane sized at a fraction of
        the batch, and the companies that genuinely need another attempt would
        never be reached.
        """
        self._run()

        next_retry_at = self._status().next_retry_at
        self.assertIsNotNone(next_retry_at)
        self.assertGreater(next_retry_at, timezone.now() + timedelta(days=300))
        self.assertAlmostEqual(
            (next_retry_at - timezone.now()).days,
            ANSWERED_RETRY_AFTER.days,
            delta=1,
        )

    def test_a_scraper_error_is_recorded_as_a_failure_and_re_raised(self):
        """The company must leave a row behind *and* still fail loudly.

        Swallowing it would make a permanent outage look like a successful
        night's work, which is the defect class this repository keeps finding.
        """
        from registers.tasks import sync_company_orsr_data

        def boom(company):
            raise OrsrScraperError("ORSR data pre IČO 77010000 sa nepodarilo získať.")

        service = SimpleNamespace(sync_company=boom)
        with patch("registers.tasks.RpoSyncService", return_value=service):
            with self.assertRaises(OrsrScraperError):
                sync_company_orsr_data(self.company.id)

        status = self._status()
        self.assertEqual(status.consecutive_failures, 1)
        self.assertIsNone(status.last_succeeded_at)
        self.assertEqual(status.last_error_type, "network")
        self.assertIn("sa nepodarilo získať", status.last_error)
        self.assertIsNotNone(status.next_retry_at)
        self.assertLess(
            status.next_retry_at,
            timezone.now() + timedelta(days=1),
            "a failure should come back on the backoff schedule, not in a year",
        )

    def test_a_transport_failure_that_writes_no_profile_is_still_recorded(self):
        """The dead end that had no trace at all.

        A `RpoClient` transport error writes no `OrsrCompanyProfile`, so the
        company stays in the `orsr_profile__isnull=True` population and is
        re-dispatched at the head of an `order_by('id')` queue on every run --
        and, before this, no row anywhere said it had ever been tried.
        """
        from registers.tasks import sync_company_orsr_data

        def boom(company):
            # What `RpoClient` actually raises: it wraps every
            # `requests.RequestException` in `RpoApiError`.
            raise RpoApiError(
                "RPO search failed: HTTPSConnectionPool(host='api.statistics.sk', "
                "port=443): Max retries exceeded with url: /search"
            )

        service = SimpleNamespace(sync_company=boom)
        with patch("registers.tasks.RpoSyncService", return_value=service):
            with self.assertRaises(RpoApiError):
                sync_company_orsr_data(self.company.id)

        status = self._status()
        self.assertEqual(status.consecutive_failures, 1)
        self.assertEqual(status.last_error_type, "network")
        self.assertIn("Max retries exceeded", status.last_error)
        self.assertFalse(
            OrsrCompanyProfile.objects.filter(company=self.company).exists(),
            "this is the case that left no trace anywhere: no profile, no row",
        )

    def test_a_failure_is_held_back_by_its_backoff_then_offered_to_the_retry_lane(self):
        """What the row is *for*: without it the rotation cannot see the company.

        The same company is asked about twice -- once right after the failure
        and once after its backoff has elapsed -- so the assertion is about the
        recorded `next_retry_at`, not about a row a test seeded by hand.
        """
        from registers.tasks import sync_company_orsr_data

        def boom(company):
            raise ConnectionError("RPO API unreachable")

        service = SimpleNamespace(sync_company=boom)
        with patch("registers.tasks.RpoSyncService", return_value=service):
            with self.assertRaises(ConnectionError):
                sync_company_orsr_data(self.company.id)

        self.assertEqual(
            [s.company_id for s in companies_due_for_sync("orsr")],
            [],
            "a failure must come back on the backoff schedule, not on the next batch",
        )

        CompanySyncStatus.objects.filter(company=self.company).update(
            next_retry_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(
            [s.company_id for s in companies_due_for_sync("orsr")],
            [self.company.id],
        )


class OrsrOutcomeRecordingViaCommandsTests(TestCase):
    """The manual drivers must record too, or the gate is blind to their work.

    `fetch_orsr_data` and `sync_orsr_filtered` are not diagnostics -- they are
    the paths an operator uses to push ORSR by hand, and the population they
    walk is exactly the one the rotation walks.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=7702,
            ico="77020000",
            nazov_UJ="Orsr Manuálna s.r.o.",
            pravna_forma="112",
        )

    def _status(self):
        return CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_ORSR
        )

    def test_fetch_orsr_data_records_the_attempt(self):
        from django.core.management import call_command

        service = SimpleNamespace(sync_company=lambda company: _profile())
        with patch(
            "registers.management.commands.fetch_orsr_data.OrsrSyncService",
            return_value=service,
        ):
            call_command("fetch_orsr_data", ico=[self.company.ico])

        self.assertEqual(self._status().consecutive_failures, 0)

    def test_sync_orsr_filtered_records_the_attempt(self):
        from django.core.management import call_command

        service = SimpleNamespace(sync_company=lambda company: _profile())
        with patch(
            "registers.management.commands.sync_orsr_filtered.OrsrSyncService",
            return_value=service,
        ):
            call_command("sync_orsr_filtered", ico=[self.company.ico])

        self.assertEqual(self._status().consecutive_failures, 0)


def _companies(count: int, *, start: int = 1, **kwargs) -> list[Company]:
    default_form = kwargs.pop("pravna_forma", "112")
    return [
        Company.objects.create(
            ruz_id=start + index,
            ico=f"{start + index:08d}",
            nazov_UJ=f"Firma {start + index}",
            pravna_forma=default_form,
            **kwargs,
        )
        for index in range(count)
    ]


def _profile_row(company, *, fetch_ok=True):
    return OrsrCompanyProfile.objects.create(
        company=company, ico=company.ico, fetch_ok=fetch_ok
    )


def _record(company_ids, *, retry_at=None, success=True):
    """What a real attempt leaves behind. `orsr_sync_batch` has no cursor."""
    for company_id in company_ids:
        CompanySyncStatus.objects.update_or_create(
            company_id=company_id,
            source=CompanySyncStatus.SOURCE_ORSR,
            defaults={
                "last_attempted_at": timezone.now(),
                "consecutive_failures": 0 if success else 1,
                "next_retry_at": retry_at,
            },
        )


class OrsrRotationTests(TestCase):
    """The batch must not choose the same companies twice.

    The previous selection was `orsr_profile__isnull=True ... order_by('id')
    [:limit]`, which advanced only because an attempt usually creates a profile
    row. A `RpoClient` transport failure writes nothing, so that company stayed
    at the head of the queue and was re-dispatched every four hours, blocking
    the rotation behind it -- for ever, and without a single row saying it had
    ever been tried.
    """

    def test_consecutive_batches_never_repeat_themselves(self):
        _companies(20)

        first = orsr_sync_batch(5)
        self.assertEqual(len(first), 5)
        _record(first, retry_at=timezone.now() + ANSWERED_RETRY_AFTER)

        second = orsr_sync_batch(5)
        self.assertEqual(len(second), 5)
        self.assertEqual(
            set(first) & set(second),
            set(),
            "the second batch returned companies the first one had just synced",
        )

    def test_with_no_status_row_the_batch_returns_the_same_companies_again(self):
        """Why C2b and C3 ship together: the status row *is* the cursor.

        Before C2b no ORSR attempt wrote one, so this batch would have returned
        the same companies on every run -- which is exactly what
        `order_by('id')[:limit]` did whenever the attempt wrote no profile.
        """
        _companies(20)

        self.assertEqual(orsr_sync_batch(5), orsr_sync_batch(5))

    def test_a_company_that_already_has_a_profile_is_not_new_ground(self):
        companies = _companies(10)
        _profile_row(companies[0])

        self.assertNotIn(companies[0].id, orsr_sync_batch(10))

    def test_a_failure_that_did_leave_a_profile_is_still_reachable(self):
        """The dead end this fixes.

        `OrsrScraperError` writes `fetch_ok=False` onto the profile and re-raises,
        so the company leaves the `orsr_profile__isnull` population and the old
        selection could never pick it again. It is reachable now only through the
        retry lane, which is why the two halves of this increment ship together.
        """
        companies = _companies(10)
        _profile_row(companies[0], fetch_ok=False)
        _record([companies[0].id], retry_at=timezone.now() - timedelta(minutes=1))

        self.assertIn(companies[0].id, orsr_sync_batch(10))

    def test_a_company_whose_retry_is_in_the_future_is_left_alone(self):
        companies = _companies(10)
        _profile_row(companies[0], fetch_ok=False)
        _record([companies[0].id], retry_at=timezone.now() + timedelta(hours=1))

        self.assertNotIn(companies[0].id, orsr_sync_batch(10))

    def test_a_blocked_company_is_never_chosen(self):
        companies = _companies(10)
        _record([companies[0].id])
        CompanySyncStatus.objects.filter(company=companies[0]).update(
            is_blocked=True, next_retry_at=None
        )

        self.assertNotIn(companies[0].id, orsr_sync_batch(10))

    def test_a_due_company_with_no_profile_is_not_handed_out_twice(self):
        """ORSR's new ground is "no profile", not "no attempt", so the two
        populations can overlap -- and a batch that returns one company twice
        would dispatch it twice."""
        companies = _companies(10)
        _record([companies[0].id], retry_at=timezone.now() - timedelta(minutes=1))

        batch = orsr_sync_batch(10)

        self.assertEqual(len(batch), len(set(batch)))
        self.assertIn(companies[0].id, batch)

    def test_the_population_excludes_dissolved_and_ineligible_companies(self):
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

        batch = orsr_sync_batch(10)

        self.assertIn(eligible.id, batch)
        self.assertNotIn(dissolved.id, batch)
        self.assertNotIn(other_form.id, batch)

    def test_retries_never_spend_more_than_their_share_of_the_batch(self):
        companies = _companies(40)
        _record(
            [company.id for company in companies],
            retry_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(len(orsr_sync_batch(20)), 20 // RETRY_SHARE)

    def test_new_ground_fills_whatever_the_retries_leave(self):
        companies = _companies(40)
        _record(
            [company.id for company in companies[:3]],
            retry_at=timezone.now() - timedelta(minutes=1),
        )

        batch = orsr_sync_batch(20)

        self.assertEqual(len(batch), 20)
        self.assertEqual(set(batch[:3]), {company.id for company in companies[:3]})

    def test_the_task_keeps_its_name_and_dispatches_what_was_chosen(self):
        """`schedule_missing_orsr_sync` is in `FOCUS_KEEP_TASKS` and called by
        name from the beat, the admin action and the legacy dashboard."""
        _companies(10)

        with patch("registers.tasks.sync_company_orsr_data") as mock_task:
            result = schedule_missing_orsr_sync(5)

        self.assertIn("5", result)
        self.assertEqual(mock_task.delay.call_count, 5)
