"""The one risk score.

The defect this file exists for is not that the score was wrong. It is that
there were three of them -- `WatchlistSerializer`, `pdf_report` and
`frontend/api.ts` -- and each was internally consistent, so nothing failed and
nothing logged. The same company read 100/100 in the watchlist and 80/100 on
its own page, and the only way to notice was to look at both.

So the tests below pin the arithmetic, and then pin that the three callers
agree, which is the property the three copies could not have.
"""

from django.test import SimpleTestCase, TestCase

from companies.models import Company, CompanyFinancialResult
from companies.services.risk_score import (
    RISK_SCORE_FLOOR,
    _round_half_up,
    compute_risk_score,
    risk_score_for_company,
    total_debt,
)


class _Company:
    """A company with only the three debts the score reads.

    Deliberately a stub and not a saved `Company`: the arithmetic under test
    touches exactly these attributes, and a database row would hide which ones
    by making every other field available too.
    """

    def __init__(self, vszp=None, soc=None, tax=None):
        self.debt_vszp = vszp
        self.debt_soc_poist = soc
        self.tax_debt = tax


def analysis(zone=None, roa=None):
    """The `to_dict` shape, as far as the score reads it."""
    if zone is None and roa is None:
        return None
    return {'latest': {'zScoreZone': zone, 'ratios': {'roa': roa}}}


class DebtTermTests(SimpleTestCase):
    def test_a_company_with_no_debt_and_no_analysis_is_clean(self):
        result = compute_risk_score(_Company(), None)
        self.assertEqual(result['score'], 100)
        self.assertIn('dobrom finančnom zdraví', result['summary'])

    def test_debt_widens_the_score_by_one_point_per_five_thousand(self):
        self.assertEqual(compute_risk_score(_Company(vszp=5000), None)['score'], 69)
        self.assertEqual(compute_risk_score(_Company(soc=10000), None)['score'], 68)

    def test_the_three_debts_are_summed(self):
        company = _Company(vszp=1000, soc=2000, tax=2000)
        self.assertEqual(total_debt(company), 5000)
        self.assertEqual(compute_risk_score(company, None)['score'], 69)

    def test_debt_alone_can_never_take_more_than_half_the_scale(self):
        # 50 points is the whole debt penalty, however large the debt -- the
        # rest of the scale is reserved for what the balance sheet says.
        self.assertEqual(compute_risk_score(_Company(tax=10_000_000), None)['score'], 20)

    def test_an_unfetched_debt_is_not_a_debt(self):
        # `None` reads as zero here, unlike in the ratios: an unfetched debt is
        # a fact about our coverage, not a claim about the company.
        self.assertEqual(compute_risk_score(_Company(vszp=None), None)['score'], 100)


class AnalysisAdjustmentTests(SimpleTestCase):
    def test_the_bankruptcy_zone_costs_twenty_and_says_so(self):
        result = compute_risk_score(_Company(), analysis(zone='distress'))
        self.assertEqual(result['score'], 80)
        self.assertEqual(result['summary'], 'Vysoké riziko — Altman Z-score v pásme bankrotu.')

    def test_the_grey_zone_costs_ten(self):
        self.assertEqual(compute_risk_score(_Company(), analysis(zone='grey'))['score'], 90)

    def test_the_safe_zone_costs_nothing(self):
        self.assertEqual(compute_risk_score(_Company(), analysis(zone='safe'))['score'], 100)

    def test_debt_and_a_bad_zone_compound(self):
        # 5 from the debt (25 000 EUR is a 5-point penalty) and 20 from the
        # zone, not one or the other: 70 - 5 - 20 = 45.
        result = compute_risk_score(_Company(tax=25_000), analysis(zone='distress'))
        self.assertEqual(result['score'], 45)

    def test_a_negative_roa_costs_ten_and_joins_the_sentence(self):
        result = compute_risk_score(_Company(), analysis(roa=-3.2))
        self.assertEqual(result['score'], 90)
        # Appended to the sentence rather than made a second one, so the tile
        # stays one line -- and the full stop is not doubled.
        self.assertEqual(
            result['summary'],
            'Spoločnosť vyzerá byť v dobrom finančnom zdraví + záporná rentabilita aktív.',
        )

    def test_a_filed_zero_roa_is_not_a_negative_one(self):
        # `0.0 %` is a measurement; only a loss is a penalty.
        result = compute_risk_score(_Company(), analysis(roa=0))
        self.assertEqual(result['score'], 100)
        self.assertNotIn('záporná', result['summary'])

    def test_an_unread_roa_is_not_a_zero(self):
        self.assertEqual(compute_risk_score(_Company(), analysis(roa=None))['score'], 100)

    def test_the_score_never_falls_through_the_floor(self):
        result = compute_risk_score(
            _Company(tax=10_000_000), analysis(zone='distress', roa=-1)
        )
        self.assertEqual(result['score'], RISK_SCORE_FLOOR)

    def test_the_zone_is_read_and_never_re_derived(self):
        # The score reads the token, so a payload that carries only the zone
        # cannot be second-guessed into a different verdict here.
        self.assertEqual(compute_risk_score(_Company(), analysis(zone='grey'))['score'], 90)

    def test_an_unknown_zone_token_is_not_a_penalty(self):
        self.assertEqual(compute_risk_score(_Company(), analysis(zone='wat'))['score'], 100)

    def test_a_missing_latest_block_is_not_a_crash(self):
        self.assertEqual(compute_risk_score(_Company(), {'latest': None})['score'], 100)
        self.assertEqual(compute_risk_score(_Company(), {})['score'], 100)


class DebtSummaryTests(SimpleTestCase):
    def test_the_debt_summary_survives_a_grey_zone(self):
        # A company with debts already has its headline; the zone does not
        # replace it. Only the debt-free cases take the zone's wording.
        result = compute_risk_score(_Company(vszp=5000), analysis(zone='grey'))
        self.assertEqual(result['score'], 59)
        self.assertIn('nedoplatkov', result['summary'])

    def test_the_zone_wording_replaces_the_clean_one(self):
        result = compute_risk_score(_Company(), analysis(zone='safe'))
        self.assertEqual(
            result['summary'], 'Spoločnosť je finančne zdravá (Z-score v bezpečnej zóne).'
        )


class RoundingTests(SimpleTestCase):
    def test_the_half_rounds_up_the_way_the_client_used_to(self):
        # Python's `round` is banker's rounding: `round(68.5)` is 68. The
        # frontend did `Math.round(68.5)` -> 69. The score is published as an
        # integer now, so if it rounded the other way the page would show a
        # number the old client never would have.
        self.assertEqual(_round_half_up(68.5), 69)
        self.assertEqual(round(68.5), 68)
        # 7 500 EUR is a 1.5-point penalty: 70 - 1.5 = 68.5 -> 69.
        self.assertEqual(compute_risk_score(_Company(tax=7500), None)['score'], 69)

    def test_the_published_score_is_an_integer(self):
        # It used to be an unrounded float in the PDF, which printed
        # "69.753/100" where the screen printed "70/100".
        result = compute_risk_score(_Company(tax=1234.56), None)
        self.assertIsInstance(result['score'], int)


class OneScoreTests(TestCase):
    """The three callers read one computation, which is the point of the file."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999001, ico='11111111', nazov_UJ='Test s. r. o.',
            tax_debt=10_000_000,
        )
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025,
            assets_total=1000, liabilities_total=400, liabilities_short=250,
            equity=600, profit=60, total_revenue=1200, revenue=1200,
            assets_inventory=100, assets_receivables_short=150,
        )

    def test_the_company_page_and_the_watchlist_publish_the_same_number(self):
        from companies.serializers import CompanyDetailSerializer, WatchlistSerializer
        from companies.models import Watchlist
        from django.contrib.auth import get_user_model

        detail = CompanyDetailSerializer(self.company).data['riskScore']

        user = get_user_model().objects.create_user(
            email='a@example.com', password='x',
        )
        entry = Watchlist.objects.create(user=user, company=self.company)
        listed = WatchlistSerializer(entry).data['riskScore']

        # The two used to differ by 20 points on exactly this company: the
        # watchlist read the debt and stopped, so it missed the Z-score zone.
        self.assertEqual(listed, detail['score'])
        self.assertLess(detail['score'], 40)

    def test_the_detail_payload_carries_a_summary_for_the_tile(self):
        from companies.serializers import CompanyDetailSerializer

        payload = CompanyDetailSerializer(self.company).data['riskScore']
        self.assertEqual(sorted(payload), ['score', 'summary'])
        self.assertTrue(payload['summary'])
