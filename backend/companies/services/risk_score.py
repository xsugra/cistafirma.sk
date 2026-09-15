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


def _describe_debt(debt: Decimal) -> str:
    """The debt total as the sentence a reader would say it in.

    Slovak groups thousands with a space and uses a comma for the decimal
    mark, and this string is rendered as-is rather than reformatted by the
    frontend -- the same figure must not read two ways on one screen.
    """
    whole = int(debt)
    text = f'{whole:,}'.replace(',', ' ')
    cents = debt - whole
    if cents:
        text += f',{int(cents * 100):02d}'
    return f'{text} €'


#: What the debt factor says when no sum is recorded. "žiadne" answers the
#: question the factor asks -- are there arrears -- and every company the
#: rotation has not reached answers it the same way, which the check dates on
#: the debts card are there to qualify.
NO_DEBT_DETAIL = 'žiadne'

#: ...except when the register listed the company without publishing a sum.
#: Sociálna poisťovňa carries two populations under one heading, and the second
#: -- employers that did not file, foreign SZČO that did not report -- is
#: recorded in `social_listed_without_amount` and nowhere else. It costs the
#: score nothing, because the register printed no sum to cost it with, so this
#: is a change to the sentence and not to the number: a factor at zero and a
#: factor we could not put a number on are different facts, and `parts` exists
#: to keep them apart.
NO_DEBT_LISTED_DETAIL = 'žiadne peňažné; SP eviduje bez zverejnenej sumy'


def describe_no_debt(company) -> str:
    """The debt factor's sentence for a company with no recorded arrears."""
    if getattr(company, 'social_listed_without_amount', None):
        return NO_DEBT_LISTED_DETAIL
    return NO_DEBT_DETAIL


def _describe_zone(zone: str) -> str:
    """The zone in the words the summary already uses for it."""
    return {
        'distress': 'pásmo bankrotu',
        'grey': 'šedá zóna',
        'safe': 'bezpečná zóna',
    }.get(zone, zone)


def compute_risk_score(company, analysis: dict | None = None) -> dict:
    """The risk score, its one-sentence summary, and what moved it.

    `analysis` is the `FinancialAnalysisService.to_dict` payload -- the same
    dict the API publishes and the PDF is rendered from, so all three read one
    computation rather than three.

    The `score` and `summary` are unchanged by `parts` being here: the
    additions below are the same ladder read out loud. They are computed as
    deductions off a clean 100 rather than the original step-by-step `max`,
    which is the same number -- every step only ever subtracts, so clamping
    once at the end is equivalent to clamping at each one -- but it can be
    *shown*, and a reader asking "why 35?" deserves an answer.

    `parts` carries every factor that was considered, not only the ones that
    cost something, because a factor at 0 and a factor we could not read are
    different facts and the difference matters to whoever is deciding whether
    to trust the number. `delta` is `None` for "not assessed", and a number
    (possibly 0) for "assessed, and this is what it cost".
    """
    debt = total_debt(company)
    has_debt = debt > 0

    if has_debt:
        penalty = min(float(debt) / DEBT_PER_POINT, DEBT_MAX_PENALTY)
        # `DEBT_BASE_SCORE` is 70 against a clean 100, so being in debt costs
        # 30 points before the slope even starts.
        debt_deduction = (100 - DEBT_BASE_SCORE) + penalty
        summary = SUMMARY_DEBT
    else:
        debt_deduction = 0.0
        summary = SUMMARY_CLEAN

    parts: list[dict] = [{
        'key': 'debt',
        'label': 'Evidované nedoplatky',
        'delta': -debt_deduction,
        'detail': _describe_debt(debt) if has_debt else describe_no_debt(company),
    }]

    latest = (analysis or {}).get('latest') or {}
    zone = latest.get('zScoreZone')
    roa = (latest.get('ratios') or {}).get('roa')

    zone_deduction = 0.0
    if zone in ZONE_PENALTY:
        zone_deduction = float(ZONE_PENALTY[zone])
        if zone == 'distress':
            summary = SUMMARY_DISTRESS
        elif zone == 'grey' and not has_debt:
            summary = SUMMARY_GREY
        elif zone == 'safe' and not has_debt:
            summary = SUMMARY_SAFE

    parts.append({
        'key': 'zone',
        'label': 'Altman Z-score',
        # `None`, not 0, when the zone is absent: an unread zone is not a
        # neutral one, and showing it as "no effect" would claim the model
        # looked at a company it never saw.
        'delta': -zone_deduction if zone in ZONE_PENALTY else None,
        'detail': _describe_zone(zone) if zone in ZONE_PENALTY else 'nemáme závierku',
    })

    roa_deduction = 0.0
    if roa is not None and roa < 0:
        roa_deduction = float(NEGATIVE_ROA_PENALTY)
        # The clause is appended to the sentence rather than made a sentence
        # of its own, so the summary stays one line in the tile it renders in.
        # `rstrip('.')` and not `replace('.', '')`, which the frontend did --
        # that would also eat a decimal point inside a summary that had one.
        summary = f'{summary.rstrip(".")} + {SUMMARY_NEGATIVE_ROA}.'

    parts.append({
        'key': 'roa',
        'label': 'Rentabilita aktív',
        'delta': -roa_deduction if roa is not None else None,
        'detail': f'{roa:.1f} %'.replace('.', ',') if roa is not None else 'nemáme závierku',
    })

    raw = 100.0 - debt_deduction - zone_deduction - roa_deduction
    clamped = raw < RISK_SCORE_FLOOR
    score = max(float(RISK_SCORE_FLOOR), raw)

    return {
        'score': _round_half_up(score),
        'summary': summary,
        'breakdown': {
            'start': 100,
            'floor': RISK_SCORE_FLOOR,
            # True when the floor is what set the number, so a reader adding
            # the parts up is told why they do not reach the score instead of
            # finding an inconsistency we left in.
            'clamped': clamped,
            'parts': parts,
        },
    }


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
