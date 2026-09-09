from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from companies.models import Company
from registers.scrapers.debt_result import DebtCheckResult


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


class BaseSyncTaskTests(TestCase):
    def test_base_sync_task_config(self):
        from core.task_utils import BaseSyncTask
        self.assertTrue(BaseSyncTask.abstract)
        self.assertEqual(BaseSyncTask.max_retries, 3)
        self.assertTrue(BaseSyncTask.retry_backoff)
        self.assertIn(Exception, BaseSyncTask.autoretry_for)
        self.assertIn(Company.DoesNotExist, BaseSyncTask.dont_autoretry_for)
