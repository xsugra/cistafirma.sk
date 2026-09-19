from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch, MagicMock
import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from companies.models import Company
from registers.integrations.ruz_api import RuzUnreachable
from registers.models import CompanySyncStatus, SyncJob, SyncProgress
from registers.scrapers.debt_result import DebtCheckResult
from registers.services import sync_engine


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class SyncPipelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
            pravna_forma="112",
        )

    @patch("registers.tasks.update_insurance_debt")
    @patch("registers.tasks.sync_company_orsr_data")
    @patch("registers.tasks.sync_company_financials_from_ruz")
    @patch("registers.tasks.sync_single_company_from_ruz")
    def test_orchestrate_builds_correct_workflow(
        self, mock_ruz, mock_fin, mock_orsr, mock_ins
    ):
        from registers.tasks import orchestrate_full_company_sync

        mock_ruz.si = MagicMock()
        mock_fin.si = MagicMock()
        mock_orsr.si = MagicMock()
        mock_ins.si = MagicMock()

        with patch("registers.tasks.chain") as mock_chain:
            mock_chain.return_value.apply_async = MagicMock()
            orchestrate_full_company_sync(self.company.id)

        mock_ruz.si.assert_called_once_with(self.company.ico)
        mock_fin.si.assert_called_once_with(self.company.id)
        mock_orsr.si.assert_called_once_with(self.company.id)
        mock_ins.si.assert_called_once_with(self.company.id)
        mock_chain.assert_called_once()

    @patch("registers.tasks.update_insurance_debt")
    @patch("registers.tasks.sync_company_orsr_data")
    @patch("registers.tasks.sync_company_financials_from_ruz")
    @patch("registers.tasks.sync_single_company_from_ruz")
    def test_orchestrate_skips_orsr_for_ineligible(
        self, mock_ruz, mock_fin, mock_orsr, mock_ins
    ):
        self.company.pravna_forma = "101"
        self.company.save()

        mock_ruz.si = MagicMock()
        mock_fin.si = MagicMock()
        mock_orsr.si = MagicMock()
        mock_ins.si = MagicMock()

        with patch("registers.tasks.chain") as mock_chain, \
             patch("registers.tasks.is_orsr_eligible_company", return_value=False):
            mock_chain.return_value.apply_async = MagicMock()
            from registers.tasks import orchestrate_full_company_sync
            orchestrate_full_company_sync(self.company.id)

        mock_orsr.si.assert_not_called()
        mock_fin.si.assert_called_once()

    def test_sync_company_now_delegates_to_orchestrator(self):
        with patch("registers.tasks.orchestrate_full_company_sync") as mock_orch:
            from registers.tasks import sync_company_now
            sync_company_now(self.company.id)
            mock_orch.delay.assert_called_once_with(self.company.id)

    @patch("registers.tasks.check_vszp_debt_get", return_value=DebtCheckResult.found(100.0))
    @patch("registers.tasks.check_socpoist_debt", return_value=DebtCheckResult.found(50.0))
    def test_update_insurance_debt_saves_values(self, mock_soc, mock_vszp):
        from registers.tasks import update_insurance_debt
        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()
        self.assertEqual(self.company.debt_vszp, 100.0)
        self.assertEqual(self.company.debt_soc_poist, 50.0)
        self.assertIsNotNone(self.company.last_insurance_debt)

    @patch("registers.tasks.check_vszp_debt_get", return_value=DebtCheckResult.unknown("response changed", "parse_error"))
    @patch("registers.tasks.check_socpoist_debt", return_value=DebtCheckResult.found(50.0))
    def test_update_insurance_debt_preserves_last_known_value_when_source_is_unknown(self, mock_soc, mock_vszp):
        self.company.debt_vszp = 125.0
        self.company.debt_soc_poist = 25.0
        self.company.save(update_fields=["debt_vszp", "debt_soc_poist"])

        from registers.tasks import update_insurance_debt

        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()

        self.assertEqual(self.company.debt_vszp, 125.0)
        self.assertEqual(self.company.debt_soc_poist, 50.0)
        self.assertIsNone(self.company.last_insurance_debt)
        self.assertTrue(
            self.company.sync_statuses.filter(
                source="vszp",
                last_error_type="parse_error",
                last_succeeded_at__isnull=True,
            ).exists()
        )

    def test_update_insurance_debt_raises_for_missing_company(self):
        from registers.tasks import update_insurance_debt
        with self.assertRaises(Company.DoesNotExist):
            update_insurance_debt(99999)

    # ── The SP register's second population (#141) ────────────────────────
    #
    # Sociálna poisťovňa carries two kinds of entry under one heading: employers
    # owing at least 5,00 €, and employers that did not file the výkaz poistného
    # a príspevkov (plus foreign SZČO that did not report income and expenses),
    # listed with a bare hyphen where the sum would be. Measured live 2026-09-15:
    # 43 of 50 rows carried a sum, 5 carried the hyphen and the missing periods.
    #
    # The defect these pin: the second kind parsed as `UNKNOWN`, which is not
    # authoritative, so the company was never written, `last_insurance_debt`
    # never advanced, and the row stayed in the `nulls_first` group to be
    # re-scraped every 12 hours for ever -- while the page showed it as a company
    # with no social-insurance debt, green tick and all.

    @patch("registers.tasks.check_vszp_debt_get", return_value=DebtCheckResult.not_found())
    @patch(
        "registers.tasks.check_socpoist_debt",
        return_value=DebtCheckResult.listed_without_amount(
            "Sociálna poisťovňa uvádza spoločnosť v zozname dlžníkov bez "
            "zverejnenej sumy. Chýbajúce podklady za obdobie: 01/2026 - 03/2026."
        ),
    )
    def test_a_listing_without_a_sum_settles_the_check_without_inventing_debt(
        self, mock_soc, mock_vszp
    ):
        from registers.tasks import update_insurance_debt

        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()

        # The listing is recorded, and it is not a figure. `None` and not `0`:
        # the register published no sum, and a stored zero would be a number it
        # never printed.
        self.assertTrue(self.company.social_listed_without_amount)
        self.assertIsNone(self.company.debt_soc_poist)

        # The VSZP column beside it holds a zero, and that is not a
        # contradiction -- it is the whole reason the two need separate
        # columns. That source answered `not_found`, which states outright
        # that the company is not among its debtors; a stated absence of debt
        # *is* a figure it printed, namely zero, and this column has stored it
        # that way since long before `LISTED_NO_AMOUNT` existed.
        #
        # This assertion once read `assertIsNone`, copying the line above it.
        # It was wrong about VSZP, and it survived review because the only
        # suite that runs this module needs Postgres, so it first ran on dell.
        self.assertEqual(self.company.debt_vszp, 0)

        # The point of the whole fix. An authoritative answer advances the check
        # date, which is what takes the company out of the `nulls_first` group
        # and ends the 12-hour re-scrape it was in for ever.
        self.assertIsNotNone(self.company.last_insurance_debt)

        status = self.company.sync_statuses.get(source="social")
        self.assertIsNotNone(status.last_succeeded_at)
        self.assertEqual(status.last_error, "")
        # The periods the register published, kept where a reader can find them
        # -- they are the reason for the listing and the only place it says which
        # filings are missing.
        self.assertIn("01/2026 - 03/2026", status.last_detail)
        self.assertIn("bez zverejnenej sumy", status.last_detail)

    @patch("registers.tasks.check_vszp_debt_get", return_value=DebtCheckResult.not_found())
    @patch("registers.tasks.check_socpoist_debt", return_value=DebtCheckResult.not_found())
    def test_a_clean_answer_records_that_the_company_is_not_listed(
        self, mock_soc, mock_vszp
    ):
        # `False` and not left NULL. A flag that is only ever set and never
        # cleared would make "listed" permanent -- the company would keep the
        # warning after it filed, and nothing could ever remove it.
        self.company.social_listed_without_amount = True
        self.company.save(update_fields=["social_listed_without_amount"])

        from registers.tasks import update_insurance_debt

        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()

        self.assertFalse(self.company.social_listed_without_amount)

    @patch("registers.tasks.check_vszp_debt_get", return_value=DebtCheckResult.not_found())
    @patch("registers.tasks.check_socpoist_debt", return_value=DebtCheckResult.found(50.0))
    def test_a_later_sum_replaces_the_listing(self, mock_soc, mock_vszp):
        # The register can start publishing a sum for a company it previously
        # listed without one -- a filed výkaz with an assessed debt. The amount
        # then arrives and the listing stops being true.
        self.company.social_listed_without_amount = True
        self.company.save(update_fields=["social_listed_without_amount"])

        from registers.tasks import update_insurance_debt

        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()

        self.assertEqual(self.company.debt_soc_poist, 50.0)
        self.assertFalse(self.company.social_listed_without_amount)

    @patch(
        "registers.tasks.check_vszp_debt_get",
        return_value=DebtCheckResult.unknown("response changed", "parse_error"),
    )
    @patch(
        "registers.tasks.check_socpoist_debt",
        return_value=DebtCheckResult.unknown("response changed", "parse_error"),
    )
    def test_a_failed_check_does_not_clear_a_listing_an_earlier_run_earned(
        self, mock_soc, mock_vszp
    ):
        # A parse error is not evidence of anything about the company, so it may
        # neither set nor clear the flag. Without the `is_authoritative` guard a
        # registry outage would quietly wipe a listing we had read from a page we
        # actually saw -- the reassuring direction, which is the worse one.
        self.company.social_listed_without_amount = True
        self.company.save(update_fields=["social_listed_without_amount"])

        from registers.tasks import update_insurance_debt

        update_insurance_debt(self.company.id)
        self.company.refresh_from_db()

        self.assertTrue(self.company.social_listed_without_amount)
        self.assertIsNone(self.company.last_insurance_debt)
        self.assertTrue(
            self.company.sync_statuses.filter(
                source="social",
                last_error_type="parse_error",
                last_succeeded_at__isnull=True,
            ).exists()
        )

    @patch("registers.tasks.sync_company_and_record")
    def test_sync_financials_calls_service(self, record):
        from registers.services.ruz_financials_sync import (
            FinancialsOutcome,
            FinancialsSyncResult,
        )

        record.return_value = FinancialsSyncResult(FinancialsOutcome.RECORDED, rows=5)
        from registers.tasks import sync_company_financials_from_ruz
        result = sync_company_financials_from_ruz(self.company.id)
        record.assert_called_once_with(self.company)
        self.assertIn("rows=5", result)

    def _financials_status(self):
        from registers.models import CompanySyncStatus
        return CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_FINANCIALS
        )

    def test_an_unreachable_registry_leaves_a_failure_not_a_silent_zero(self):
        """The whole path, with only the HTTP client replaced.

        Before this, the same run stored nothing at all: `CompanySyncStatus`
        had zero `financials` rows for the entire table, so "we never reached
        the registry" and "this company has no statements" were the same state
        -- and the second is what everything downstream reported.
        """
        from registers.integrations.ruz_api import RuzUnreachable
        from registers.tasks import sync_company_financials_from_ruz

        class _UnreachableRuzApi:
            def __init__(self, **_kwargs):
                pass

            def get_company_details(self, company_id):
                raise RuzUnreachable("Failed to resolve www.registeruz.sk")

        with patch("registers.services.ruz_financials_sync.RuzApi", _UnreachableRuzApi):
            result = sync_company_financials_from_ruz(self.company.id)

        status = self._financials_status()
        self.assertGreater(status.consecutive_failures, 0)
        self.assertIsNotNone(status.next_retry_at)
        self.assertEqual(status.last_error_type, "network")
        self.assertIn("unreachable", result)

    def test_a_company_with_no_statements_leaves_a_success_far_in_the_future(self):
        from registers.tasks import sync_company_financials_from_ruz

        class _EmptyRuzApi:
            def __init__(self, **_kwargs):
                pass

            def get_company_details(self, company_id):
                return {"id": company_id, "idUctovnychZavierok": []}

        with patch("registers.services.ruz_financials_sync.RuzApi", _EmptyRuzApi):
            result = sync_company_financials_from_ruz(self.company.id)

        status = self._financials_status()
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNotNone(
            status.next_retry_at,
            "a success must not clear next_retry_at -- NULL reads as 'due now', "
            "and the batch would refill with the companies it just synced",
        )
        self.assertGreater(status.next_retry_at, timezone.now() + timedelta(days=300))
        self.assertIn("no_statements", result)

    @patch("registers.tasks.RpoSyncService")
    def test_sync_orsr_calls_rpo_for_eligible(self, MockService):
        mock_profile = MagicMock()
        MockService.return_value.sync_company.return_value = mock_profile
        from registers.tasks import sync_company_orsr_data
        with patch("registers.tasks.is_orsr_eligible_company", return_value=True):
            result = sync_company_orsr_data(self.company.id)
        self.assertIn("OK", result)
        MockService.return_value.sync_company.assert_called_once_with(self.company)

    @patch("registers.tasks.RpoSyncService")
    def test_sync_orsr_skips_ineligible(self, MockService):
        from registers.tasks import sync_company_orsr_data
        with patch("registers.tasks.is_orsr_eligible_company", return_value=False):
            result = sync_company_orsr_data(self.company.id)
        self.assertIn("skipped", result)
        MockService.return_value.sync_company.assert_not_called()

    def _watch(self):
        from django.contrib.auth import get_user_model
        from companies.models import Watchlist
        from notifications.models import NotificationPreference

        user = get_user_model().objects.create_user(
            email="watcher@example.com", password="testpass123",
        )
        Watchlist.objects.create(user=user, company=self.company)
        NotificationPreference.objects.create(
            user=user, email_enabled=True, on_status_change=True,
        )

    def test_a_dissolution_survives_the_sync_being_run_twice(self):
        """The same company dissolving once must notify once.

        `_update_company_from_ruz_data` writes `datum_zrusenia` with
        `update_or_create`, which cannot see what it overwrote -- so the
        transition has to be captured by reading the old value first. If that
        read is missing, every sync re-announces every company that has ever
        been dissolved: 120k rows on the first pass, and again every 6 hours.
        """
        from notifications.models import NotificationEvent
        from registers.tasks import _update_company_from_ruz_data

        self._watch()
        data = {
            "ico": self.company.ico,
            "id": self.company.ruz_id,
            "nazovUJ": self.company.nazov_UJ,
            "datumZrusenia": "2026-03-12",
        }

        _update_company_from_ruz_data(data)
        _update_company_from_ruz_data(data)

        self.company.refresh_from_db()
        self.assertEqual(self.company.datum_zrusenia, date(2026, 3, 12))
        self.assertEqual(
            NotificationEvent.objects.filter(
                event_type=NotificationEvent.EventType.STATUS_CHANGE
            ).count(),
            1,
        )

    def test_a_company_first_seen_already_dissolved_notifies_nobody(self):
        """We never knew it as active, so there is no change to report."""
        from notifications.models import NotificationEvent
        from registers.tasks import _update_company_from_ruz_data

        self._watch()
        _update_company_from_ruz_data({
            "ico": "11111111",
            "id": 999,
            "nazovUJ": "Už zaniknutá s.r.o.",
            "datumZrusenia": "2026-03-12",
        })

        self.assertEqual(Company.objects.filter(ico="11111111").count(), 1)
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_a_sync_that_does_not_dissolve_anything_notifies_nobody(self):
        from notifications.models import NotificationEvent
        from registers.tasks import _update_company_from_ruz_data

        self._watch()
        _update_company_from_ruz_data({
            "ico": self.company.ico,
            "id": self.company.ruz_id,
            "nazovUJ": self.company.nazov_UJ,
        })

        self.assertEqual(NotificationEvent.objects.count(), 0)


class _FakeRuzApi:
    """One page of companies, then the end of the list.

    The command's own `RuzApi` is a retrying HTTP client; nothing here should
    reach the network.
    """

    def __init__(
        self,
        pages,
        unreachable_ids=(),
        unstorable_ids=(),
        long_ico_ids=(),
        duplicate_ico_ids=(),
    ):
        self._pages = list(pages)
        self.detail_calls = []
        # Ids whose detail read fails the way a strict client reports an
        # unreachable registry: by raising, not by answering `None`. The
        # command builds its client strict, so this is the shape a transport
        # failure actually takes here -- and the difference matters, because
        # `None` is filed as `skipped` with no per-company row while a raise is
        # filed as an error the window guard can see.
        self.unreachable_ids = set(unreachable_ids)
        # Ids that arrive fine but carry an IČO no column can hold: past the
        # `varchar(20)` the three IČO columns were widened to, so Postgres
        # refuses it. Deliberately not mocked as a raised DataError -- letting
        # the database refuse the real value is what proves the handler catches
        # the error Django actually raises and that the walk survives it.
        #
        # This used to be the twelve-character organisational-unit IČO
        # (`00178152` + a serial). That value is storable now, which is the
        # point of the widening, so the fixture moved to the shape that is
        # still unstorable -- see `long_ico_ids` for the other half.
        self.unstorable_ids = set(unstorable_ids)
        # Ids carrying that twelve-character IČO, the real value measured
        # 2026-09-13 at RUZ id 1520199. It reaches the walk through the same
        # code path that used to lose it, so this is what pins the widening:
        # stored, counted as created, and no error.
        self.long_ico_ids = set(long_ico_ids)
        # Ids whose IČO is already held by company 111 in the same page, so
        # whichever of the two is written second is refused by the unique index.
        # A collision, not a widening problem: the register answers one IČO with
        # more than one entity, and `update_or_create` keyed on `ico` used to
        # re-stamp the existing row's `ruz_id` instead of noticing.
        self.duplicate_ico_ids = set(duplicate_ico_ids)
        # Every `(zmenene_od, pokracovat_za_id)` pair the command asked with,
        # in order. The window and the resume cursor are the two halves of the
        # incremental sync's state, and neither is visible in the job row -- so
        # the only place a test can read them is here.
        self.window_calls = []

    def get_changed_company_ids(self, zmenene_od=None, pokracovat_za_id=None):
        self.window_calls.append((zmenene_od, pokracovat_za_id))
        if not self._pages:
            return {"id": [], "existujeDalsieId": False}
        page = self._pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return {"id": page, "existujeDalsieId": bool(self._pages)}

    def get_company_details(self, company_id):
        self.detail_calls.append(company_id)
        if company_id in self.unreachable_ids:
            raise RuzUnreachable(f"RUZ unreachable reading company {company_id}")
        if company_id in self.unstorable_ids:
            # 21 digits, one past `varchar(20)`.
            return {
                "ico": f"00178152{company_id:013d}",
                "id": company_id,
                "nazovUJ": f"SZZ Základná organizácia {company_id}",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        if company_id in self.long_ico_ids:
            return {
                "ico": "001781521576",
                "id": company_id,
                "nazovUJ": f"SZZ Základná organizácia {company_id}",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        if company_id in self.duplicate_ico_ids:
            # `9{111:07d}` is what id 111 in the same page holds.
            return {
                "ico": "90000111",
                "id": company_id,
                "nazovUJ": f"Firma {company_id}",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        return {
            "ico": f"9{company_id:07d}",
            "id": company_id,
            "nazovUJ": f"Firma {company_id}",
            "pravnaForma": "112",
            "datumZalozenia": "2020-01-01",
        }


class RuzCommandHeartbeatTests(TestCase):
    """The beat that makes the watchdog safe to switch on.

    `detect_and_fail_stuck_jobs` treats a stale heartbeat as death, so the RUZ
    command has to write one -- it never did, which is why wiring the reaper up
    unchanged would have failed every healthy multi-hour import instead of the
    dead job it was written for. These tests are what keeps that ordering from
    silently reverting.
    """

    def _job(self, **kwargs):
        # No `concurrency_key`: these tests are about the heartbeat and the
        # per-run counters, and the partial unique index that guards the RUZ
        # singleton allows only one live holder at a time -- which
        # `tests_sync_job_singleton.py` owns.
        defaults = {
            "job_type": "ruz_incremental",
            "status": "running",
            "started_at": timezone.now(),
            "last_heartbeat": timezone.now(),
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _run(self, job, pages):
        api = _FakeRuzApi(pages)
        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi", return_value=api
        ):
            call_command(
                "fetch_ruz_data", sync_job_id=job.pk, stdout=StringIO(), stderr=StringIO()
            )
        return api

    def test_the_run_beats_its_own_heart(self):
        """Without this the job looks dead from the instant it starts."""
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)

        self._run(job, [[111, 222]])

        job.refresh_from_db()
        self.assertGreater(job.last_heartbeat, stale + timedelta(hours=2))

    def test_a_running_import_is_not_stuck_while_it_is_working(self):
        """The property the watchdog depends on, asserted against the reaper
        itself rather than against a timestamp: a live run must not be a
        candidate for reaping."""
        job = self._job(last_heartbeat=timezone.now() - timedelta(hours=3))

        self._run(job, [[111, 222]])

        job.refresh_from_db()
        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 0)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_the_gap_between_beats_is_a_clock_not_a_record_count(self):
        """The gate has to survive slow records, not only ordinary ones.

        It used to be `index % 50`, and a count of records bounds the gap only
        while a record costs about what a record usually costs. It does not:
        `RUZApi` builds its session with `Retry(total=4, backoff_factor=0.6)`
        over a 20s timeout, so one read against a register that is answering
        slowly occupies five attempts and around 110s before it raises -- and
        fifty of those is over ninety minutes, three times what
        `detect_and_fail_stuck_jobs` reaps on. A healthy walk inside a register
        outage would have been failed underneath itself by the watchdog written
        to protect it, and the keeper would then have had nothing to resume.

        The slowness is simulated on the clock rather than slept through: each
        record costs 60s of wall clock, so the count-based gate it replaced
        would leave a 50-minute hole where this one leaves one of a minute.
        """
        record_seconds = 60.0
        clock = [0.0]
        beats = []
        job = self._job()

        def _slow_sleep(_seconds):
            clock[0] += record_seconds

        def _record_beat(_job_row):
            beats.append(clock[0])

        with patch("time.sleep", side_effect=_slow_sleep), patch.object(
            sync_engine.time, "monotonic", lambda: clock[0]
        ), patch.object(SyncJob, "heartbeat", _record_beat):
            self._run(job, [list(range(1000, 1120))])

        self.assertGreater(len(beats), 1, "the run recorded no heartbeat at all")

        worst = max(b - a for a, b in zip(beats, beats[1:]))
        self.assertLess(
            worst,
            sync_engine.stuck_heartbeat_threshold().total_seconds(),
            "a beat gap reached the threshold the watchdog reaps on",
        )
        # And not merely under it: one interval plus one record is the honest
        # ceiling, with the rest of the threshold left as headroom.
        self.assertLessEqual(
            worst, sync_engine.HEARTBEAT_INTERVAL_SECONDS + record_seconds
        )

    def test_a_walk_whose_job_row_is_gone_refuses_to_start(self):
        """A walk that cannot beat its heart is one the watchdog later fails.

        With no row there is no heartbeat at all, and `set_job_outcome` is a
        `filter(pk=...).update()` -- which reports nothing when the row it
        writes to has vanished. The run would import into `SyncProgress` while
        the keeper, seeing no live job, dispatched a second walk over the same
        window. Refusing is the only outcome that does not lie.
        """
        with self.assertRaises(CommandError):
            call_command(
                "fetch_ruz_data",
                sync_job_id=999_999,
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_the_run_records_what_it_actually_did(self):
        """`processed_items=0` on a run that created companies is the defect
        this counter exists to remove."""
        job = self._job()

        self._run(job, [[111, 222, 333]])

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 3)
        self.assertEqual(job.succeeded_items, 3)
        self.assertEqual(job.failed_items, 0)
        self.assertEqual(Company.objects.filter(ruz_id__in=[111, 222, 333]).count(), 3)

    def test_the_counters_describe_this_run_not_every_run_before_it(self):
        """`SyncProgress` accumulates across runs -- it reuses its row and
        `start()` resets only `started_at` -- so it cannot answer what the last
        run did. That is why the outcome lives on the job instead, and why it
        must not inherit the old total."""
        job = self._job()

        self._run(job, [[111, 222, 333]])
        job.refresh_from_db()
        self.assertEqual(job.processed_items, 3)

        second = self._job()
        self._run(second, [[444, 555]])

        second.refresh_from_db()
        self.assertEqual(second.processed_items, 2)

    def test_recording_the_outcome_never_writes_the_status(self):
        """`status` belongs to the lifecycle (`complete_job` / `fail_job`).

        This run does not own the job -- it was dispatched with an explicit
        `sync_job_id` -- so the row must come out of it exactly as running as
        it went in. A second writer of `status` is how a job gets marked
        `completed` before anyone has decided it is.
        """
        job = self._job()

        self._run(job, [[111, 222]])

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertIsNone(job.completed_at)

    def test_one_bad_company_is_counted_not_swallowed(self):
        """A record that blows up must not kill the other 439 999.

        The per-company handler catches everything and counts it, which is
        deliberate for a bulk import -- but it means the *only* trace of a
        failure is the counter. If `failed_items` were not recorded, a run
        that threw away a tenth of its batch would look identical to a clean
        one.
        """
        job = self._job()
        api = _FakeRuzApi([[111, 222]])
        good = {
            "ico": "90000001",
            "id": 111,
            "nazovUJ": "Firma 111",
            "pravnaForma": "112",
        }
        api.get_company_details = MagicMock(side_effect=[good, RuntimeError("boom")])

        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi", return_value=api
        ):
            call_command(
                "fetch_ruz_data",
                sync_job_id=job.pk,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.succeeded_items, 1)
        self.assertEqual(job.failed_items, 1)
        self.assertEqual(Company.objects.filter(ico="90000001").count(), 1)

    def test_a_run_that_dies_midway_still_records_what_it_managed(self):
        """The `finally` exists so a truncated run is still legible.

        A crash used to leave the counters at zero, which reads exactly like a
        run that did nothing -- and a job reporting zero cannot be told from
        one that silently processed nothing.
        """
        job = self._job()

        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi",
            return_value=_FakeRuzApi([[111, 222], RuntimeError("connection reset")]),
        ):
            with self.assertRaises(RuntimeError):
                call_command(
                    "fetch_ruz_data",
                    sync_job_id=job.pk,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.succeeded_items, 2)


class RuzTransportFailureTests(TestCase):
    """An unreachable registry must not read as an empty one.

    The import loop ends on a falsy page, and `get_changed_company_ids` used to
    answer `None` both for "nothing has changed" and for "we could not ask", so
    a transport failure on the *first* call took the loop's success path: it
    printed `No more company IDs to fetch.`, ran `progress.complete()` and
    stored the whole run as `completed` with `processed_items=0`. Two beat runs
    did exactly that on 2026-09-11 (jobs #13 and #14), each re-requesting the
    same page and fetching nothing.
    """

    def _job(self):
        return SyncJob.objects.create(
            job_type="ruz_incremental",
            status="running",
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
        )

    def test_the_client_raises_rather_than_answering_none(self):
        """The value a caller reads as "nothing further" must not also mean
        "could not ask" -- the two answers need two values."""
        from registers.integrations.ruz_api import RuzApi

        api = RuzApi()
        with patch.object(
            RuzApi,
            "_get_json",
            side_effect=requests.exceptions.ConnectionError("Failed to resolve host"),
        ):
            with self.assertRaises(requests.exceptions.RequestException):
                api.get_changed_company_ids(zmenene_od="2026-08-04")

    def test_a_transport_failure_on_the_first_call_fails_the_run(self):
        """End to end, on the real client rather than a stub that raises for
        us: if `get_changed_company_ids` went back to answering `None`, it is
        this test -- not the loop's own failure handling -- that would notice.
        """
        from registers.integrations.ruz_api import RuzApi

        job = self._job()
        out = StringIO()

        with patch.object(
            RuzApi,
            "_get_json",
            side_effect=requests.exceptions.ConnectionError(
                "Failed to resolve www.registeruz.sk"
            ),
        ), patch(
            "registers.management.commands.fetch_ruz_data.RuzApi",
            return_value=RuzApi(),
        ):
            with self.assertRaises(requests.exceptions.RequestException):
                call_command(
                    "fetch_ruz_data",
                    sync_job_id=job.pk,
                    stdout=out,
                    stderr=StringIO(),
                )

        self.assertNotIn("No more company IDs to fetch.", out.getvalue())
        self.assertEqual(
            SyncProgress.objects.get(sync_type="incremental").status, "failed"
        )

    def test_an_empty_page_still_ends_the_run_as_completed(self):
        """The other half of the same rule, and the reason the fix is in the
        client rather than in the loop: a registry with nothing new is a normal
        run -- five beat runs a day look exactly like this -- and must not
        start failing."""
        job = self._job()
        api = _FakeRuzApi([])
        out = StringIO()

        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi", return_value=api
        ):
            call_command(
                "fetch_ruz_data", sync_job_id=job.pk, stdout=out, stderr=StringIO()
            )

        self.assertIn("No more company IDs to fetch.", out.getvalue())
        self.assertEqual(
            SyncProgress.objects.get(sync_type="incremental").status, "completed"
        )


class RuzIncrementalWindowTests(TestCase):
    """The two halves of the incremental sync's state, and why they move together.

    `SyncProgress.zmenene_od` is the window the sync reads through and
    `last_processed_ruz_id` is where a walk got to. The job row records neither,
    so a run that does nothing looks exactly like a run with nothing to do --
    which is how ten beat runs reported `completed, 0 items` over three days
    while the register changed underneath them.

    From 2026-09-11 the beat run resumed from a cursor the previous run had left
    at the *end of its own window*, asked RUZ for changes past that point, got an
    empty page, and read it as "reached the end". Verified against the live
    register: `zmenene-od=2026-08-04` alone returned 1000 ids; the same request
    with `pokracovat-za-id=2624307` returned none.
    """

    def _job(self):
        return SyncJob.objects.create(
            job_type="ruz_incremental",
            status="running",
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
        )

    def _progress(self, **kwargs):
        defaults = {
            "sync_type": "incremental",
            "status": "completed",
            "zmenene_od": timezone.localdate() - timedelta(days=40),
        }
        defaults.update(kwargs)
        return SyncProgress.objects.create(**defaults)

    def _run(self, api, job, **extra):
        out = StringIO()
        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi", return_value=api
        ):
            call_command(
                "fetch_ruz_data",
                sync_job_id=job.pk,
                stdout=out,
                stderr=StringIO(),
                **extra,
            )
        return out.getvalue()

    def test_a_fresh_run_does_not_resume_from_a_previous_runs_cursor(self):
        """The defect itself. A cursor left by a *finished* run describes a list
        that no longer exists, and asking past its end is what turned a working
        sync into a no-op that reported success."""
        self._progress(last_processed_ruz_id=2624307)
        api = _FakeRuzApi([[111]])

        self._run(api, self._job())

        self.assertEqual(api.window_calls[0][1], None)

    def test_a_completed_walk_moves_the_window_forward(self):
        """The other half. Clearing the cursor without moving the window would
        have every beat run re-scan everything back to 2026-08-04; leaving the
        window alone -- as it was -- is what made the stall permanent."""
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111]])

        self._run(api, self._job())

        progress.refresh_from_db()
        self.assertEqual(
            progress.zmenene_od, timezone.localdate() - timedelta(days=1)
        )

    def test_the_window_carries_a_day_of_overlap(self):
        """`zmenene_od` is a `DateField`, so a day is the finest cursor we can
        store. A company that changed in the window's final hours, after the
        page carrying its id had been read, would otherwise fall between two
        windows and never be seen at all.

        Pinned to the exact day rather than to "some day in the past": the
        loose form of this assert passed even with the advance block deleted,
        because the row was seeded with 2026-08-04 and that is already behind
        today.
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111]])

        self._run(api, self._job())

        progress.refresh_from_db()
        self.assertEqual(
            progress.zmenene_od, timezone.localdate() - timedelta(days=1)
        )

    def test_the_window_never_moves_backwards(self):
        """A window already at or ahead of the advance target must not be pulled
        back. Within one day the target is constant (`today - 1`), so a second
        run on the same day would otherwise rewrite the same value, and a window
        someone had already moved further forward would be dragged behind where
        it was -- re-reading days already covered, or skipping them.

        This pins the `>` in the advance, not the advance itself: `start()`
        writes back the run's own window, so the asserted value would survive
        deleting the advance block entirely. The block's existence is
        `test_the_window_carries_a_day_of_overlap`'s job, which is seeded
        behind and therefore does fail without it. Both are needed; neither
        covers the other.
        """
        today = timezone.localdate()
        progress = self._progress(zmenene_od=today)
        api = _FakeRuzApi([[111]])

        self._run(api, self._job())

        progress.refresh_from_db()
        self.assertEqual(progress.zmenene_od, today)

    def test_an_unreachable_company_holds_the_window(self):
        """Moving the window asserts that everything inside it was read. A
        company whose read failed gets no per-company row at all, so the window
        is the only thing that remembers it was skipped -- and advancing would
        drop it silently and permanently, which is the defect class this file
        exists to close, not one to reintroduce through the fix.

        The run still finishes; what it must not do is claim to have read what
        it did not. `skipped` is deliberately not treated this way: the register
        answering "no such record" is a fact about the company, and re-reading
        it forever would be the stall this window advance was written to end.
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111, 222]], unreachable_ids={222})

        out = self._run(api, self._job())

        progress.refresh_from_db()
        self.assertIn("Okno neposunuté", out)
        self.assertEqual(progress.zmenene_od, date(2026, 8, 4))

    def test_a_record_we_cannot_store_does_not_hold_the_window(self):
        """The mirror of the test above, and the reason the two failures are
        counted apart.

        A record whose read failed is a hole, and holding the window is the
        only thing that stops it being lost. A record that arrived and cannot be
        stored is the opposite: re-reading returns the same value, so holding
        the window would never repair it -- it would re-read everything inside
        it on every run, forever, and pin the gate red. Measured live on
        2026-09-13: one such record held a 47 800-item window.

        The value is real rather than mocked: an IČO past the column's width,
        which Postgres itself refuses. That is what proves the handler catches
        what Django actually raises and that the walk survives it. The twelve-
        character organisational-unit IČO that produced the live failure is no
        longer unstorable -- see `test_a_long_organisational_unit_ico_is_stored`
        for that half.
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111, 222]], unstorable_ids={222})

        out = self._run(api, self._job())

        progress.refresh_from_db()
        # Not held: the walk read it, and nothing about it changes on a re-read.
        self.assertNotIn("Okno neposunuté", out)
        self.assertEqual(
            progress.zmenene_od, timezone.localdate() - timedelta(days=1)
        )
        # And not silent either -- it leaves no row anywhere, so the run has to
        # name it or the hole is invisible.
        self.assertIn("Unstorable", out)
        self.assertIn("222", progress.notes)

    def test_a_new_ledger_does_not_erase_the_previous_one(self):
        """The ledger is the only trace a skipped record leaves, and it is
        written on the row that survives -- which is the entire reason it is
        written there. A five-day `full` walk is resumed by the keeper dozens of
        times, so a plain assignment left one segment's ledger on the row and
        destroyed every earlier one: a mechanism built to be read later could
        only ever be read once.

        Seeded rather than driven by two runs on purpose. A finished row is
        neither `running` nor `idle`, so a second run creates its own
        `SyncProgress` row -- the assertion would then be about two rows instead
        of about the single row the keeper keeps returning to.
        """
        progress = self._progress(
            zmenene_od=date(2026, 8, 4),
            notes='1 záznamov sa nedalo uložiť, okno ich preskočilo: 999',
        )
        api = _FakeRuzApi([[111, 222]], unstorable_ids={222})

        self._run(api, self._job())

        progress.refresh_from_db()
        # This segment's ledger is there ...
        self.assertIn("222", progress.notes)
        # ... and it did not replace the one that was already on the row.
        self.assertIn("999", progress.notes)

    def test_the_note_ledger_is_bounded_and_says_that_it_is(self):
        """`notes` is a `TextField` the admin loads whole, and the keeper appends
        to it for days, so it needs a bound.

        The bound has to be *named in the field*: a ledger that is silently
        trimmed reads exactly like a run in which nothing was skipped, and this
        field exists precisely so that a skipped record is not invisible.
        """
        progress = self._progress()
        total = SyncProgress.NOTES_KEEP_BLOCKS + 4
        for i in range(total):
            progress.append_notes(f"blok {i}")

        blocks = progress.notes.split("\n\n")
        self.assertEqual(len(blocks), SyncProgress.NOTES_KEEP_BLOCKS)
        self.assertIn("5 starších blokov odstránených", blocks[0])
        # The newest block is the one just appended -- the trim is at the front.
        self.assertEqual(blocks[-1], f"blok {total - 1}")

    def test_a_record_we_cannot_store_does_not_stop_the_walk(self):
        """One bad record must not cost the rest of the page.

        Live, a single record failed and the walk went on to finish the window.
        That depends on the failed write rolling back to a savepoint rather than
        poisoning the connection -- if `update_or_create`'s atomic block did not
        contain it, every later company in the run would fail too, and the
        damage would look like a registry outage.
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111, 222, 333]], unstorable_ids={222})

        out = self._run(api, self._job())

        progress.refresh_from_db()
        self.assertIn("Unstorable: 1", out)
        # 111 and 333 stored; only 222 was refused.
        self.assertEqual(
            Company.objects.filter(ruz_id__in=[111, 333]).count(), 2
        )
        self.assertFalse(Company.objects.filter(ruz_id=222).exists())

    def test_a_duplicate_ico_is_unstorable_rather_than_identity_swapping(self):
        """A unique-index refusal has to be filed like an over-long value.

        `update_or_create(ico=..., defaults={'ruz_id': ...})` matches the row by
        IČO and then re-stamps its `ruz_id`. When a second RUZ entity arrives
        under an IČO we already hold, that call does not fail -- it *succeeds*,
        and the row that was entity A now claims to be entity B. Silent identity
        swapping, and the reason the walk is keyed on `ruz_id` instead.

        Keyed on `ruz_id`, the collision surfaces as an `IntegrityError` from the
        unique index. Filed as `unreadable` it would hold the window forever --
        the re-read returns the same collision, so it would never clear -- which
        is the exact failure this window guard was written to end. So it is
        `unstorable`: named, counted, and the window moves.

        The first entity is left intact. That is the assertion that separates
        "refused the new one" from "overwrote the old one".
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111, 222]], duplicate_ico_ids={222})

        out = self._run(api, self._job())

        progress.refresh_from_db()
        self.assertIn("Unstorable: 1", out)
        self.assertIn("Unstorable", out)
        self.assertIn("222", progress.notes)
        # Not held: this collision is deterministic, so the re-read repairs
        # nothing.
        self.assertNotIn("Okno neposunuté", out)
        self.assertEqual(
            progress.zmenene_od, timezone.localdate() - timedelta(days=1)
        )
        # 111 kept its row and its identity; 222 got nothing.
        self.assertEqual(Company.objects.get(ico="90000111").ruz_id, 111)
        self.assertFalse(Company.objects.filter(ruz_id=222).exists())

    def test_a_long_organisational_unit_ico_is_stored(self):
        """The other half of the widening: the record that used to be lost.

        RUZ id 1520199 carries `001781521576` -- twelve digits, the parent's
        `00178152` plus a serial -- and `varchar(8)` refused it. It was counted
        as a failure and the window moved past it, which is how one unreadable
        record became 13 missing statements.

        Asserted on the stored value and not just on the absence of an error:
        a run that stored a *truncated* IČO would also report no error, and the
        company would then be unfindable by the IČO its owner quotes.
        """
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([[111, 222]], long_ico_ids={222})

        out = self._run(api, self._job())

        progress.refresh_from_db()
        self.assertNotIn("Unstorable", out)
        self.assertNotIn("Okno neposunuté", out)
        self.assertEqual(
            Company.objects.get(ruz_id=222).ico, "001781521576"
        )

    def test_a_full_run_does_not_move_its_own_window(self):
        """The `full*` types pick their start elsewhere: `full` hardcodes
        2000-01-01, while `full_companies` and `full_individuals` read it back
        out of this very column. Writing the incremental advance's `today - 1`
        into the column a full resync reads would shrink the next one to a
        single day -- so the advance belongs to the incremental walk alone.

        Pinned on the stored start rather than on the absence of an advance,
        because "did not advance" and "advanced to the same value" are the two
        ways this could be wrong and only the stored value separates them.
        """
        progress = self._progress(sync_type="full_companies", zmenene_od=None)
        api = _FakeRuzApi([[111]])

        out = self._run(api, self._job(), full_resync=True, entity_type="companies")

        progress.refresh_from_db()
        self.assertIn("Okno neposunuté", out)
        self.assertEqual(progress.zmenene_od, date(2020, 1, 1))

    def test_resume_still_picks_up_the_stored_cursor(self):
        """The cursor is not wrong, it is *scoped*: it belongs to a run that was
        interrupted and is being continued. `--resume` is the only path that
        may use it, and this keeps the fix from taking that away."""
        self._progress(
            status="paused",
            last_processed_ruz_id=4242,
            zmenene_od=timezone.localdate() - timedelta(days=40),
        )
        api = _FakeRuzApi([[111]])

        self._run(api, self._job(), resume=True)

        self.assertEqual(api.window_calls[0][1], 4242)

    def test_an_empty_registry_still_ends_the_run_as_completed(self):
        """A window with genuinely nothing in it is a normal run -- most beat
        runs look like this -- and must not be turned into a failure by the
        fix. What made the stall invisible was never the empty page; it was
        that the page was empty *and* the window never moved."""
        progress = self._progress(zmenene_od=date(2026, 8, 4))
        api = _FakeRuzApi([])

        self._run(api, self._job())

        progress.refresh_from_db()
        self.assertEqual(progress.status, "completed")
        self.assertEqual(
            progress.zmenene_od, timezone.localdate() - timedelta(days=1)
        )


class SyncProgressErrorReasonTests(TestCase):
    """Why an item failed has to be readable *while* the run is running.

    `record_progress` writes every hundredth item, and the two callers that file
    a failed item used to assign `progress.last_error` *after* calling it -- so
    the message was set on an instance whose save had already happened. The row
    then climbed to `total_errors=57` with an empty `last_error`, and the only
    copy of the reason was a stderr line in a container log.

    The end of a run papers over this: `complete()`, `pause()` and `fail()` all
    call a full `save()`, so a *finished* row does carry the last reason. That is
    exactly why this is asserted mid-run, on the throttled save -- a test placed
    after the walk would have passed with the defect still in place. Observed
    live on the full walk, 2026-09-18: `total_errors=1`, `last_error` empty.
    """

    def _progress(self):
        return SyncProgress.objects.create(sync_type="incremental", status="running")

    def test_a_failed_item_leaves_its_reason_on_the_row(self):
        progress = self._progress()
        reason = (
            'duplicate key value violates unique constraint '
            '"Companies and SZCO_ICO_key"'
        )

        progress.record_progress(ruz_id=491, error=True, error_message=reason)
        # Up to the hundredth item, which is what triggers the write. The reason
        # was recorded on the first one, so a save that omits it loses it.
        for ruz_id in range(492, 591):
            progress.record_progress(ruz_id=ruz_id)

        stored = SyncProgress.objects.get(pk=progress.pk)
        self.assertEqual(stored.total_errors, 1)
        self.assertEqual(stored.last_error, reason)

    def test_a_later_success_does_not_erase_the_reason(self):
        """The write lands on every hundredth item, so it usually arrives well
        after the error it is meant to record. A save that only carried the
        reason when its *own* item had failed would drop it here."""
        progress = self._progress()

        progress.record_progress(ruz_id=491, error=True, error_message="refused")
        for ruz_id in range(492, 591):
            progress.record_progress(ruz_id=ruz_id)

        stored = SyncProgress.objects.get(pk=progress.pk)
        self.assertEqual(stored.last_error, "refused")
        self.assertEqual(stored.total_processed, 100)


class RuzDateGuardTests(TestCase):
    """A date we cannot read must not erase a date we already hold.

    `parse_date` answers `None` both for a field RUZ omitted and for one it
    sent in a shape we cannot read, and both writers stored that `None`
    alike. For `datum_zrusenia` an upstream format change would therefore
    erase every dissolution date at once -- and the sync that followed the
    fix would restore all of them as dissolution notifications, through the
    feature `detect_status_change` exists to serve.

    Measured against the live API on 2026-09-10 before touching anything:
    20/20 dissolved records carry `datumZrusenia`, 8/8 active ones omit it.
    The format has not changed and nothing has been lost. These tests are
    what keeps that from mattering if it ever does.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=111,
            ico="90000111",
            nazov_UJ="Zrušená s.r.o.",
            datum_zrusenia=date(2026, 3, 12),
        )

    def _watch(self):
        from django.contrib.auth import get_user_model
        from companies.models import Watchlist
        from notifications.models import NotificationPreference

        watcher = get_user_model().objects.create_user(
            email="watcher@example.com", password="testpass123",
        )
        Watchlist.objects.create(user=watcher, company=self.company)
        NotificationPreference.objects.create(
            user=watcher, email_enabled=True, on_status_change=True,
        )

    def _record(self, **overrides):
        data = {
            "ico": self.company.ico,
            "id": self.company.ruz_id,
            "nazovUJ": self.company.nazov_UJ,
        }
        data.update(overrides)
        return data

    def test_a_parsed_date_is_written_as_before(self):
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data(self._record(datumZrusenia="2026-04-01"))

        self.company.refresh_from_db()
        self.assertEqual(self.company.datum_zrusenia, date(2026, 4, 1))

    def test_an_absent_date_still_clears_the_stored_one(self):
        """The guard has to stay narrow.

        RUZ says "not dissolved" by omitting the key, so absence is a
        statement and must land -- otherwise a revoked dissolution could
        never clear, and the company would read as dissolved forever.
        """
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data(self._record())

        self.company.refresh_from_db()
        self.assertIsNone(self.company.datum_zrusenia)

    def test_an_unreadable_date_does_not_erase_the_stored_one(self):
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        self.company.refresh_from_db()
        self.assertEqual(self.company.datum_zrusenia, date(2026, 3, 12))

    def test_an_unreadable_date_says_which_value_it_could_not_read(self):
        """An operator has to be able to tell a format change from a typo
        without going to the API by hand."""
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR") as logs:
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        self.assertEqual(len(logs.records), 1)
        message = logs.records[0].getMessage()
        self.assertIn("datumZrusenia", message)
        self.assertIn("12.03.2026", message)
        self.assertIn(self.company.ico, message)

    def test_an_unreadable_date_is_not_announced_as_a_dissolution(self):
        """The caller has to pass the value it *meant* to write.

        `detect_status_change` is told the old value by a pre-read that only
        happens when the record carries a dissolution date. Handing it
        `company.datum_zrusenia` instead -- the row, read back -- means that
        when `apply_ruz_dates` declines to write an unreadable value, the
        untouched stored date is reported as new, with `old=None`, and every
        watcher is told about a dissolution that did not happen. That is the
        failure this whole guard exists to prevent, arriving by the back door.
        """
        from notifications.models import NotificationEvent
        from registers.tasks import _update_company_from_ruz_data

        self._watch()

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_a_format_change_cannot_produce_a_false_dissolution(self):
        """The whole point, end to end.

        A watcher is told about a dissolution once. If a format change erased
        the date and the next sync restored it, they would be told again --
        for a company that never stopped being dissolved.
        """
        from notifications.models import NotificationEvent
        from registers.tasks import _update_company_from_ruz_data

        self._watch()

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))
        _update_company_from_ruz_data(self._record(datumZrusenia="2026-03-12"))

        self.company.refresh_from_db()
        self.assertEqual(self.company.datum_zrusenia, date(2026, 3, 12))
        self.assertEqual(
            NotificationEvent.objects.filter(
                event_type=NotificationEvent.EventType.STATUS_CHANGE
            ).count(),
            0,
        )

    def test_a_refused_date_reaches_the_source_health_gate(self):
        """A refusal that only logs is not a control.

        `source_health` judges a source on whether it produced a usable
        answer, and a date-format change is exactly "records arrived, and not
        one of them usable". Recording the refusal against `ruz` is what lets
        `make ops-check` reach that verdict; without it the guard's failure
        mode is a JSON line nobody queries, and the gate reports SATISFIED
        throughout a mass erasure.
        """
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.last_error_type, "parse_error")
        self.assertIn("datumZrusenia", status.last_error)
        self.assertIsNone(status.last_succeeded_at)

    def test_a_refused_date_is_counted_so_the_admin_screens_can_see_it(self):
        """The refusal has to reach the readers that key on the failure count.

        The gate was never the only audience. `adminapi`'s dashboard builds
        `failures_24h` and its per-source card from `consecutive_failures`, and
        so do the company filters and the lead-scoring average -- all four read
        that column and nothing else. A refusal written without incrementing it
        left `ruz` looking immaculate everywhere a human looks, while the one
        screen that could see it said only how many records were affected and
        never which company. This asserts the count, because the count is what
        the four readers actually consume.
        """
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.consecutive_failures, 1)

        # Exactly the dashboard's `failures_24h` query, run against the row the
        # sync just wrote.
        self.assertEqual(
            CompanySyncStatus.objects.filter(
                last_attempted_at__gte=timezone.now() - timedelta(hours=24),
                consecutive_failures__gt=0,
            ).count(),
            1,
        )

    def test_two_refused_fields_are_one_attempt_not_two(self):
        """A record refusing two dates is one bad record, not two failures.

        The refusal used to be written one field per call, which was harmless
        only because nothing incremented a counter. Routing it through the
        shared attempt path makes the count load-bearing: per-field writes
        would count one malformed record twice, and the backoff that
        `next_retry_at` derives from the count would grow on a phantom.
        """
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(
                self._record(datumZrusenia="12.03.2026", datumZalozenia="01.01.2020")
            )

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.consecutive_failures, 1)
        self.assertIn("datumZrusenia", status.last_error)
        self.assertIn("datumZalozenia", status.last_error)

    def test_a_clean_sync_records_a_success_so_a_refusal_can_clear(self):
        """The success path is what makes writing the failure honest.

        `ruz` used to write a row only when it refused a field and never a
        success, and that was deliberate: with nothing able to reset the count,
        a written failure would accumulate on every re-fetch of the same
        company with `next_retry_at` backing off towards its 24h cap -- a trap
        for whichever reader trusted it next. So this asserts both halves of
        the trade: the row exists, and it says the company is healthy.
        """
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data(self._record(datumZrusenia="2026-04-01"))

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNotNone(status.last_succeeded_at)
        self.assertEqual(status.last_error, "")
        self.assertIsNone(status.next_retry_at)

    def test_a_later_clean_sync_clears_an_earlier_refusal(self):
        """A refusal is a state, not a scar.

        `source_health` counts a company as refusing only while
        `consecutive_failures` is above zero, so an upstream typo that is fixed
        has to stop counting -- otherwise the gate stays red for a format
        change that is over, and the alarm stops being read.
        """
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))
        _update_company_from_ruz_data(self._record(datumZrusenia="2026-03-12"))

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.consecutive_failures, 0)
        self.assertEqual(status.last_error_type, "")
        self.assertIsNotNone(status.last_succeeded_at)

    def test_the_command_writer_is_guarded_too(self):
        """`fetch_ruz_data` is the one that runs every six hours; it maps the
        same payload by hand and had the same hole."""
        job = SyncJob.objects.create(
            job_type="ruz_incremental",
            status="running",
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
        )
        api = _FakeRuzApi([[self.company.ruz_id]])
        api.get_company_details = MagicMock(return_value={
            "ico": self.company.ico,
            "id": self.company.ruz_id,
            "nazovUJ": self.company.nazov_UJ,
            "datumZrusenia": "12.03.2026",
        })

        with patch(
            "registers.management.commands.fetch_ruz_data.RuzApi", return_value=api
        ):
            with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
                call_command(
                    "fetch_ruz_data",
                    sync_job_id=job.pk,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        self.company.refresh_from_db()
        self.assertEqual(self.company.datum_zrusenia, date(2026, 3, 12))


class RefusedDatesReachTheGateTests(TestCase):
    """The verdict, not the mechanism.

    `source_health` fails a source that made `min_attempts` attempts in the
    window and produced no successful answer at all. A date-format change is
    exactly that shape, so this asserts the end of the chain the guard starts:
    `make ops-check` goes red instead of reporting SATISFIED while dates are
    being erased. Without this the guard's failure mode would be a JSON line
    nobody queries -- the defect class this repo keeps paying for.
    """

    MIN_ATTEMPTS = 200

    # The sources `source_health` now expects to attempt, and fails for silence.
    # This class is about `ruz`, so the rest get a healthy baseline in `setUp` --
    # otherwise every assertion below would be reading four unrelated FAILs.
    # Not a change of subject: the command was made to name every declared
    # source, and these tests pin the verdict for one of them.
    OTHER_SOURCES = ("orsr", "financials", "vszp", "social")

    def setUp(self):
        now = timezone.now()
        statuses = []
        for index, source in enumerate(self.OTHER_SOURCES):
            # `vszp` and `social` are judged on the found / no-record split as
            # well as on having a success, so the baseline has to carry both.
            amount_field = {"vszp": "debt_vszp", "social": "debt_soc_poist"}.get(source)
            companies = Company.objects.bulk_create([
                Company(
                    ruz_id=900000 + index * 1000 + i,
                    ico=f"7{index}{i:06d}",
                    nazov_UJ=f"Baseline {source} {i}",
                    **({amount_field: Decimal("100.00") if i < 25 else Decimal("0.00")}
                       if amount_field else {}),
                )
                for i in range(self.MIN_ATTEMPTS)
            ])
            statuses.extend(
                CompanySyncStatus(
                    company=company,
                    source=source,
                    last_attempted_at=now - timedelta(hours=1),
                    last_succeeded_at=now - timedelta(hours=1),
                )
                for company in companies
            )
        CompanySyncStatus.objects.bulk_create(statuses)

    def test_enough_unreadable_dates_fail_the_source_health_gate(self):
        from registers.tasks import _update_company_from_ruz_data

        for index in range(self.MIN_ATTEMPTS):
            _update_company_from_ruz_data({
                "ico": f"8{index:07d}",
                "id": 100000 + index,
                "nazovUJ": f"Firma {index}",
                "datumZrusenia": "12.03.2026",
            })

        with self.assertRaises(SystemExit) as exit_info:
            call_command("source_health", skip_checks=True)

        self.assertEqual(exit_info.exception.code, 1)

    def test_one_malformed_record_is_reported_but_not_judged(self):
        """The threshold has to keep its meaning.

        A single upstream typo must not hold the gate red forever, or the
        alarm stops being read -- so below `min_attempts` the count is shown
        and left alone.
        """
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data({
            "ico": "80000001",
            "id": 100001,
            "nazovUJ": "Firma 1",
            "datumZrusenia": "12.03.2026",
        })

        call_command("source_health", skip_checks=True)

    def test_a_source_that_fails_both_of_its_lines_is_counted_once(self):
        """One broken source is one unmet control, not two.

        When every attempt refuses, the attempts line and the refusal line are
        two readings of a single event, and both go red. Counting the source
        twice would make the gate's own headline number -- and therefore the
        threshold anyone tunes against it -- wrong.
        """
        from registers.tasks import _update_company_from_ruz_data

        for index in range(self.MIN_ATTEMPTS):
            _update_company_from_ruz_data({
                "ico": f"8{index:07d}",
                "id": 100000 + index,
                "nazovUJ": f"Firma {index}",
                "datumZrusenia": "12.03.2026",
            })

        stdout = StringIO()
        with self.assertRaises(SystemExit):
            call_command("source_health", skip_checks=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Source health: 1 unmet", output)
        self.assertEqual(output.count("FAIL"), 2)

    def test_a_refusal_is_judged_even_when_the_source_is_mostly_answering(self):
        """The shape a format change actually has.

        A partial format change does not silence a source: most records still
        parse, and `succeeded == 0` never becomes true. Only the refusal count
        can see it -- which is why the refusal line survives the move of `ruz`
        into the attempts table rather than being replaced by it. One healthy
        company is added here so that the attempts line reads OK and the
        verdict can only be coming from the refusals.
        """
        from registers.tasks import _update_company_from_ruz_data

        for index in range(self.MIN_ATTEMPTS):
            _update_company_from_ruz_data({
                "ico": f"8{index:07d}",
                "id": 100000 + index,
                "nazovUJ": f"Firma {index}",
                "datumZrusenia": "12.03.2026",
            })
        _update_company_from_ruz_data({
            "ico": "89999999",
            "id": 100999,
            "nazovUJ": "Zdravá firma",
            "datumZrusenia": "2026-03-12",
        })

        stdout = StringIO()
        with self.assertRaises(SystemExit) as exit_info:
            call_command("source_health", skip_checks=True, stdout=stdout)

        self.assertEqual(exit_info.exception.code, 1)
        output = stdout.getvalue()
        self.assertIn("200 companies refusing a date field", output)
        self.assertIn("Source health: 1 unmet", output)

    def test_a_refusal_that_stops_counting_releases_the_gate(self):
        """A refusal is a state, and the gate has to let it go.

        The refusal count is "companies refusing *now*", read from
        `consecutive_failures`. If it were instead a count of rows that had
        ever refused, an upstream typo that was fixed would hold `make
        ops-check` red forever -- and an alarm that cannot clear is an alarm
        that stops being read.
        """
        from registers.tasks import _update_company_from_ruz_data

        records = [
            {
                "ico": f"8{index:07d}",
                "id": 100000 + index,
                "nazovUJ": f"Firma {index}",
            }
            for index in range(self.MIN_ATTEMPTS)
        ]

        for record in records:
            with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
                _update_company_from_ruz_data({**record, "datumZrusenia": "12.03.2026"})

        with self.assertRaises(SystemExit):
            call_command("source_health", skip_checks=True, stdout=StringIO())

        # The upstream format is corrected; every company syncs cleanly again.
        for record in records:
            _update_company_from_ruz_data({**record, "datumZrusenia": "2026-03-12"})

        stdout = StringIO()
        call_command("source_health", skip_checks=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("0 companies refusing a date field", output)
        self.assertIn("Source health: 0 unmet", output)


class BaseSyncTaskTests(TestCase):
    def test_base_sync_task_config(self):
        from core.task_utils import BaseSyncTask
        self.assertTrue(BaseSyncTask.abstract)
        self.assertEqual(BaseSyncTask.max_retries, 3)
        self.assertTrue(BaseSyncTask.retry_backoff)
        self.assertIn(Exception, BaseSyncTask.autoretry_for)
        self.assertIn(Company.DoesNotExist, BaseSyncTask.dont_autoretry_for)
