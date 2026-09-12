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
    interpretation: dict[str, str]  # key -> good|warning|bad
    z_score: float | None
    z_score_label: str | None


@dataclass
class AnalysisResult:
    latest: YearAnalysis | None
    history: list[YearAnalysis] = field(default_factory=list)


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
        has_income = any(
            getattr(fr, name) is not None
            for name in ("revenue", "profit", "total_revenue", "costs")
        )

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
            roa=_ratio(profit, assets_total) if has_income else None,
            roe=_ratio(profit, equity) if has_income else None,
            ros=_ratio(profit, total_revenue),
            current_ratio=_simple_ratio_present(current_assets, liabilities_short),
            quick_ratio=_simple_ratio_present(
                _sum_present(receivables_short, financial_accounts), liabilities_short
            ),
            cash_ratio=_simple_ratio_present(financial_accounts, liabilities_short),
            asset_turnover=_simple_ratio(total_revenue, assets_total) if has_income else None,
            receivables_collection=_simple_ratio(
                receivables_short / max(total_revenue, 1) * 365, 1
            ) if total_revenue and receivables_short is not None else None,
            # Guarded on the balance-sheet lines themselves, not on `has_income`:
            # this one is fabricated by an absent *liability* figure.
            debt_to_equity=_simple_ratio(liabilities_total, equity)
            if fr.liabilities_total is not None and fr.equity is not None
            else None,
            self_financing_ratio=_ratio_present(equity_filed, assets_filed),
        )

        # --- interpretation ---
        interpretation = {
            key: _interpret(getattr(ratios, key), key)
            for key in (
                'roa', 'roe', 'ros', 'current_ratio', 'quick_ratio',
                'cash_ratio', 'asset_turnover', 'receivables_collection',
                'debt_to_equity', 'self_financing_ratio',
            )
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
        # relaxed write gate stopped guaranteeing. X5 falls back to `revenue`
        # when `total_revenue` is unset, because a P&L that resolved the
        # operating-revenue line without the financial-revenue line is a real and
        # common shape, and refusing there would remove scores that are sound.
        #
        # X1, X2 and X4 still read an absent component as 0, as they always have.
        # That understates rather than fabricates, and tightening it belongs to
        # whoever revisits the formula -- it is not a consequence of this gate.
        z_score = None
        z_score_label = None
        z_revenue = fr.total_revenue if fr.total_revenue is not None else fr.revenue
        if (
            assets_total > 0
            and liabilities_total > 0
            and fr.profit is not None
            and z_revenue is not None
        ):
            x1 = working_capital / assets_total
            x2 = equity_retained / assets_total
            x3 = profit / assets_total
            x4 = equity / liabilities_total
            x5 = float(z_revenue) / assets_total

            z_score = round(
                0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5,
                2,
            )

            if z_score > 2.90:
                z_score_label = 'Bezpečná zóna'
            elif z_score > 1.23:
                z_score_label = 'Šedá zóna'
            else:
                z_score_label = 'Pásmo bankrotu'

        return YearAnalysis(
            year=fr.year,
            ratios=ratios,
            interpretation=interpretation,
            z_score=z_score,
            z_score_label=z_score_label,
        )

    @staticmethod
    def to_dict(analysis: AnalysisResult) -> dict[str, Any] | None:
        """Serialize AnalysisResult to JSON-safe dict."""
        if analysis.latest is None:
            return None

        def _ratio_dict(r: RatioSet) -> dict:
            return {
                'roa': r.roa,
                'roe': r.roe,
                'ros': r.ros,
                'currentRatio': r.current_ratio,
                'quickRatio': r.quick_ratio,
                'cashRatio': r.cash_ratio,
                'assetTurnover': r.asset_turnover,
                'receivablesCollection': r.receivables_collection,
                'debtToEquity': r.debt_to_equity,
                'selfFinancingRatio': r.self_financing_ratio,
            }

        def _year_dict(y: YearAnalysis) -> dict:
            return {
                'year': y.year,
                'ratios': _ratio_dict(y.ratios),
                'interpretation': y.interpretation,
                'zScore': y.z_score,
                'zScoreLabel': y.z_score_label,
            }

        return {
            'latest': _year_dict(analysis.latest),
            'history': [_year_dict(y) for y in analysis.history],
        }
