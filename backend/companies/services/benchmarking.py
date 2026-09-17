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
    current_assets_of,
)
from .nace import get_nace_section

logger = logging.getLogger(__name__)


# Indicators to compute medians for (in FinancialAnalysisService ratio terms)
BENCHMARK_RATIOS = [
    'roa', 'roe', 'ros', 'debt_ratio', 'gross_margin',
    'current_ratio', 'self_financing_ratio',
]

# A year needs at least this many filed results before a median drawn from it is
# a sector median rather than a median of a handful of firms.
MIN_RESULTS_PER_YEAR = 500

# ... and one section needs at least this many companies before we store a row
# for it at all.
MIN_COMPANIES_PER_SECTION = 5


def _years_with_enough_results(min_results: int | None = None) -> list[int]:
    """Every year whose filings can carry a sector median, newest first.

    `min_results` defaults to `MIN_RESULTS_PER_YEAR` at call time rather than at
    definition time, so a test can lower the threshold and exercise this query
    with a handful of rows.
    """
    if min_results is None:
        min_results = MIN_RESULTS_PER_YEAR
    from django.db.models import Count
    counts = (
        CompanyFinancialResult.objects
        .values('year')
        .annotate(cnt=Count('id'))
        .order_by('-year')
    )
    return [row['year'] for row in counts if row['cnt'] >= min_results]


def compute_sector_benchmarks(year: int | None = None) -> dict[int, dict[str, int]]:
    """Compute sector benchmarks, one row per NACE section per year.

    Args:
        year: A single year to (re)compute. `None` -- what the daily beat entry
            passes -- means every year clearing `MIN_RESULTS_PER_YEAR`.

    Returns:
        `{year: {section: company_count}}`, one entry per year computed.

    `None` used to mean "the newest year that clears the threshold", and the
    loop that found it `break`-ed on the first match, so exactly one year was
    ever stored: on 2026-09-17 the table held 19 rows, all of them 2025. The two
    readers (`companies/serializers.py`, `companies/services/pdf_report.py`)
    look a benchmark up by the **company's** latest filed year, so no company
    whose last filing predates the newest qualifying year could ever match one
    and every one of them rendered without a benchmark. Measured on production,
    that was **1 703 of 15 467** companies (2024: 469, 2023: 179, 2013-2022: the
    remaining 1 055), against 228 of the 247 (section, year) keys missing.

    It is a filter, not a search: all thirteen years 2013-2025 clear 500 (13 999
    to 14 790 filings each; only 2026, still being filed, is under it at 98).
    """
    years = _years_with_enough_results() if year is None else [year]
    if not years:
        logger.warning(
            'No year has >=%d financial results — skipping benchmark computation',
            MIN_RESULTS_PER_YEAR,
        )
        return {}

    return {target_year: _compute_year(target_year) for target_year in years}


def _compute_year(year: int) -> dict[str, int]:
    """Compute and store one year's benchmarks, section by section."""
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
            'assets_current', 'assets_inventory', 'assets_receivables_short',
            'assets_receivables_long', 'assets_financial_short',
            'assets_financial_accounts',
            'liabilities_total', 'liabilities_short', 'equity_retained',
            # `_compute_section_metrics` reads this one too, and it has to be
            # listed: a field left out of `only()` is not merely absent, it is
            # *deferred*, so reading it issues one more query -- per row, and
            # this loop walks every row of a year. It was missing, and 13 999
            # rows meant 13 999 extra round trips, once per year computed.
            'liabilities_accruals',
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
    # Only the sections actually stored, so the summary the caller logs is the
    # table's contents rather than the input's -- those differ by every section
    # the threshold below skips.
    stored: dict[str, int] = {}

    for section, fr_list in section_data.items():
        metrics = _compute_section_metrics(fr_list, section)

        if metrics['company_count'] < MIN_COMPANIES_PER_SECTION:
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
        stored[section] = metrics['company_count']

    logger.info(
        'Sector benchmarks computed: %d sections, %d created, %d updated (year=%s)',
        len(stored), created, updated, year,
    )

    # Return summary
    return stored


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

        # Current assets -- the same call the per-company ratio set makes, not a
        # second copy of the rule. These two were copies once, and the copy here
        # still read the four-term sum after the statement was found to report
        # the total outright at r.33: the median would have been built from
        # figures excluding cash and short-term financial assets, and printed
        # beside per-company ratios that included them.
        current_assets = current_assets_of(fr)

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
