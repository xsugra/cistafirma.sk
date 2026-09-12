"""
Financial ratio analysis service.

Computes all financial ratios, trend indicators, and Altman Z-score
from existing CompanyFinancialResult model fields.
No database writes — pure computation over in-memory model instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..models import CompanyFinancialResult


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RatioSet:
    roa: float | None = None
    roe: float | None = None
    ros: float | None = None
    current_ratio: float | None = None  # L3
    quick_ratio: float | None = None  # L2
    cash_ratio: float | None = None  # L1
    asset_turnover: float | None = None
    receivables_collection: float | None = None  # days
    debt_to_equity: float | None = None
    self_financing_ratio: float | None = None


@dataclass
class YearAnalysis:
    year: int
    ratios: RatioSet
    # Keyed the way `RATIO_WIRE_KEYS` spells each ratio, so a verdict is
    # findable by whoever holds the ratio. Values are `good` | `warning` |
    # `bad` | `unknown`.
    interpretation: dict[str, str]
    z_score: float | None
    z_score_label: str | None
    # The same verdict as `z_score_label`, as a token: `safe` | `grey` |
    # `distress`, or None when no Z-score could be computed. The label is for a
    # reader; this is for a program. Both come from `z_score_zone` so a client
    # never has to re-derive the boundary -- which it did, and got a different
    # answer at exactly 1.23 and exactly 2.90.
    z_score_zone: str | None = None
    # The Taffler score, its label and its zone, shaped exactly like the three
    # above and for the same reason: the zone is decided here and read by
    # clients, never re-derived from the score.
    taffler_score: float | None = None
    taffler_label: str | None = None
    taffler_zone: str | None = None


@dataclass
class AnalysisResult:
    latest: YearAnalysis | None
    history: list[YearAnalysis] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Altman Z-score
# ---------------------------------------------------------------------------

# The Altman (1983) thresholds for a private, non-manufacturing firm. They are
# stated once, here, and every surface reads the zone -- the API, the company
# page and both PDF generators. The rule is a strict `>` ladder, so a score of
# exactly 1.23 is distress and exactly 2.90 is grey; a client that wrote the
# mirror image (`< 1.23` / `< 2.90`) put both boundary values in the other
# zone, which is a one-in-a-thousand disagreement that no test could see until
# the boundary was exercised by name.
Z_SCORE_SAFE_MIN = 2.90
Z_SCORE_GREY_MIN = 1.23

Z_SCORE_ZONE_LABELS = {
    'safe': 'Bezpečná zóna',
    'grey': 'Šedá zóna',
    'distress': 'Pásmo bankrotu',
}


def z_score_zone(z_score: float | None) -> str | None:
    """The Altman zone for a score: `safe` | `grey` | `distress`, or None."""
    if z_score is None:
        return None
    if z_score > Z_SCORE_SAFE_MIN:
        return 'safe'
    if z_score > Z_SCORE_GREY_MIN:
        return 'grey'
    return 'distress'


# ---------------------------------------------------------------------------
# Taffler model (1977)
# ---------------------------------------------------------------------------

# ZT = 0,53·X1 + 0,13·X2 + 0,18·X3 + 0,16·X4, the *modified* form -- the one
# whose classification bounds are published; the basic form differs only in X4
# and uses a single zero bound, so the two are not interchangeable and the
# figure below is only meaningful read as the modified one.
#
#   X1 = zisk pred zdanením / krátkodobé záväzky
#   X2 = obežný majetok / cizí zdroje
#   X3 = krátkodobé záväzky / aktíva
#   X4 = tržby / aktíva
TAFFLER_SAFE_MIN = 0.3
TAFFLER_GREY_MIN = 0.2

TAFFLER_ZONE_LABELS = {
    'safe': 'Nízka pravdepodobnosť bankrotu',
    'grey': 'Nejednoznačná situácia',
    'distress': 'Vysoká pravdepodobnosť bankrotu',
}


def taffler_zone(score: float | None) -> str | None:
    """The Taffler zone for a score: `safe` | `grey` | `distress`, or None."""
    if score is None:
        return None
    if score > TAFFLER_SAFE_MIN:
        return 'safe'
    if score > TAFFLER_GREY_MIN:
        return 'grey'
    return 'distress'


# The five models the plan named for this repository, and what became of them.
# Recorded here because the answer is not "they are all computable": the schema
# decides, and four of the five are decided *against*.
#
#   Altman      computed (1983 private-firm form, above)
#   Taffler     computed (modified form, above)
#   IN05        NOT computed -- its second term is EBIT / nákladové úroky, and
#               `CompanyFinancialResult` carries no interest-expense line. The
#               authors' documented convention caps that term at 9 when the
#               charge is *small*; it says nothing about a charge that was never
#               read, so substituting the cap would print the most favourable
#               value the term can take on every row in the database and
#               attribute that choice to the authors. A constant dressed as a
#               measurement is what this module exists to stop doing.
#   Quick test  NOT computed -- K2 and K4 are both built on cash flow, which no
#               field here carries. (Kralicek, 1990.)
#   Index bonity NOT computed -- six weighted terms, the heaviest of which
#   (= Binkert)  (1,5) is cash flow / cizí zdroje, and three more are built on
#               celkové výkony. Neither cash flow nor výkony is a field here.
#               These two names are one model, listed as the plan listed them.
#
# Cash flow, výkony and interest expense are all *parser* inputs, not
# computations: reading them is a schema change plus a re-sync, which is why
# the four are omitted rather than approximated.

# ---------------------------------------------------------------------------
# Thresholds for interpretation
# ---------------------------------------------------------------------------

# Format: (key, good_min, good_max,  warning_min, warning_max)  — None = no limit
THRESHOLDS: dict[str, tuple[float | None, float | None, float | None, float | None]] = {
    'roa':                    (5, None,   0, 5),    # >=5% good, 0-5% warning, <0% bad
    'roe':                    (10, None,  0, 10),
    'ros':                    (5, None,   0, 5),
    'current_ratio':          (1.5, None, 1.0, 1.5),
    'quick_ratio':            (1.0, None, 0.5, 1.0),
    'cash_ratio':             (0.2, None, 0.1, 0.2),
    'asset_turnover':         (0.5, None, 0.2, 0.5),
    'receivables_collection': (None, 60,  60, 90),  # lower = better
    'debt_to_equity':         (None, 1.5, 1.5, 3.0),
    'self_financing_ratio':   (30, None,  15, 30),
}

# The ten ratios, spelled the one way the whole stack spells them: the attribute
# on `RatioSet` (snake_case, what `THRESHOLDS` is keyed by) against the name the
# API, the PDF and the frontend use (camelCase).
#
# One table, because two spellings of the same ten ratios is not a style
# question. A dict lookup for a key that does not exist returns `None` here, and
# `None` is a legal value for every one of these -- so the miss is invisible at
# every layer. It had already produced three separate defects: the PDF's
# benchmark block asked for `current_ratio`, `self_financing_ratio` and
# `debt_to_equity` and drew a dash for the company half of three rows; the PDF's
# ratio table asked the same way and dropped seven of its ten rows entirely; and
# `interpretation` was emitted keyed by the snake_case name while `ratios` beside
# it was keyed by the camelCase one, so the frontend found a verdict for
# `roa`/`roe`/`ros` and nothing for the other seven. Those three are spelled
# identically in both vocabularies, which is what kept the mismatch hidden.
RATIO_WIRE_KEYS: dict[str, str] = {
    'roa': 'roa',
    'roe': 'roe',
    'ros': 'ros',
    'currentRatio': 'current_ratio',
    'quickRatio': 'quick_ratio',
    'cashRatio': 'cash_ratio',
    'assetTurnover': 'asset_turnover',
    'receivablesCollection': 'receivables_collection',
    'debtToEquity': 'debt_to_equity',
    'selfFinancingRatio': 'self_financing_ratio',
}


def _safe_float(value: Decimal | float | None) -> float:
    """Convert Decimal/float/None to float, returning 0.0 for None.

    Read `_amount` below before using this on a figure that becomes a ratio.
    Collapsing absence into zero is right where the value is only ever summed
    and compared, and wrong where it is divided by something: a line the filing
    never carried then enters a sector median as a measured zero, which is how
    the median gross margin of a whole NACE section came out as 0.0 %.
    """
    if value is None:
        return 0.0
    return float(value)


def _amount(value: Decimal | float | None) -> float | None:
    """A stored figure as a float, or `None` when the statement lacked it."""
    return None if value is None else float(value)


def _sum_present(*values: float | None) -> float | None:
    """The sum of the lines actually filed, or `None` if none of them was.

    A sum of present lines is a measurement; a sum with an absent line counted
    as zero is a guess wearing the same clothes.
    """
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _ratio_present(a: float | None, b: float | None) -> float | None:
    """`a / b` as a percentage, or `None` if either side was not filed."""
    if a is None or b is None:
        return None
    return _ratio(a, b)


def _simple_ratio_present(a: float | None, b: float | None) -> float | None:
    """`a / b` as a multiple, or `None` if either side was not filed."""
    if a is None or b is None:
        return None
    return _simple_ratio(a, b)


def _ratio(a: float, b: float) -> float | None:
    """Return a/b as percentage, or None if b is 0."""
    if b == 0:
        return None
    return round(a / b * 100, 2)


def _simple_ratio(a: float, b: float) -> float | None:
    """Return a/b, or None if b is 0 (no *100)."""
    if b == 0:
        return None
    return round(a / b, 2)


def _interpret(value: float | None, key: str) -> str:
    """Return 'good', 'warning', 'bad', or 'unknown' from the threshold table.

    A ratio the filing did not support has no verdict, and `unknown` says that
    out loud. It used to answer `bad`, which is the strongest claim in the
    vocabulary: it told the reader a company was risky because a line was
    missing from a form. `_interpret` is a closed vocabulary shared with the
    PDF template and the frontend -- every one of them has to know the fourth
    token, or `bad` reappears one layer up.
    """
    if value is None:
        return 'unknown'

    thresholds = THRESHOLDS.get(key)
    if thresholds is None:
        return 'good'

    gmin, gmax, wmin, wmax = thresholds

    # For "lower is better" indicators (receivables_collection, debt_to_equity)
    if key in ('receivables_collection', 'debt_to_equity'):
        if gmax is not None and value <= gmax:
            return 'good'
        if wmin is not None and wmax is not None and wmin <= value <= wmax:
            return 'warning'
        return 'bad'

    # For "higher is better" indicators
    if gmin is not None and value >= gmin:
        return 'good'
    if wmin is not None and wmax is not None and wmin <= value <= wmax:
        return 'warning'
    return 'bad'


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FinancialAnalysisService:
    """Compute financial ratios and trends.

    Usage:
        results = list(company.financial_results.all().order_by('year'))
        analysis = FinancialAnalysisService.analyze(results)
    """

    @staticmethod
    def analyze(financials: list[CompanyFinancialResult]) -> AnalysisResult:
        """Compute full analysis from ordered financial results."""
        if not financials:
            return AnalysisResult(latest=None, history=[])

        history: list[YearAnalysis] = []
        prev_ratios: RatioSet | None = None

        for i, fr in enumerate(financials):
            ya = FinancialAnalysisService._analyze_year(fr, prev_ratios if i > 0 else None)
            history.append(ya)
            prev_ratios = ya.ratios

        latest = history[-1] if history else None
        return AnalysisResult(latest=latest, history=history)

    @staticmethod
    def _analyze_year(
        fr: CompanyFinancialResult,
        prev: RatioSet | None = None
    ) -> YearAnalysis:
        """Compute ratios for a single year."""
        # --- extract raw values ---
        profit = _safe_float(fr.profit)
        assets_total = _safe_float(fr.assets_total)
        equity = _safe_float(fr.equity)
        total_revenue = _safe_float(fr.total_revenue)
        added_value = _safe_float(fr.added_value)

        # The same two totals, keeping "not filed" distinct -- the zero-based
        # `assets_total`/`equity` above are what the Z-score arithmetic takes.
        assets_filed = _amount(fr.assets_total)
        equity_filed = _amount(fr.equity)

        # The revenue side of the statement as it was actually filed:
        # "Celkové výnosy" when that line was read, the operating-revenue line
        # otherwise. This is the fallback X5 of the Z-score has always taken
        # (see the note above the formula), named once here because the printed
        # turnover row is the same quantity and the two must not disagree.
        #
        # It is a fallback and not a preference: `total_revenue` is populated on
        # 22.9 % of the 14 236 stored rows against 98.1 % for `revenue`, so a
        # P&L that resolved the operating line without the financial-revenue
        # line is the common shape, not the exception.
        revenue_filed = _amount(fr.total_revenue)
        if revenue_filed is None:
            revenue_filed = _amount(fr.revenue)

        # `_safe_float` maps an absent figure to 0.0, which is right for an
        # arithmetic term and wrong for a *ratio*: a company whose statement
        # carries a balance sheet and no income statement has no ROA, it does
        # not have an ROA of zero. Such a row is now reachable -- the write gate
        # in `ruz_financials_sync` accepts a balance sheet on its own -- so the
        # difference between "zero" and "not filed" is the whole point.
        #
        # Unguarded, `0/328` becomes `roa=0.0` and `_interpret` files it as a
        # `warning`; `debt_to_equity` becomes `0.0` and is filed as `good`, i.e.
        # "no debt" because liabilities were never read rather than because
        # there are none. Both are then *displayed* -- the PDF omits a `None`
        # ratio and prints the badge beside a real one.
        #
        # The guard is `profit` itself, not "some income line was filed". The
        # three profitability ratios divide by `profit`, so the looser test
        # (`any` of revenue/profit/total_revenue/costs) let a filing that
        # carried `revenue` and no profit row through, and `0 / assets` then
        # became an ROA, an ROE and an ROS of 0.0 -- three verdicts, all of them
        # about a line nobody read. Measured 2026-09-12 after the full re-sync:
        # 2 of the 14 236 rows are in that state (a revenue line, no profit row,
        # and no `assets_total` or `total_revenue` either). Both would have been
        # spared by `_ratio`'s own zero-denominator guard, so this closes the
        # general path rather than those two in particular -- it is the rows
        # that carry assets *and* a revenue line *and* no profit that the
        # denominator guard cannot reach.
        profit_filed = fr.profit is not None

        # Assets detail. None-preserving, because each of these becomes a
        # liquidity ratio below: `_safe_float` would turn an unfiled line into
        # a filed zero, and a company whose statement never carried a financial
        # account was being shown a cash ratio of 0.0 % -- filed as `bad`, i.e.
        # "no cash", which is a claim about the company and not about the filing.
        inventory = _amount(fr.assets_inventory)
        receivables_short = _amount(fr.assets_receivables_short)
        receivables_long = _amount(fr.assets_receivables_long)
        financial_accounts = _amount(fr.assets_financial_accounts)

        # Liabilities detail. `liabilities_total` stays zero-based: it is a term
        # in the Altman arithmetic (`liabilities_total > 0`, `equity /
        # liabilities_total`), not an input to a ratio of its own --
        # `debt_to_equity` is guarded on the raw fields instead.
        liabilities_total = _safe_float(fr.liabilities_total)
        liabilities_short = _amount(fr.liabilities_short)
        equity_retained = _safe_float(fr.equity_retained)

        # --- compute current assets and working capital ---
        # A partial sum is the reading the filing supports, and it is the same
        # sum the sector medians take (`benchmarking._compute_section_metrics`),
        # so the figure in the benchmark row and the median beside it are built
        # the same way. Only "the filing carried none of the four lines" is
        # unknown, and that is what `_sum_present` answers with None.
        current_assets = _sum_present(
            inventory, receivables_short, receivables_long, financial_accounts
        )
        # X1 of the Z-score still reads an absent component as 0, as it always
        # has (see the note above the formula); that understates rather than
        # fabricates, and it is deliberately not the ratio-set rule.
        working_capital = (current_assets or 0.0) - (liabilities_short or 0.0)

        # --- ratios ---
        ratios = RatioSet(
            roa=_ratio(profit, assets_total) if profit_filed else None,
            roe=_ratio(profit, equity) if profit_filed else None,
            ros=_ratio(profit, total_revenue) if profit_filed else None,
            current_ratio=_simple_ratio_present(current_assets, liabilities_short),
            quick_ratio=_simple_ratio_present(
                _sum_present(receivables_short, financial_accounts), liabilities_short
            ),
            cash_ratio=_simple_ratio_present(financial_accounts, liabilities_short),
            # X5 of the Z-score, printed as a row: the statement's revenue side
            # over its assets, from the same `revenue_filed` the score uses, so
            # the turnover on the page and the one inside the score are one
            # number.
            #
            # It used to be a fabricated one. `_simple_ratio` sent an unread
            # `total_revenue` through `_safe_float` as 0.0, and 0.0 falls under
            # this row's `bad` threshold -- so 10 924 of the 14 236 rows in the
            # database (77 %) rendered "Obrat aktív 0.00" with the verdict
            # "Riziková": an adverse claim about a company, from a line nobody
            # had read. Of those 10 924, re-measured 2026-09-12 after the full
            # re-sync: 10 704 now show the figure the statement actually
            # supports, 185 show nothing at all, and 35 still show 0.00 --
            # those 35 filed a real zero revenue, which is a measurement and
            # not a fabrication.
            asset_turnover=_simple_ratio_present(revenue_filed, assets_filed),
            receivables_collection=_simple_ratio(
                receivables_short / max(total_revenue, 1) * 365, 1
            ) if total_revenue and receivables_short is not None else None,
            # Guarded on the balance-sheet lines themselves, not on `profit_filed`:
            # this one is fabricated by an absent *liability* figure.
            debt_to_equity=_simple_ratio(liabilities_total, equity)
            if fr.liabilities_total is not None and fr.equity is not None
            else None,
            self_financing_ratio=_ratio_present(equity_filed, assets_filed),
        )

        # --- interpretation ---
        # Keyed the same way the ratios are, from the same table: the verdict
        # for a ratio has to be findable by whoever holds that ratio.
        interpretation = {
            wire: _interpret(getattr(ratios, attr), attr)
            for wire, attr in RATIO_WIRE_KEYS.items()
        }

        # --- Altman Z-score (simplified for private Slovak companies) ---
        # Z = 0.717×X1 + 0.847×X2 + 3.107×X3 + 0.420×X4 + 0.998×X5
        # X1 = working_capital / assets_total
        # X2 = retained_earnings / assets_total
        # X3 = profit (EBIT approx) / assets_total
        # X4 = equity / liabilities_total
        # X5 = total_revenue / assets_total
        #
        # X3 and X5 are guarded on their inputs being *measured*, because a
        # `_safe_float` zero here is not a zero: a company that filed a balance
        # sheet and no income statement would otherwise be scored with
        # `x3 = x5 = 0` and labelled `Pásmo bankrotu` -- a bankruptcy verdict
        # printed into the PDF, from a figure nobody read. The two are what the
        # relaxed write gate stopped guaranteeing. X5 takes `revenue_filed`,
        # which falls back to `revenue` when `total_revenue` is unset, because a
        # P&L that resolved the operating-revenue line without the
        # financial-revenue line is a real and common shape, and refusing there
        # would remove scores that are sound.
        #
        # X1, X2 and X4 still read an absent component as 0, as they always have.
        # That understates rather than fabricates, and tightening it belongs to
        # whoever revisits the formula -- it is not a consequence of this gate.
        z_score = None
        z_score_label = None
        if (
            assets_total > 0
            and liabilities_total > 0
            and fr.profit is not None
            and revenue_filed is not None
        ):
            x1 = working_capital / assets_total
            x2 = equity_retained / assets_total
            x3 = profit / assets_total
            x4 = equity / liabilities_total
            x5 = revenue_filed / assets_total

            z_score = round(
                0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5,
                2,
            )

            zone = z_score_zone(z_score)
            z_score_label = Z_SCORE_ZONE_LABELS[zone]

        # --- Taffler model, modified form ---
        # Guarded on the same four facts the Z-score is guarded on, plus the two
        # inputs only this model has: a filed `liabilities_short` (X1's
        # denominator, X3's numerator) and at least one current-asset line
        # (X2's numerator). An unfiled denominator is not a zero here for the
        # same reason it is not one above -- it would score the company on a
        # figure nobody read.
        #
        # X1's numerator is `profit`, the pre-tax operating result, which is the
        # convention this module already uses for Altman's X3 (`profit (EBIT
        # approx)`). It is an approximation of `zisk pred zdanením`, stated
        # rather than assumed: the statement does carry `income_tax` and
        # `profit_after_tax`, but only since the two profit rows were split, so
        # deriving EBT as their sum would make the Taffler score unavailable on
        # exactly the rows Altman still scores. One convention, applied to both
        # models, is worth more than a second one that is right on some rows.
        #
        # X4 is `revenue_filed`, the same quantity the printed turnover row and
        # Altman's X5 take, so the three cannot disagree about what "tržby" was.
        #
        # `liabilities_short > 0` and not merely `is not None`: a filing that
        # carries the line as a filed zero ("no short-term liabilities") is a
        # real shape, and X1 divides by it. The ratio is then genuinely
        # undefined -- infinite short-term-debt cover is not a measurement -- so
        # the model is left unscored rather than crashed on.
        taffler_score = None
        taffler_label = None
        if (
            assets_total > 0
            and liabilities_total > 0
            and fr.profit is not None
            and revenue_filed is not None
            and liabilities_short is not None
            and liabilities_short > 0
            and current_assets is not None
        ):
            t1 = profit / liabilities_short
            t2 = current_assets / liabilities_total
            t3 = liabilities_short / assets_total
            t4 = revenue_filed / assets_total

            taffler_score = round(0.53 * t1 + 0.13 * t2 + 0.18 * t3 + 0.16 * t4, 2)
            taffler_label = TAFFLER_ZONE_LABELS[taffler_zone(taffler_score)]

        return YearAnalysis(
            year=fr.year,
            ratios=ratios,
            interpretation=interpretation,
            z_score=z_score,
            z_score_label=z_score_label,
            z_score_zone=z_score_zone(z_score),
            taffler_score=taffler_score,
            taffler_label=taffler_label,
            taffler_zone=taffler_zone(taffler_score),
        )

    @staticmethod
    def to_dict(analysis: AnalysisResult) -> dict[str, Any] | None:
        """Serialize AnalysisResult to JSON-safe dict."""
        if analysis.latest is None:
            return None

        def _ratio_dict(r: RatioSet) -> dict:
            return {wire: getattr(r, attr) for wire, attr in RATIO_WIRE_KEYS.items()}

        def _year_dict(y: YearAnalysis) -> dict:
            return {
                'year': y.year,
                'ratios': _ratio_dict(y.ratios),
                'interpretation': y.interpretation,
                'zScore': y.z_score,
                'zScoreLabel': y.z_score_label,
                'zScoreZone': y.z_score_zone,
                'tafflerScore': y.taffler_score,
                'tafflerLabel': y.taffler_label,
                'tafflerZone': y.taffler_zone,
            }

        return {
            'latest': _year_dict(analysis.latest),
            'history': [_year_dict(y) for y in analysis.history],
        }
