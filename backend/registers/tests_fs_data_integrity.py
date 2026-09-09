from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from companies.models import Company
from registers.management.commands.update_fs_data import Command


class FinancialAdministrationDataIntegrityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Exact Name s. r. o.",
            mesto="Bratislava",
            psc="81101",
        )

    @patch("registers.management.commands.update_fs_data.download_and_parse_fs_data")
    def test_item_without_ico_is_not_fuzzy_matched_or_updated(self, mock_download):
        mock_download.return_value = [
            {
                "NAZOV_SUBJEKTU": self.company.nazov_UJ,
                "OBEC": self.company.mesto,
                "PSC": self.company.psc,
                "DLH": "999.99",
            }
        ]
        handlers = Mock()
        command = Command()

        stats = command._process_dataset(
            "tax_debtors",
            "https://example.invalid/dataset.zip",
            handlers,
            dry_run=False,
        )

        handlers.update_company.assert_not_called()
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(stats["unverified"], 1)
        self.company.refresh_from_db()
        self.assertIsNone(self.company.tax_debt)

    @patch("registers.management.commands.update_fs_data.download_and_parse_fs_data")
    def test_item_with_matching_ico_can_be_updated(self, mock_download):
        mock_download.return_value = [{"ICO": self.company.ico, "DLH": "999.99"}]
        handlers = Mock()
        handlers.update_company.return_value = True
        command = Command()

        stats = command._process_dataset(
            "tax_debtors",
            "https://example.invalid/dataset.zip",
            handlers,
            dry_run=True,
        )

        handlers.update_company.assert_called_once()
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["unverified"], 0)
