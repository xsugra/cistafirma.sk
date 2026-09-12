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
    Z_SCORE_ZONE_LABELS,
    FinancialAnalysisService,
    z_score_zone,
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


class AltmanZoneTests(SimpleTestCase):
    """One boundary, and the two values that sit exactly on it.

    The ladder was written twice with mirror-image comparisons -- `> 2.90` /
    `> 1.23` in the analysis service, `< 1.23` / `< 2.90` in the frontend's
    risk summary -- so at exactly 1.23 the service said *distress* and the
    summary said *grey*, and at exactly 2.90 the service said *grey* and the
    summary said *safe*. Both spellings passed every test, because no test had
    ever handed either one a score that lands on a threshold.

    These pin the boundary values themselves, and pin the label to the zone, so
    the two can no longer be derived separately.
    """

    def test_a_score_above_the_upper_threshold_is_safe(self):
        self.assertEqual(z_score_zone(2.91), 'safe')

    def test_the_upper_threshold_itself_is_grey_and_not_safe(self):
        # `> 2.90`, so 2.90 is *not* safe. This is the value the frontend's
        # `< 2.90` put in the safe zone.
        self.assertEqual(z_score_zone(2.90), 'grey')

    def test_a_score_between_the_thresholds_is_grey(self):
        self.assertEqual(z_score_zone(2.00), 'grey')

    def test_the_lower_threshold_itself_is_distress_and_not_grey(self):
        # `> 1.23`, so 1.23 is *not* grey. This is the value the frontend's
        # `< 1.23` put in the grey zone.
        self.assertEqual(z_score_zone(1.23), 'distress')

    def test_a_score_below_the_lower_threshold_is_distress(self):
        self.assertEqual(z_score_zone(1.22), 'distress')

    def test_no_score_has_no_zone(self):
        self.assertIsNone(z_score_zone(None))

    def test_every_zone_has_a_label_and_the_labels_are_the_published_ones(self):
        self.assertEqual(
            Z_SCORE_ZONE_LABELS,
            {
                'safe': 'Bezpečná zóna',
                'grey': 'Šedá zóna',
                'distress': 'Pásmo bankrotu',
            },
        )
        for zone in ('safe', 'grey', 'distress'):
            with self.subTest(zone=zone):
                self.assertTrue(Z_SCORE_ZONE_LABELS[zone])

    def test_the_serialized_zone_and_label_are_the_same_verdict(self):
        # The claim is not "the zone is right" but "the zone and the label are
        # one verdict" -- a client may render either one, and the PDF renders
        # the label while the risk summary now reads the zone.
        row = CompanyFinancialResult(
            year=2025, assets_total=1000, equity=250, liabilities_total=750,
            profit=-50, total_revenue=100, assets_inventory=10,
            assets_receivables_short=10, assets_financial_accounts=5,
            liabilities_short=100, equity_retained=-200,
        )
        payload = FinancialAnalysisService.to_dict(
            FinancialAnalysisService.analyze([row])
        )

        latest = payload['latest']
        self.assertIsNotNone(latest['zScore'])
        self.assertEqual(latest['zScoreZone'], z_score_zone(latest['zScore']))
        self.assertEqual(
            latest['zScoreLabel'], Z_SCORE_ZONE_LABELS[latest['zScoreZone']]
        )

    def test_a_year_with_no_readable_score_has_neither_zone_nor_label(self):
        # A statement with no assets line cannot produce a Z-score, and the
        # absent score must not arrive as a zone.
        payload = FinancialAnalysisService.to_dict(
            FinancialAnalysisService.analyze([
                CompanyFinancialResult(year=2025, revenue=100),
            ])
        )

        self.assertIsNone(payload['latest']['zScore'])
        self.assertIsNone(payload['latest']['zScoreZone'])
        self.assertIsNone(payload['latest']['zScoreLabel'])



class TurnoverPresenceTests(SimpleTestCase):
    """Obrat aktív: the row used to state a figure nobody had read.

    `asset_turnover` was `_simple_ratio(total_revenue, assets_total)`, and
    `total_revenue` reaches it through `_safe_float`, which answers an unread
    line with 0.0. Zero falls under this row's `bad` threshold, so the row
    rendered "0.00" with the verdict "Riziková" -- measured 2026-09-12 on the
    live database, that was 10 909 of 14 204 rows (77 %), every one of them a
    company whose filing simply did not carry the "Celkové výnosy" line
    (`total_revenue` coverage: 22.9 %, against 98.3 % for `revenue`).

    The row states the same quantity as X5 of the Z-score, which has always
    fallen back to `revenue` for exactly this shape of filing. These pin the two
    together, because a page that prints one turnover while the score beside it
    computes another is the class of defect this whole set of changes is about.
    """

    def test_the_operating_line_stands_in_when_the_total_was_not_filed(self):
        r = ratios(assets_total=1000, revenue=500, profit=50)

        self.assertEqual(r.asset_turnover, 0.5)

    def test_the_filed_total_wins_over_the_operating_line(self):
        # Not a preference between equals: when the statement carried both, the
        # total is the figure the row names.
        r = ratios(assets_total=1000, revenue=500, total_revenue=800, profit=50)

        self.assertEqual(r.asset_turnover, 0.8)

    def test_a_statement_with_no_revenue_line_at_all_has_no_turnover(self):
        # The row leaves the table. It does not become a zero, and it does not
        # become a zero wearing the verdict "Riziková".
        r = ratios(assets_total=1000, equity=600, liabilities_total=400)

        self.assertIsNone(r.asset_turnover)

    def test_the_turnover_and_the_score_appear_and_vanish_together(self):
        # The coupling that matters: both read the revenue side of the same
        # filing, so one cannot be present while the other is missing.
        operating_only = year(
            assets_total=1000, equity=600, liabilities_total=400, profit=100,
            revenue=500, equity_retained=200, assets_inventory=300,
            liabilities_short=400,
        )
        self.assertEqual(operating_only.ratios.asset_turnover, 0.5)
        self.assertIsNotNone(operating_only.z_score)

        no_revenue = year(
            assets_total=1000, equity=600, liabilities_total=400, profit=100,
            equity_retained=200, assets_inventory=300, liabilities_short=400,
        )
        self.assertIsNone(no_revenue.ratios.asset_turnover)
        self.assertIsNone(no_revenue.z_score)

    def test_the_score_is_the_one_the_printed_turnover_implies(self):
        # X5 = revenue_filed / assets_total, and the row above prints exactly
        # that. Recomputing the score from the published weights proves the
        # turnover the reader sees is the one inside the score -- it fails if
        # X5 ever goes back to reading a different revenue line.
        row = CompanyFinancialResult(
            year=2025, assets_total=1000, equity=600, liabilities_total=400,
            profit=100, revenue=500, equity_retained=200,
            assets_inventory=300, liabilities_short=400,
        )
        result = FinancialAnalysisService._analyze_year(row, None)

        x1 = (300 - 400) / 1000        # working capital / assets
        x2 = 200 / 1000                # retained earnings / assets
        x3 = 100 / 1000                # profit / assets
        x4 = 600 / 400                 # equity / liabilities
        x5 = result.ratios.asset_turnover   # the printed row, not a copy of it
        expected = round(
            0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5, 2
        )

        self.assertEqual(result.z_score, expected)


class ProfitabilityGuardTests(SimpleTestCase):
    """The three profitability ratios are guarded on `profit` itself.

    They divide by `profit`, so the guard has to be "the profit line was read",
    not "some income line was read". The looser test let a filing that carried
    `revenue` and no profit row through, and `0 / assets` then arrived as an
    ROA, an ROE and an ROS of 0.0: three adverse verdicts about a line nobody
    had read. Measured 2026-09-12, no stored row is in that state, so these pin
    the path shut rather than a leak.

    Each case files `total_revenue` as well, so ROS's denominator is present and
    the only thing missing is the profit line -- which is the claim under test.
    """

    def test_revenue_and_costs_without_a_profit_row_yield_no_ratio(self):
        # A statement that resolved the revenue and cost lines and no result
        # line: the shape a parser vocabulary gap produces.
        r = ratios(
            assets_total=1000, equity=600, revenue=500, costs=400,
            total_revenue=500,
        )

        self.assertIsNone(r.roa)
        self.assertIsNone(r.roe)
        self.assertIsNone(r.ros)

    def test_a_filed_profit_still_produces_all_three(self):
        r = ratios(
            assets_total=1000, equity=500, revenue=500, total_revenue=500,
            profit=100,
        )

        self.assertEqual(r.roa, 10.0)
        self.assertEqual(r.roe, 20.0)
        self.assertEqual(r.ros, 20.0)

    def test_a_filed_zero_profit_is_a_measurement_not_an_absence(self):
        # The other side of the same line: zero filed is a real figure and keeps
        # its zero, with a verdict, rather than being withheld.
        r = ratios(
            assets_total=1000, equity=500, revenue=500, total_revenue=500,
            profit=0,
        )

        self.assertEqual(r.roa, 0.0)
        self.assertEqual(r.ros, 0.0)
