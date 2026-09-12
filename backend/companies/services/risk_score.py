"""The one risk score.

There used to be three, and all three answered differently:

  * `WatchlistSerializer.get_riskScore` -- debt only, and `int()` truncating.
    It never looked at the analysis at all, so a company in the Altman
    bankruptcy zone with no debt scored 100/100 on the watchlist and 80/100 on
    its own page.
  * `services/pdf_report.py` -- debt plus the zone plus ROA, as an unrounded
    float: the printed report read "69.753/100" where the screen read "70/100".
  * `frontend/api.ts` -- the same ladder again in TypeScript, `Math.round`ed,
    and the only one that appended the negative-ROA clause to the summary text.

Two of the three carried a comment claiming to be "the same formula as" the
other, which was true of the base branch and false of every adjustment below
it. That is the shape this repository keeps repairing: one rule spelled in
several places drifts, and the drift is silent because each copy is internally
consistent.

So the ladder lives here, once. `CompanyDetailSerializer` publishes it,
`WatchlistSerializer` publishes it, the PDF prints it, and the frontend renders
what it is given instead of deriving its own.

What the score is: a 0-100 *attention* indicator for a human scanning a list --
5 is "look at this now", 100 is "nothing here". It is not a probability of
default and not an accounting measure; the Altman and Taffler scores are those,
and they are published separately rather than folded in.

The zone is read from `FinancialAnalysisService.to_dict`'s `zScoreZone`
(`analysis['latest']['zScoreZone']`) rather than re-derived here. A second
ladder would put exactly 1.23 and exactly 2.90 in different zones again, which
is the defect the `zScoreZone` field was added to end.

Taffler deliberately does not move this score. The two models answer different
questions at different horizons, and adding a second penalty ladder would
change every score in the product at once -- a decision to take on its own
evidence, not as a side effect of giving the score one home.
"""

from decimal import Decimal

from .financial_analysis import FinancialAnalysisService

# The score never falls below this: the scale exists to rank attention, and
# collapsing everything distressed to 0 would throw away the ordering among
# the companies that need looking at most.
RISK_SCORE_FLOOR = 5

# Where the debt slope saturates. 5 000 EUR of debt costs one point, and 50
# points -- half the scale -- is as much as debt alone can take, so a company
# with debts can never score below 70 on debt alone. That ceiling is
# deliberate: debt is a fact about cash flow, not about solvency, and the
# analysis adjustments below are what a bad balance sheet costs.
DEBT_PER_POINT = 5000
DEBT_MAX_PENALTY = 50
DEBT_BASE_SCORE = 70

ZONE_PENALTY = {'distress': 20, 'grey': 10, 'safe': 0}
NEGATIVE_ROA_PENALTY = 10

SUMMARY_DEBT = 'Spoločnosť vykazuje riziko z dôvodu existujúcich nedoplatkov.'
SUMMARY_CLEAN = 'Spoločnosť vyzerá byť v dobrom finančnom zdraví.'
SUMMARY_DISTRESS = 'Vysoké riziko — Altman Z-score v pásme bankrotu.'
SUMMARY_GREY = 'Zvýšená opatrnosť — Z-score v šedej zóne.'
SUMMARY_SAFE = 'Spoločnosť je finančne zdravá (Z-score v bezpečnej zóne).'
SUMMARY_NEGATIVE_ROA = 'záporná rentabilita aktív'


def total_debt(company) -> Decimal:
    """The three statutory debts the score reads, summed.

    `None` is treated as zero because an unfetched debt is not a debt -- but
    note the asymmetry this creates with the ratios, where `None` is *not*
    zero: there, an absent line would be a claim about the company. Here it
    is a claim about our own coverage, and the score starts from "nothing
    known against this company" rather than from a penalty.
    """
    total = Decimal(0)
    for value in (company.debt_vszp, company.debt_soc_poist, company.tax_debt):
        if value:
            total += Decimal(value)
    return total


def _round_half_up(value: float) -> int:
    """`Math.round`, so the number the API sends is the number it printed.

    Python's `round` is banker's rounding: `round(70.5)` is 70 where
    JavaScript's `Math.round(70.5)` is 71. The frontend used to do this
    rounding itself, so the two disagreed on exact halves.
    """
    return int(value + 0.5)


def compute_risk_score(company, analysis: dict | None = None) -> dict:
    """The risk score and its one-sentence summary.

    `analysis` is the `FinancialAnalysisService.to_dict` payload -- the same
    dict the API publishes and the PDF is rendered from, so all three read one
    computation rather than three.
    """
    debt = total_debt(company)
    has_debt = debt > 0

    if has_debt:
        penalty = min(float(debt) / DEBT_PER_POINT, DEBT_MAX_PENALTY)
        score = max(RISK_SCORE_FLOOR, DEBT_BASE_SCORE - penalty)
        summary = SUMMARY_DEBT
    else:
        score = 100.0
        summary = SUMMARY_CLEAN

    latest = (analysis or {}).get('latest') or {}
    zone = latest.get('zScoreZone')
    roa = (latest.get('ratios') or {}).get('roa')

    if zone in ZONE_PENALTY:
        score = max(RISK_SCORE_FLOOR, score - ZONE_PENALTY[zone])
        if zone == 'distress':
            summary = SUMMARY_DISTRESS
        elif zone == 'grey' and not has_debt:
            summary = SUMMARY_GREY
        elif zone == 'safe' and not has_debt:
            summary = SUMMARY_SAFE

    if roa is not None and roa < 0:
        score = max(RISK_SCORE_FLOOR, score - NEGATIVE_ROA_PENALTY)
        # The clause is appended to the sentence rather than made a sentence
        # of its own, so the summary stays one line in the tile it renders in.
        # `rstrip('.')` and not `replace('.', '')`, which the frontend did --
        # that would also eat a decimal point inside a summary that had one.
        summary = f'{summary.rstrip(".")} + {SUMMARY_NEGATIVE_ROA}.'

    return {'score': _round_half_up(score), 'summary': summary}


def risk_score_for_company(company) -> dict:
    """`compute_risk_score` for a caller that has no analysis payload yet.

    The watchlist is that caller: it holds a list of companies and no
    analysis. Prefetch `company__financial_results` on the queryset, or this
    walks the results once per row.
    """
    results = list(company.financial_results.all().order_by('year'))
    analysis = None
    if results:
        analysis = FinancialAnalysisService.to_dict(
            FinancialAnalysisService.analyze(results)
        )
    return compute_risk_score(company, analysis)
