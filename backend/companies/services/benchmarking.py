"""
Sector benchmarking service.

Computes sector-level medians for financial indicators
by aggregating CompanyFinancialResult data grouped by NACE section.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from statistics import median
from typing import Any

from django.db.models import QuerySet

from ..models import Company, CompanyFinancialResult, SectorBenchmark
from .financial_analysis import (
    FinancialAnalysisService,
    _amount,
    _ratio_present,
    _sum_present,
)
from .nace import get_nace_section

logger = logging.getLogger(__name__)


# Indicators to compute medians for (in FinancialAnalysisService ratio terms)
BENCHMARK_RATIOS = [
    'roa', 'roe', 'ros', 'debt_ratio', 'gross_margin',
    'current_ratio', 'self_financing_ratio',
]


def compute_sector_benchmarks(year: int | None = None) -> dict[str, int]:
    """Compute sector benchmarks for all NACE sections.

    Args:
        year: Target year. Defaults to the latest available year.

    Returns:
        Dict mapping section → number of companies in benchmark.
    """
    if year is None:
        # Find the latest year with enough financial data for meaningful benchmarks
        from django.db.models import Count
        year_counts = (
            CompanyFinancialResult.objects
            .values('year')
            .annotate(cnt=Count('id'))
            .order_by('-year')
        )
        year = None
        for yc in year_counts:
            if yc['cnt'] >= 500:  # Need at least 500 companies for meaningful sector medians
                year = yc['year']
                break
        if year is None:
            logger.warning('No year with >=500 financial results found — skipping benchmark computation')
            return {}

    logger.info('Computing sector benchmarks for year %s ...', year)

    # Fetch all financial results for the target year, joined with company NACE
    results = (
        CompanyFinancialResult.objects
        .filter(year=year)
        .select_related('company')
        .only(
            'year', 'company_id', 'company__sk_NACE',
            'profit', 'total_revenue', 'revenue', 'added_value',
            'assets_total', 'equity',
            'assets_inventory', 'assets_receivables_short',
            'assets_receivables_long', 'assets_financial_accounts',
            'liabilities_total', 'liabilities_short', 'equity_retained',
        )
        .iterator(chunk_size=2000)
    )

    # Group by NACE section
    section_data: dict[str, list] = defaultdict(list)

    for fr in results:
        section = get_nace_section(fr.company.sk_NACE)
        if section is None:
            continue
        section_data[section].append(fr)

    # Compute medians and save
    created = 0
    updated = 0

    for section, fr_list in section_data.items():
        metrics = _compute_section_metrics(fr_list, section)

        if metrics['company_count'] < 5:
            # Too few companies — skip to avoid misleading benchmarks
            continue

        benchmark, was_created = SectorBenchmark.objects.update_or_create(
            nace_section=section,
            year=year,
            defaults={
                'company_count': metrics['company_count'],
                'median_revenue': metrics.get('median_revenue'),
                'median_profit': metrics.get('median_profit'),
                'median_assets_total': metrics.get('median_assets_total'),
                'median_equity': metrics.get('median_equity'),
                'median_roa': metrics.get('median_roa'),
                'median_roe': metrics.get('median_roe'),
                'median_ros': metrics.get('median_ros'),
                'median_debt_ratio': metrics.get('median_debt_ratio'),
                'median_gross_margin': metrics.get('median_gross_margin'),
                'median_current_ratio': metrics.get('median_current_ratio'),
                'median_self_financing_ratio': metrics.get('median_self_financing_ratio'),
            },
        )

        if was_created:
            created += 1
        else:
            updated += 1

    logger.info(
        'Sector benchmarks computed: %d sections, %d created, %d updated (year=%s)',
        len(section_data), created, updated, year,
    )

    # Return summary
    return {s: len(d) for s, d in section_data.items()}


def _compute_section_metrics(fr_list: list[CompanyFinancialResult], section: str) -> dict[str, Any]:
    """Compute median metrics for a list of financial results in one section."""

    # Helper: collect non-None numeric values, compute median
    def _median_of(values: list[float]) -> Decimal | None:
        filtered = [v for v in values if v is not None]
        if not filtered:
            return None
        return Decimal(str(round(median(filtered), 2)))

    # Collect raw values and computed ratios
    revenues = []
    profits = []
    assets_totals = []
    equities = []
    ratios_roa = []
    ratios_roe = []
    ratios_ros = []
    ratios_debt = []
    ratios_margin = []
    ratios_current = []
    ratios_self = []

    for fr in fr_list:
        # Raw values. Every one of these becomes a ratio below, so an absent
        # line has to stay absent rather than arrive as 0.0 -- `_safe_float`
        # is deliberately not used here (see its docstring).
        profit = _amount(fr.profit)
        assets_total = _amount(fr.assets_total)
        equity = _amount(fr.equity)
        total_revenue = _amount(fr.total_revenue)
        revenue = _amount(fr.revenue)
        added_value = _amount(fr.added_value)
        liabilities_total = _amount(fr.liabilities_total)
        liabilities_short = _amount(fr.liabilities_short)
        liabilities_accruals = _amount(fr.liabilities_accruals)

        # Current assets. A partial sum is still the best reading the filing
        # supports, and it is the same sum the per-company ratio set takes --
        # so the median and the figure it is compared against agree.
        current_assets = _sum_present(
            _amount(fr.assets_inventory),
            _amount(fr.assets_receivables_short),
            _amount(fr.assets_receivables_long),
            _amount(fr.assets_financial_accounts),
        )

        if revenue:
            revenues.append(revenue)
        if profit:
            profits.append(profit)
        if assets_total:
            assets_totals.append(assets_total)
        if equity:
            equities.append(equity)

        # Ratios. `_ratio_present` answers "not filed" with None, so the row
        # leaves the median instead of voting for zero.
        roa = _ratio_present(profit, assets_total)
        roe = _ratio_present(profit, equity)
        # Operating revenue, not `total_revenue`: the numerator is operating
        # profit, and dividing it by a denominator that also carries the
        # financial revenues the numerator excludes is not a ratio. It is also
        # the difference between a median for most companies and one for a few
        # -- `total_revenue` is populated on 3 458 of 15 275 rows (22.6 %)
        # against 14 999 (98.2 %) for `revenue`. The per-company ratio set
        # divides the same two lines, and the company page prints the two
        # figures side by side.
        ros = _ratio_present(profit, revenue)
        debt_ratio = _ratio_present(
            _sum_present(liabilities_total, liabilities_accruals), assets_total
        )
        gross_margin = _ratio_present(added_value, revenue)
        current_ratio = _ratio_present(current_assets, liabilities_short)
        self_financing = _ratio_present(equity, assets_total)

        if roa is not None:
            ratios_roa.append(roa)
        if roe is not None:
            ratios_roe.append(roe)
        if ros is not None:
            ratios_ros.append(ros)
        if debt_ratio is not None:
            ratios_debt.append(debt_ratio)
        if gross_margin is not None:
            ratios_margin.append(gross_margin)
        if current_ratio is not None:
            ratios_current.append(current_ratio)
        if self_financing is not None:
            ratios_self.append(self_financing)

    return {
        'company_count': len(fr_list),
        'median_revenue': _median_of(revenues),
        'median_profit': _median_of(profits),
        'median_assets_total': _median_of(assets_totals),
        'median_equity': _median_of(equities),
        'median_roa': _median_of(ratios_roa),
        'median_roe': _median_of(ratios_roe),
        'median_ros': _median_of(ratios_ros),
        'median_debt_ratio': _median_of(ratios_debt),
        'median_gross_margin': _median_of(ratios_margin),
        'median_current_ratio': _median_of(ratios_current),
        'median_self_financing_ratio': _median_of(ratios_self),
    }


def get_benchmark_for_company(nace_code: str | None) -> dict | None:
    """Get the sector benchmark for a company's NACE section.

    Returns a dict with benchmark data or None if no benchmark exists.
    """
    section = get_nace_section(nace_code)
    if section is None:
        return None

    # Get company's latest financial year
    from ..models import Company
    # nace_code alone is not enough to resolve the company — we need the Company object
    # This function is designed to be called from the serializer with a Company obj
    return None  # placeholder — real lookup is in serializer
