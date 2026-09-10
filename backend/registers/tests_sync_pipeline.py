from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from companies.models import Company
from registers.models import SyncJob
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

    @patch("registers.tasks.RuzFinancialsSyncService")
    def test_sync_financials_calls_service(self, MockService):
        mock_service = MockService.return_value
        mock_service.sync_company.return_value = 5
        from registers.tasks import sync_company_financials_from_ruz
        result = sync_company_financials_from_ruz(self.company.id)
        mock_service.sync_company.assert_called_once_with(self.company)
        self.assertIn("rows=5", result)

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

    def __init__(self, pages):
        self._pages = list(pages)
        self.detail_calls = []

    def get_changed_company_ids(self, zmenene_od=None, pokracovat_za_id=None):
        if not self._pages:
            return {"id": [], "existujeDalsieId": False}
        page = self._pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return {"id": page, "existujeDalsieId": bool(self._pages)}

    def get_company_details(self, company_id):
        self.detail_calls.append(company_id)
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

        `source_health` judges a source on whether its attempts produce a
        usable answer -- "attempts, and not one of them usable" is a
        date-format change. Recording the refusal as a failed attempt for
        `ruz` is what lets `make ops-check` reach that verdict; without it the
        guard's failure mode is a JSON line nobody queries, and the gate
        reports SATISFIED throughout a mass erasure.
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

    def test_a_clean_sync_records_nothing_against_the_source(self):
        """The other half: RUZ must not appear in the gate's table at all
        while it is answering us properly. A row here means a date went
        unread, not that RUZ was synced."""
        from registers.models import CompanySyncStatus
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data(self._record(datumZrusenia="2026-04-01"))

        self.assertEqual(CompanySyncStatus.objects.count(), 0)

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


class BaseSyncTaskTests(TestCase):
    def test_base_sync_task_config(self):
        from core.task_utils import BaseSyncTask
        self.assertTrue(BaseSyncTask.abstract)
        self.assertEqual(BaseSyncTask.max_retries, 3)
        self.assertTrue(BaseSyncTask.retry_backoff)
        self.assertIn(Exception, BaseSyncTask.autoretry_for)
        self.assertIn(Company.DoesNotExist, BaseSyncTask.dont_autoretry_for)
