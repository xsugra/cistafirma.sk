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
from companies.services.financial_analysis import (
    RATIO_WIRE_KEYS,
    FinancialAnalysisService,
)


def ratios(**fields):
    """The ratio set for a single filed year."""
    row = CompanyFinancialResult(year=2025, **fields)
    return FinancialAnalysisService._analyze_year(row, None).ratios


def year(**fields):
    """The whole analysed year, ratios and verdicts together."""
    row = CompanyFinancialResult(year=2025, **fields)
    return FinancialAnalysisService._analyze_year(row, None)


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


class InterpretationVocabularyTests(SimpleTestCase):
    """The four tokens, and which one an unmeasured ratio gets.

    `interpretation` crosses three boundaries -- the API, the PDF template and
    `frontend/types.ts` -- and each one has its own copy of the token set. A
    token added here without them renders as an unstyled pill or a blank cell,
    and a token *removed* here leaves the frontend's `?? 'unknown'` fallback as
    the only thing standing between a missing verdict and `undefined` on screen.
    So the set is asserted, not assumed.
    """

    RATIO_KEYS = tuple(RATIO_WIRE_KEYS)

    def test_every_ratio_carries_a_verdict(self):
        # A key missing from the dict is a key the frontend has to guess at.
        analysed = year(assets_total=1000, equity=600, liabilities_total=400)

        self.assertEqual(sorted(analysed.interpretation), sorted(self.RATIO_KEYS))

    def test_the_vocabulary_is_closed(self):
        # A balance sheet with every line present, so nothing is `unknown`.
        measured = year(
            assets_total=1000, equity=600, liabilities_total=400, profit=100,
            total_revenue=2000, assets_inventory=100,
            assets_receivables_short=100, assets_financial_accounts=50,
            liabilities_short=200,
        )

        self.assertLessEqual(
            set(measured.interpretation.values()), {'good', 'warning', 'bad'}
        )

    def test_an_unmeasured_ratio_is_not_given_a_verdict(self):
        # The whole point: `bad` is the harshest word in the vocabulary and it
        # used to be handed out for a line the filing never carried.
        analysed = year(assets_total=1000, equity=600, liabilities_total=400)

        self.assertEqual(analysed.interpretation['roa'], 'unknown')
        self.assertEqual(analysed.interpretation['cashRatio'], 'unknown')
        for wire, attr in RATIO_WIRE_KEYS.items():
            with self.subTest(ratio=wire):
                if getattr(analysed.ratios, attr) is None:
                    self.assertEqual(analysed.interpretation[wire], 'unknown')

    def test_a_measured_ratio_that_is_bad_is_still_called_bad(self):
        # `unknown` must not swallow the real verdict, or the fix trades a
        # false alarm for a missing one.
        analysed = year(
            assets_total=1000, equity=100, liabilities_total=900,
            profit=-50, total_revenue=1000,
        )

        self.assertEqual(analysed.interpretation['roa'], 'bad')

    def test_the_serialized_year_keeps_the_fourth_token(self):
        # `to_dict` is what the API and the PDF read; a vocabulary that stops
        # at `_analyze_year` reaches nobody.
        result = FinancialAnalysisService.analyze([
            CompanyFinancialResult(
                year=2025, assets_total=1000, equity=600, liabilities_total=400
            )
        ])

        payload = FinancialAnalysisService.to_dict(result)

        self.assertEqual(payload['latest']['interpretation']['roa'], 'unknown')


class SerializedRatioKeysTests(SimpleTestCase):
    """`ratios` and `interpretation` are keyed alike, in every year.

    They were not. `_ratio_dict` renamed to camelCase and `interpretation` was
    passed through under its snake_case attribute names, so a consumer holding
    a ratio could only find its verdict when the two spellings happened to
    agree -- which they do for `roa`, `roe` and `ros`, and for nothing else.
    The frontend found three verdicts of ten and the PDF's ratio table silently
    dropped seven rows.

    Nothing errored, because a missing key in a dict of nullable numbers is a
    `None` and `None` is a legal value. So this asserts the two key sets are
    equal rather than that any particular key resolves.
    """

    def payload(self):
        return FinancialAnalysisService.to_dict(
            FinancialAnalysisService.analyze([
                CompanyFinancialResult(
                    year=2024, assets_total=1000, equity=600, liabilities_total=400
                ),
                CompanyFinancialResult(
                    year=2025, assets_total=1000, equity=600, liabilities_total=400,
                    profit=100, total_revenue=2000, assets_inventory=100,
                    assets_receivables_short=100, assets_financial_accounts=50,
                    liabilities_short=200,
                ),
            ])
        )

    def test_the_two_dicts_share_one_key_set(self):
        payload = self.payload()

        for label, year_payload in [('latest', payload['latest'])] + [
            (f'history[{i}]', y) for i, y in enumerate(payload['history'])
        ]:
            with self.subTest(year=label):
                self.assertEqual(
                    sorted(year_payload['ratios']),
                    sorted(year_payload['interpretation']),
                )

    def test_the_keys_are_the_ones_the_frontend_asks_for(self):
        # `RatioSet` in `frontend/types.ts` and `RATIO_ROWS` in `pdf_report.py`
        # both name these; a rename here without them is the original bug.
        payload = self.payload()

        self.assertEqual(
            sorted(payload['latest']['ratios']), sorted(RATIO_WIRE_KEYS)
        )
