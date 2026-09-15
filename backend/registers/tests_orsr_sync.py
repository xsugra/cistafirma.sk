from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from companies.models import Company
from registers.integrations.rpo_client import RpoApiError
from registers.models import CompanySyncStatus, OrsrCompanyProfile
from registers.scrapers.orsr_scraper import (
    OrsrNoRecordError,
    OrsrScraper,
    OrsrScraperError,
)
from registers.services.sync_engine import (
    ANSWERED_RETRY_AFTER,
    NO_RECORD_RETRY_AFTER,
    RETRY_SHARE,
    companies_due_for_sync,
    record_orsr_failure,
)
from registers.tasks import (
    orsr_sync_batch,
    schedule_missing_orsr_sync,
    sync_company_orsr_data,
)


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

    def test_an_earlier_writers_note_does_not_survive_as_the_reason(self):
        """A leftover sentence must not be read as what the newest attempt said.

        The ORSR row has more than one writer: `record_orsr_not_monitored` puts a
        reason on it, and migration 0018 seeded 147 rows with a note about the
        migration. ORSR's own writer never wrote the column, so that note kept
        the slot a reason occupies -- and the admin's `ReasonCell` renders
        `last_detail` next to `last_error` as "the reason a company is where it
        is". Measured on dell 2026-09-15: 125 rows carried a `not_in_register`
        verdict from a real attempt and the migration note underneath it.
        """
        CompanySyncStatus.objects.create(
            company_id=self.company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            last_detail="zaradené do fronty migráciou 0018: …",
            consecutive_failures=1,
        )

        self._run()

        self.assertEqual(self._status().last_detail, "")

    def test_a_reason_this_source_owns_is_cleared_by_the_next_attempt_too(self):
        """`record_orsr_not_monitored`'s reason is a reason, and it is the last one.

        It describes an attempt that was *not* made -- nothing was requested --
        so the row leaves the lane and is never superseded in practice. If it
        ever is, the newest attempt is the one that must be read.
        """
        CompanySyncStatus.objects.create(
            company_id=self.company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            last_detail="ORSR sa na firmu nepýta: zrušená 12.05.2026",
            consecutive_failures=0,
        )

        self._run()

        self.assertEqual(self._status().last_detail, "")

    def test_the_error_column_is_still_the_attempts_own(self):
        """Clearing `detail` must not be read as clearing the row's record.

        `last_error` and `last_error_type` are written by this attempt and are
        untouched by the change -- the point is that `last_detail` stops
        carrying someone else's sentence, not that the row forgets.
        """
        CompanySyncStatus.objects.create(
            company_id=self.company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            last_detail="zaradené do fronty migráciou 0018: …",
            consecutive_failures=1,
        )

        self._run(fetch_ok=False, last_error="ORSR neodpovedal")

        status = self._status()
        self.assertEqual(status.last_detail, "")
        self.assertEqual(status.last_error, "ORSR neodpovedal")
        self.assertNotEqual(status.last_error_type, "")

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


# The register's own page for an IČO it does not carry, abbreviated to the parts
# that decide the outcome: no detail link, and the sentence. `Záznamy: 0 - 0 / 0`
# is the counter that precedes it on the real page; it is included because it is
# the tempting thing to match on, and matching the sentence instead is a decision
# this class exists to hold in place.
_NO_RECORD_PAGE = """
<html><body>
<p align="center">Záznamy:&nbsp;<b>0&nbsp;-&nbsp;0&nbsp;/&nbsp;0</b></p>
<p align="center" class="wrn">Kritériám vyhľadávania nezodpovedá žiadny záznam!</p>
</body></html>
"""

# The same page with the sentence reworded the way a register might reword it.
# Nothing in the response says "absent" any more, so the attempt has to fall back
# to being an unclassified failure -- and wait on the short backoff rather than
# being parked for a month on a guess.
_REWORDED_PAGE = """
<html><body>
<p align="center">Záznamy:&nbsp;<b>0&nbsp;-&nbsp;0&nbsp;/&nbsp;0</b></p>
<p align="center" class="wrn">Pre zadané kritériá nebol nájdený žiadny záznam.</p>
</body></html>
"""

_RESULTS_PAGE = """
<html><body>
<a href="vypis.asp?ID=123&amp;SID=1">31987087</a>
</body></html>
"""

_EXTRACT_PAGE = """
<html><body>
<span class="tl">Obchodné meno:</span><span class="ra">ORSR Zapísaná s.r.o.</span>
<span class="tl">Oddiel:</span><span class="ra">Sro</span>
</body></html>
"""


class _ScriptedResponse:
    """Enough of a `requests.Response` for `fetch_by_ico`, and nothing else.

    `text` is a plain attribute here rather than a property, so the scraper's
    `response.encoding = "cp1250"` has nothing to re-decode -- these pages are
    already the string the register would have handed us.
    """

    def __init__(self, text: str, url: str = "https://www.orsr.sk/hladaj_ico.asp?ICO=31987087"):
        self.text = text
        self.url = url
        self.encoding = None

    def raise_for_status(self):
        return None


class _ScriptedSession:
    """Hands out responses in order and remembers what was asked for."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if not self._responses:
            raise AssertionError(
                f"the scraper made {len(self.calls)} requests but the test scripted "
                f"{len(self.calls) - 1}"
            )
        return self._responses.pop(0)


def _scraper(*responses) -> OrsrScraper:
    scraper = OrsrScraper()
    scraper.session = _ScriptedSession(responses)
    return scraper


class OrsrNoRecordTests(SimpleTestCase):
    """The register answering "I hold no such IČO" is an answer, not a fault.

    Measured on dell 2026-09-15: 249 companies were in this state and were being
    asked about every day, three requests each, because `fetch_by_ico` raised one
    generic `OrsrScraperError` for "the request went wrong" and for "the register
    has nothing" alike, and every call site filed both as `network`. Nothing
    about that loop could ever have succeeded. RPO was asked directly about three
    of the IČOs and returned `{"results": []}`, so the register is right.
    """

    def test_the_registers_own_sentence_is_read_as_an_absence(self):
        with self.assertRaises(OrsrNoRecordError):
            _scraper(_ScriptedResponse(_NO_RECORD_PAGE)).fetch_by_ico("31987087")

    def test_an_absence_is_a_kind_of_scraper_error(self):
        """Every `except OrsrScraperError` in the tree has to keep working.

        Three call sites catch that class to leave a record of the attempt, and
        recording a *failure* is still the right thing to do here -- it is only
        the wait and the label that change. A subclass is what buys that.
        """
        self.assertTrue(issubclass(OrsrNoRecordError, OrsrScraperError))

    def test_the_absence_costs_one_request_and_not_three(self):
        """The three spellings are the same question to a classic ASP page.

        `Request.QueryString` is case-insensitive, so `ICO`, `ico` and `Ico` are
        one request asked three times. Spending the other two after the register
        has already answered would triple the traffic of exactly the population
        this whole change is about.
        """
        scraper = _scraper(_ScriptedResponse(_NO_RECORD_PAGE))
        with self.assertRaises(OrsrNoRecordError):
            scraper.fetch_by_ico("31987087")

        self.assertEqual(len(scraper.session.calls), 1)
        self.assertEqual(scraper.session.calls[0][1], {"ICO": "31987087"})

    def test_a_contradictory_page_still_reads_as_an_absence(self):
        """The sentence beats the "does this look like an extract" heuristic.

        Both signals are ours except one: the sentence is the register's own
        statement about the entity, while `_looks_like_company_extract` is a
        guess at markup. When they disagree the register is the one that knows.
        """
        page = _NO_RECORD_PAGE + _EXTRACT_PAGE
        with self.assertRaises(OrsrNoRecordError):
            _scraper(_ScriptedResponse(page)).fetch_by_ico("31987087")

    def test_the_sentence_is_read_as_text_and_not_as_markup(self):
        """The sentence is compared as the register renders it.

        A `<b>` around one word, a `&nbsp;` between two, a newline in the middle
        -- none of those are the register changing its answer, and reading them
        as a change would put every absence quietly back on the daily retry.
        This is the test that caught exactly that: the first version of the
        predicate compared raw HTML and failed here.
        """
        page = (
            '<p class="wrn">Kritériám vyhľadávania\n'
            "        <b>nezodpovedá</b>&nbsp;žiadny záznam!</p>"
        )
        with self.assertRaises(OrsrNoRecordError):
            _scraper(_ScriptedResponse(page)).fetch_by_ico("31987087")

    def test_a_reworded_absence_stays_an_unclassified_failure(self):
        """The safe side of matching a sentence rather than a count.

        If the register rephrases, we no longer recognise the answer -- and the
        honest reading of "we do not understand this reply" is a failure to be
        retried, not a claim that the company does not exist. The opposite
        choice would take a company out of the queue for a month on a guess.
        """
        scraper = _scraper(*(_ScriptedResponse(_REWORDED_PAGE) for _ in range(3)))

        with self.assertRaises(OrsrScraperError) as caught:
            scraper.fetch_by_ico("31987087")

        self.assertNotIsInstance(caught.exception, OrsrNoRecordError)
        self.assertEqual(len(scraper.session.calls), 3)

    def test_a_company_the_register_does_carry_is_unaffected(self):
        """The control: this change must not touch the path that works."""
        scraper = _scraper(
            _ScriptedResponse(_RESULTS_PAGE),
            _ScriptedResponse(_EXTRACT_PAGE, url="https://www.orsr.sk/vypis.asp?ID=123&SID=1"),
        )

        result = scraper.fetch_by_ico("31987087")

        self.assertEqual(result.ico, "31987087")
        self.assertEqual(result.source_url, "https://www.orsr.sk/vypis.asp?ID=123&SID=1")


class OrsrNoRecordRecordingTests(TestCase):
    """Two outcomes that used to share a label, a wait and a fate.

    The label is what `source_health` groups by and what an operator reads off
    the admin column; the wait is what decides whether the company comes back
    tomorrow or next month. Both are asserted here side by side, because the
    point of the change is the *difference* between them.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=7703,
            ico="31987087",
            nazov_UJ="Cirkev Neevidovaná",
            pravna_forma="721",
        )

    def _status(self):
        return CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_ORSR
        )

    def _run(self, exc: BaseException):
        from registers.tasks import sync_company_orsr_data

        def boom(company):
            raise exc

        service = SimpleNamespace(sync_company=boom)
        with patch("registers.tasks.RpoSyncService", return_value=service):
            with self.assertRaises(type(exc)):
                sync_company_orsr_data(self.company.id)

    def test_an_absence_is_labelled_as_the_register_not_holding_it(self):
        self._run(OrsrNoRecordError("ORSR neeviduje IČO 31987087"))

        status = self._status()
        self.assertEqual(status.last_error_type, "not_in_register")
        self.assertEqual(status.consecutive_failures, 1)
        self.assertIsNone(status.last_succeeded_at)
        self.assertIn("neeviduje", status.last_error)

    def test_an_absence_waits_a_month_instead_of_a_day(self):
        """Backoff is the wrong shape for an answer that cannot change.

        30 days and not a year: ORSR refreshes its public search on its own
        schedule, so a company registered last month can be missing today and
        present next month. Re-asking ~250 companies monthly is about eight
        requests a day; the old schedule spent roughly 750 a day on it.
        """
        before = timezone.now()
        self._run(OrsrNoRecordError("ORSR neeviduje IČO 31987087"))

        next_retry_at = self._status().next_retry_at
        self.assertIsNotNone(next_retry_at)
        self.assertGreater(next_retry_at, before + timedelta(days=29))
        self.assertAlmostEqual(
            (next_retry_at - before).days, NO_RECORD_RETRY_AFTER.days, delta=1
        )

    def test_an_absence_does_not_come_back_on_the_next_batch(self):
        """What the wait is for: the retry lane must not be spent on it.

        `companies_due_for_sync('orsr')` is that lane, and it is sized at a
        fraction of each batch. A month-long `next_retry_at` is what keeps ~250
        permanently-absent companies from crowding out the ones a retry can
        actually help.
        """
        self._run(OrsrNoRecordError("ORSR neeviduje IČO 31987087"))

        self.assertNotIn(
            self.company.id, [s.company_id for s in companies_due_for_sync("orsr")]
        )

    def test_a_silent_register_is_still_a_network_failure_on_backoff(self):
        """The contrast that proves the classification is doing work.

        Same task, same company, a different exception -- and the row has to
        come out labelled and scheduled differently, or the split bought
        nothing.
        """
        before = timezone.now()
        self._run(OrsrScraperError("ORSR data pre IČO 31987087 sa nepodarilo získať."))

        status = self._status()
        self.assertEqual(status.last_error_type, "network")
        self.assertLess(status.next_retry_at, before + timedelta(days=1))


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


class OrsrNotMonitoredTests(TestCase):
    """A retry row for a company ORSR will not ask about must stop being due.

    `sync_company_orsr_data` refuses a dissolved company, or one whose legal
    form ORSR does not carry, before it makes a request -- and it used to return
    before writing anything either. `rotating_batch` draws retries on
    `next_retry_at` alone, so such a row was due in every batch from then on and
    written back by none: one of the `RETRY_SHARE` slots spent, every batch, for
    ever, on a question already answered.

    Measured 2026-09-15: 19 rows were in that state or heading for it, all of
    them companies dissolved after their last successful read and all of them
    due `2027-09`. Nothing leaked yet; the leak was what that date would have
    started.
    """

    def _status(self, company):
        return CompanySyncStatus.objects.get(
            company_id=company.id, source=CompanySyncStatus.SOURCE_ORSR
        )

    def test_a_dissolved_company_is_taken_out_of_the_lane(self):
        company, = _companies(1)
        _profile_row(company)
        CompanySyncStatus.objects.create(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            next_retry_at=timezone.now() - timedelta(hours=1),
            consecutive_failures=1,
        )
        company.datum_zrusenia = date(2026, 5, 12)
        company.save(update_fields=["datum_zrusenia"])

        with self.assertLogs("registers.tasks", level="INFO"):
            result = sync_company_orsr_data(company.id)

        status = self._status(company)
        self.assertIn("skipped", result)
        self.assertGreater(status.next_retry_at, timezone.now() + timedelta(days=300))
        self.assertIn("zrušená", status.last_detail)
        self.assertIn("12.05.2026", status.last_detail)

    def test_nothing_about_an_attempt_is_claimed(self):
        """Nothing was requested, so nothing may read as if it had been."""
        company, = _companies(1)
        _profile_row(company)
        attempted = timezone.now() - timedelta(days=400)
        CompanySyncStatus.objects.create(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            last_attempted_at=attempted,
            last_succeeded_at=attempted,
            consecutive_failures=0,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )
        company.datum_zrusenia = date(2026, 5, 12)
        company.save(update_fields=["datum_zrusenia"])

        with self.assertLogs("registers.tasks", level="INFO"):
            sync_company_orsr_data(company.id)

        status = self._status(company)
        self.assertEqual(status.last_attempted_at, attempted)
        self.assertEqual(status.last_succeeded_at, attempted)
        self.assertEqual(status.consecutive_failures, 0)
        self.assertEqual(status.last_error, "")

    def test_a_company_that_never_had_a_row_gets_none(self):
        """The `refresh_person_history` principle: a company ORSR refuses does
        not belong in the ORSR retry lane at all."""
        company, = _companies(1, pravna_forma="701")
        company.datum_zrusenia = None
        company.save(update_fields=["datum_zrusenia"])

        with self.assertLogs("registers.tasks", level="INFO"):
            sync_company_orsr_data(company.id)

        self.assertFalse(
            CompanySyncStatus.objects.filter(
                company_id=company.id, source=CompanySyncStatus.SOURCE_ORSR
            ).exists()
        )

    def test_the_reason_names_the_legal_form_when_the_company_is_not_dissolved(self):
        company, = _companies(1, pravna_forma="701")
        CompanySyncStatus.objects.create(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )

        with self.assertLogs("registers.tasks", level="INFO"):
            sync_company_orsr_data(company.id)

        self.assertIn("701", self._status(company).last_detail)

    def test_the_row_does_not_come_back_on_the_next_batch(self):
        company, = _companies(1)
        _profile_row(company)
        CompanySyncStatus.objects.create(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_ORSR,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )
        company.datum_zrusenia = date(2026, 5, 12)
        company.save(update_fields=["datum_zrusenia"])

        with self.assertLogs("registers.tasks", level="INFO"):
            sync_company_orsr_data(company.id)

        self.assertNotIn(company.id, orsr_sync_batch(20))
        self.assertEqual(
            list(companies_due_for_sync(CompanySyncStatus.SOURCE_ORSR, limit=10)), []
        )
