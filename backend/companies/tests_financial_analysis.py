"""The per-company ratio set, and what it does with a line nobody filed.

These ratios are printed beside the sector medians in the benchmark table, so
they have to be built the same way the medians are: a company whose statement
carried no financial account has an *unknown* cash ratio, not a cash ratio of
zero. "0.00 ×" beside "Riziková" is a statement about the company, and we would
be inventing it.

A partial reading still counts. A filing that carried inventory and receivables
but no financial accounts supports a current ratio; refusing it would replace a
slightly low figure with no figure at all.
"""

from django.test import SimpleTestCase

from companies.models import CompanyFinancialResult
from companies.services.financial_analysis import FinancialAnalysisService


def ratios(**fields):
    """The ratio set for a single filed year."""
    row = CompanyFinancialResult(year=2025, **fields)
    return FinancialAnalysisService._analyze_year(row, None).ratios


class LiquidityRatioPresenceTests(SimpleTestCase):
    def test_a_balance_sheet_without_an_asset_detail_has_no_liquidity(self):
        # Assets and equity filed, no breakdown of the current assets at all.
        r = ratios(assets_total=1000, equity=600, liabilities_short=400)

        self.assertIsNone(r.cash_ratio)
        self.assertIsNone(r.quick_ratio)
        self.assertIsNone(r.current_ratio)

    def test_a_filed_financial_account_is_still_a_measurement(self):
        r = ratios(
            assets_total=1000,
            liabilities_short=400,
            assets_financial_accounts=0,
        )

        # Zero cash is a reading; "no cash line" is not the same thing.
        self.assertEqual(r.cash_ratio, 0.0)

    def test_a_partial_reading_is_used_rather_than_discarded(self):
        # Inventory and receivables filed, financial accounts not. The current
        # ratio is 300/400 = 0.75 -- understated by whatever cash exists, which
        # is the honest reading of what was filed.
        r = ratios(
            assets_total=1000,
            liabilities_short=400,
            assets_inventory=200,
            assets_receivables_short=100,
        )

        self.assertEqual(r.current_ratio, 0.75)
        # The quick ratio needs the two lines it is defined on, and only one of
        # them was filed: 100/400.
        self.assertEqual(r.quick_ratio, 0.25)
        self.assertIsNone(r.cash_ratio)

    def test_self_financing_needs_a_filed_equity(self):
        # Liabilities filed, equity line absent. `0/1000` would have read as
        # "nothing is financed by its own capital", which is `bad`.
        r = ratios(assets_total=1000, liabilities_total=900)

        self.assertIsNone(r.self_financing_ratio)

    def test_a_filed_zero_equity_is_a_measurement(self):
        r = ratios(assets_total=1000, equity=0, liabilities_total=900)

        self.assertEqual(r.self_financing_ratio, 0.0)

    def test_collection_period_needs_a_filed_receivable(self):
        # Revenue filed, receivables line absent. `0 * 365` reads as a 0-day
        # collection period, the best possible score, from no figure at all.
        r = ratios(total_revenue=1000, assets_total=1000)

        self.assertIsNone(r.receivables_collection)

    def test_the_z_score_still_needs_measured_inputs(self):
        # A balance sheet on its own, no income statement: unchanged by the
        # presence rule above, and still refused rather than scored zero.
        year = FinancialAnalysisService._analyze_year(
            CompanyFinancialResult(
                year=2025, assets_total=1000, equity=600, liabilities_total=400
            ),
            None,
        )

        self.assertIsNone(year.z_score)
        self.assertIsNone(year.ratios.roa)
