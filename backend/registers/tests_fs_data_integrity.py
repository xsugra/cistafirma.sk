from datetime import date
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from companies.models import Company
from registers.management.commands.update_fs_data import Command
from registers.services.fs_data_handlers import FSDataHandlers


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


class VatRemovalIsHistoryNotStandingTests(TestCase):
    """`vat_deleted` is a **history** list; `vat_payers` is the **current state**.

    Measured on production 2026-09-17: of the 32 127 rows carrying a removal
    date, **384** have a registration date *later* than it -- the firm sits in
    both datasets at once -- and **379** of those had `vat_payer = False`, so
    the company page called it "Vymazaný z registra DPH" on no evidence but the
    order the datasets happen to be walked in (`vat_payers` first, so
    `vat_deleted` always won).
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=2,
            ico="35757442",
            nazov_UJ="Re-registered s. r. o.",
            datum_reg_dph=date(2024, 3, 1),
            vat_payer=True,
        )
        self.handlers = FSDataHandlers(
            stdout_write=lambda s: None,
            stderr_write=lambda s: None,
            style_success=lambda s: s,
            style_error=lambda s: s,
            style_warning=lambda s: s,
        )

    def _removal(self, dat_vymazu="05.05.2020", rok_porusenia="2019"):
        return self.handlers.handle_vat_deleted(
            self.company,
            {"DAT_VYMAZU": dat_vymazu, "ROK_PORUSENIA": rok_porusenia},
        )

    def test_registration_after_the_removal_does_not_clear_the_flag(self):
        self._removal()
        self.assertIs(self.company.vat_payer, True)

    def test_the_removal_is_still_recorded_on_a_superseded_row(self):
        """Not clearing the flag must not throw the history away."""
        self._removal()
        self.assertEqual(self.company.vat_deleted_date, date(2020, 5, 5))
        self.assertEqual(self.company.vat_deleted_reason, "Rok porušenia: 2019")

    def test_removal_after_the_registration_still_clears_the_flag(self):
        """The guard must not disable the handler's actual job."""
        self.company.datum_reg_dph = date(2018, 1, 1)
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_a_row_with_no_registration_date_still_clears_the_flag(self):
        """Nothing to compare against is not a reason to keep the flag."""
        self.company.datum_reg_dph = None
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_a_same_day_removal_keeps_the_previous_behaviour(self):
        """Two dates in one day cannot be ordered, so the old rule stands."""
        self.company.datum_reg_dph = date(2020, 5, 5)
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_an_unparseable_removal_date_still_clears_the_flag(self):
        self._removal(dat_vymazu="not a date")
        self.assertIs(self.company.vat_payer, False)
        self.assertIsNone(self.company.vat_deleted_date)

    @patch("registers.management.commands.update_fs_data.download_and_parse_fs_data")
    def test_one_pass_over_both_datasets_leaves_the_firm_a_payer(self, mock_download):
        """The defect itself: both datasets run, and the second one used to win.

        `bulk_update` is what makes this a real test rather than an in-memory
        one -- `vat_deleted` writes `vat_payer` for every row it touches, so
        the handler's decision is what lands in the column.
        """
        mock_download.side_effect = [
            [{"ICO": self.company.ico, "DATUM_REG": "01.03.2024", "IC_DPH": "SK1234567890"}],
            [{"ICO": self.company.ico, "DAT_VYMAZU": "05.05.2020", "ROK_PORUSENIA": "2019"}],
        ]
        command = Command()

        command._process_dataset(
            "vat_payers", "https://example.invalid/payers.zip", self.handlers, dry_run=False
        )
        command._process_dataset(
            "vat_deleted", "https://example.invalid/deleted.zip", self.handlers, dry_run=False
        )

        self.company.refresh_from_db()
        self.assertIs(self.company.vat_payer, True)
        self.assertEqual(self.company.datum_reg_dph, date(2024, 3, 1))
        self.assertEqual(self.company.vat_deleted_date, date(2020, 5, 5))
        self.assertEqual(self.company.vat_deleted_reason, "Rok porušenia: 2019")
