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
    """Convert Decimal/float/None to float, returning 0.0 for None."""
    if value is None:
        return 0.0
    return float(value)


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
    """Return 'good', 'warning', or 'bad' based on threshold table."""
    if value is None:
        return 'bad'

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
        revenue = _safe_float(fr.revenue)
        added_value = _safe_float(fr.added_value)

        # Assets detail
        inventory = _safe_float(fr.assets_inventory)
        receivables_short = _safe_float(fr.assets_receivables_short)
        receivables_long = _safe_float(fr.assets_receivables_long)
        financial_accounts = _safe_float(fr.assets_financial_accounts)

        # Liabilities detail
        liabilities_total = _safe_float(fr.liabilities_total)
        liabilities_short = _safe_float(fr.liabilities_short)
        equity_retained = _safe_float(fr.equity_retained)

        # --- compute current assets and working capital ---
        current_assets = inventory + receivables_short + receivables_long + financial_accounts
        working_capital = current_assets - liabilities_short

        # --- ratios ---
        ratios = RatioSet(
            roa=_ratio(profit, assets_total),
            roe=_ratio(profit, equity),
            ros=_ratio(profit, total_revenue),
            current_ratio=_simple_ratio(current_assets, liabilities_short),
            quick_ratio=_simple_ratio(receivables_short + financial_accounts, liabilities_short),
            cash_ratio=_simple_ratio(financial_accounts, liabilities_short),
            asset_turnover=_simple_ratio(total_revenue, assets_total),
            receivables_collection=_simple_ratio(
                receivables_short / max(total_revenue, 1) * 365, 1
            ) if total_revenue else None,
            debt_to_equity=_simple_ratio(liabilities_total, equity),
            self_financing_ratio=_ratio(equity, assets_total),
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
        z_score = None
        z_score_label = None
        if assets_total > 0 and liabilities_total > 0:
            x1 = working_capital / assets_total
            x2 = equity_retained / assets_total
            x3 = profit / assets_total
            x4 = equity / liabilities_total
            x5 = total_revenue / assets_total

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
