"""
PDF company report generation service.

Uses weasyprint to render an HTML template into a PDF document.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from io import BytesIO
from typing import Any

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import Company, SectorBenchmark
from .financial_analysis import (
    FinancialAnalysisService,
    _amount,
    _ratio_present,
    _sum_present,
)
from .nace import get_nace_info

logger = logging.getLogger(__name__)

REPORT_CACHE_TIMEOUT = 300
REPORT_CACHE_LOCK_TIMEOUT = 120
REPORT_CACHE_POLL_INTERVAL = 0.1

# Ratio display configuration for PDF
RATIO_ROWS = [
    {'key': 'roa', 'label': 'ROA (Rentabilita aktív)', 'unit': '%'},
    {'key': 'roe', 'label': 'ROE (Rentabilita vlastného kapitálu)', 'unit': '%'},
    {'key': 'ros', 'label': 'ROS (Rentabilita tržieb)', 'unit': '%'},
    {'key': 'current_ratio', 'label': 'L3 — Bežná likvidita', 'unit': '×'},
    {'key': 'quick_ratio', 'label': 'L2 — Pohotová likvidita', 'unit': '×'},
    {'key': 'cash_ratio', 'label': 'L1 — Okamžitá likvidita', 'unit': '×'},
    {'key': 'asset_turnover', 'label': 'Obrat aktív', 'unit': '×'},
    {'key': 'receivables_collection', 'label': 'Doba inkasa pohľadávok', 'unit': 'dní'},
    {'key': 'debt_to_equity', 'label': 'Zadĺženosť (D/E)', 'unit': '×'},
    {'key': 'self_financing_ratio', 'label': 'Miera samofinancovania', 'unit': '%'},
]


def _report_cache_key(company: Company) -> str:
    """Return an opaque, data-versioned cache key for a company report."""
    financial_versions = sorted(
        (
            result.pk,
            result.updated_at.isoformat() if result.updated_at else '',
        )
        for result in company.financial_results.all()
    )
    try:
        profile = company.orsr_profile
    except ObjectDoesNotExist:
        profile = None

    fingerprint = repr(
        (
            company.pk,
            company.datum_poslednej_upravy.isoformat()
            if company.datum_poslednej_upravy
            else '',
            financial_versions,
            profile.pk if profile else None,
            profile.last_synced_at.isoformat()
            if profile and profile.last_synced_at
            else '',
        )
    )
    digest = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
    return f'company-report:v1:{digest}'


def _get_cached_report(cache_key: str) -> bytes | None:
    """Return a valid cached PDF, or None for a miss."""
    cached_report = cache.get(cache_key)
    if cached_report is None:
        return None
    if isinstance(cached_report, bytes):
        return cached_report

    logger.warning('Ignoring a malformed cached company report.')
    return None


def get_company_report(company: Company) -> bytes:
    """Return a cached PDF report or generate one under a cache-miss lock.

    ``cache.add()`` is atomic for Django's Redis cache backend, so only one
    Gunicorn worker normally renders a report for the same cache key. Cache
    failures deliberately fall back to direct generation; they are logged, but
    never turn an otherwise successful report into a cache error.
    """
    cache_key = _report_cache_key(company)
    lock_key = f'{cache_key}:lock'

    try:
        cached_report = _get_cached_report(cache_key)
        if cached_report is not None:
            return cached_report
        has_generation_lock = cache.add(
            lock_key,
            True,
            timeout=REPORT_CACHE_LOCK_TIMEOUT,
        )
    except Exception:
        logger.warning(
            'Company report cache is unavailable; generating report without caching.',
            exc_info=True,
        )
        return generate_company_report(company)

    if has_generation_lock:
        report = generate_company_report(company)
        try:
            cache.set(cache_key, report, timeout=REPORT_CACHE_TIMEOUT)
        except Exception:
            logger.warning(
                'Company report was generated but could not be cached.',
                exc_info=True,
            )
        return report

    # Another worker owns the atomic Redis lock. Wait for its result instead of
    # rendering a duplicate PDF. The lock expiry bounds this wait if that worker
    # exits before filling the cache.
    deadline = time.monotonic() + REPORT_CACHE_LOCK_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(REPORT_CACHE_POLL_INTERVAL)
        try:
            cached_report = _get_cached_report(cache_key)
        except Exception:
            logger.warning(
                'Company report cache became unavailable while waiting for a report.',
                exc_info=True,
            )
            return generate_company_report(company)
        if cached_report is not None:
            return cached_report

    # The lock has expired without a result. Generate the response so a failed
    # worker cannot make the report endpoint unavailable indefinitely.
    logger.warning(
        'Timed out waiting for a cached company report; generating it directly.'
    )
    return generate_company_report(company)


def _fmt(value: float | None, unit: str) -> str:
    """Format a ratio value with unit."""
    if value is None:
        return '—'
    if unit == '%':
        return f'{value:.1f} %'
    if unit == 'dní':
        return f'{value:.0f}'
    return f'{value:.2f}'


def _fmt_eur(value: float | None) -> str:
    """Format a euro amount with thousands separator."""
    if value is None:
        return '—'
    try:
        from core.formatting import format_currency_eur
        return format_currency_eur(value)
    except Exception:
        return f'{value:,.0f}'


def generate_company_report(company: Company) -> bytes:
    """Generate a PDF report for a company.

    Args:
        company: Company model instance (with prefetched relations).

    Returns:
        PDF file as bytes.
    """
    # 1. Gather data
    financial_results = list(company.financial_results.all().order_by('year'))

    # Financial analysis
    analysis = None
    if financial_results:
        analysis_result = FinancialAnalysisService.analyze(financial_results)
        analysis = FinancialAnalysisService.to_dict(analysis_result)

    # Debts
    debts = []
    total_debt = 0
    if company.debt_vszp and float(company.debt_vszp) > 0:
        debts.append({'source': 'VšZP', 'amount_eur': float(company.debt_vszp)})
        total_debt += float(company.debt_vszp)
    if company.debt_soc_poist and float(company.debt_soc_poist) > 0:
        debts.append({'source': 'Sociálna poisťovňa', 'amount_eur': float(company.debt_soc_poist)})
        total_debt += float(company.debt_soc_poist)
    if company.tax_debt and float(company.tax_debt) > 0:
        debts.append({'source': 'Finančná správa', 'amount_eur': float(company.tax_debt)})
        total_debt += float(company.tax_debt)

    # Risk score (same formula as frontend)
    if total_debt > 0:
        risk_score = max(5, 70 - min(total_debt / 5000, 50))
        risk_summary = 'Spoločnosť vykazuje riziko z dôvodu existujúcich nedoplatkov.'
    else:
        risk_score = 100
        risk_summary = 'Spoločnosť vyzerá byť v dobrom finančnom zdraví.'

    # Enhance with analysis data
    if analysis and analysis.get('latest'):
        zs = analysis['latest'].get('zScore')
        roa = analysis['latest']['ratios'].get('roa')
        if zs is not None:
            if zs < 1.23:
                risk_score = max(5, risk_score - 20)
                risk_summary = 'Vysoké riziko — Altman Z-score v pásme bankrotu.'
            elif zs < 2.90:
                risk_score = max(5, risk_score - 10)
                if total_debt == 0:
                    risk_summary = 'Zvýšená opatrnosť — Z-score v šedej zóne.'
            else:
                if total_debt == 0:
                    risk_summary = 'Spoločnosť je finančne zdravá (Z-score v bezpečnej zóne).'
        if roa is not None and roa < 0:
            risk_score = max(5, risk_score - 10)

    # NACE info
    nace_info = get_nace_info(company.sk_NACE)

    # ORSR profile
    orsr = {}
    try:
        orsr_profile = company.orsr_profile
    except Exception:
        orsr_profile = None

    # Executives (from serializer-like logic)
    executives = []
    if orsr_profile:
        structured = {}
        raw = getattr(orsr_profile, 'raw_payload', None) or {}
        if isinstance(raw, dict):
            structured = raw.get('structured', {})
        for person in structured.get('statutarny_organ', []):
            name = (person.get('name') or '').strip() if isinstance(person, dict) else ''
            role = person.get('role', 'Konateľ') if isinstance(person, dict) else 'Konateľ'
            if name:
                executives.append({'name': name, 'role': role})
        # Fallback flat fields
        if not executives:
            for section in [getattr(orsr_profile, 'statutarny_organ', []) or []]:
                for raw_line in section:
                    lines = [l.strip() for l in (raw_line or '').split('\n') if l.strip()]
                    for line in lines[:3]:
                        executives.append({'name': line, 'role': 'Štatutár'})

    # Ratio rows for template
    ratio_rows = []
    if analysis and analysis.get('latest'):
        ratios = analysis['latest']['ratios']
        interp = analysis['latest']['interpretation']
        for row_def in RATIO_ROWS:
            key = row_def['key']
            val = ratios.get(key)
            if val is not None:
                ratio_rows.append({
                    'label': row_def['label'],
                    'display': _fmt(val, row_def['unit']),
                    'interpretation': interp.get(key, 'unknown'),
                })

    # Financial history rows
    financial_history = []
    for fr in financial_results[-6:]:  # Last 6 years
        financial_history.append({
            'year': fr.year,
            'revenue': _fmt_eur(float(fr.revenue or 0)),
            'profit': _fmt_eur(float(fr.profit or 0)),
            'assets': _fmt_eur(float(fr.assets_total or 0)),
            'equity': _fmt_eur(float(fr.equity or 0)),
        })

    # Benchmark rows
    benchmark_rows = []
    benchmark_data = None
    if analysis and analysis.get('latest') and nace_info and nace_info.get('section'):
        latest_year = financial_results[-1].year if financial_results else None
        if latest_year:
            try:
                bm = SectorBenchmark.objects.get(
                    nace_section=nace_info['section'],
                    year=latest_year,
                )
                benchmark_data = {
                    'section': bm.nace_section,
                    'section_name': nace_info.get('section_name'),
                    'year': bm.year,
                    'company_count': bm.company_count,
                }
                company_ratios = analysis['latest']['ratios']
                # The row is labelled with a percentage and the sector side is
                # a percentage, so the company side has to be one too. It used
                # to be `debt_to_equity` -- a multiple, printed with a '%' sign
                # beside a percentage median, which flattered almost every
                # company. The filed debt ratio for the analysed year is the
                # figure the sector median is a median *of*.
                # `company_ratios` comes from `FinancialAnalysisService.to_dict`
                # and is camelCase. Three of the six rows here asked for
                # `current_ratio`, `self_financing_ratio` and `debt_to_equity`
                # instead, which resolved to None every single time -- the
                # company half of those rows printed "—" beside a real median,
                # with no error anywhere. `roa`/`roe`/`ros` are spelled the same
                # in both, which is what kept it invisible.
                latest_fr = financial_results[-1]
                filed_debt_ratio = _ratio_present(
                    _sum_present(
                        _amount(latest_fr.liabilities_total),
                        _amount(latest_fr.liabilities_accruals),
                    ),
                    _amount(latest_fr.assets_total),
                )
                # The same two expressions the API computes `debtRatio` and
                # `grossMargin` with, so the printed figure and the one on the
                # company page cannot drift apart.
                filed_gross_margin = _ratio_present(
                    _amount(latest_fr.added_value), _amount(latest_fr.revenue)
                )
                bench_metrics = [
                    ('ROA', company_ratios.get('roa'), _amount(bm.median_roa), '%'),
                    ('ROE', company_ratios.get('roe'), _amount(bm.median_roe), '%'),
                    ('ROS', company_ratios.get('ros'), _amount(bm.median_ros), '%'),
                    ('Zadĺženosť', filed_debt_ratio, _amount(bm.median_debt_ratio), '%'),
                    # Was missing from the export entirely while the company page
                    # carried it -- the one row a trade reader looks for first.
                    ('Hrubá marža', filed_gross_margin, _amount(bm.median_gross_margin), '%'),
                    ('L3 Likvidita', company_ratios.get('currentRatio'), _amount(bm.median_current_ratio), '×'),
                    ('Samofinancovanie', company_ratios.get('selfFinancingRatio'), _amount(bm.median_self_financing_ratio), '%'),
                ]
                for label, cv, sv, unit in bench_metrics:
                    benchmark_rows.append({
                        'label': label,
                        'company_val': _fmt(cv, unit),
                        'sector_val': _fmt(sv, unit),
                    })
            except SectorBenchmark.DoesNotExist:
                pass

    # 2. Build context
    context = {
        'company': {
            'name': company.nazov_UJ,
            'ico': company.ico,
            'legal_form': company.get_legal_form_display() if hasattr(company, 'get_legal_form_display') else (company.pravna_forma or ''),
            'status': 'Vymazaná' if company.datum_zrusenia else 'Aktívna',
            'registration_date': company.datum_zalozenia,
            'address': {
                'street': company.ulica or '',
                'city': company.mesto or '',
                'zip_code': company.psc or '',
            },
            'orsr_profile': orsr,
            'vat_status': {
                'is_vat_payer': company.vat_payer,
                'ic_dph': company.ic_dph,
                'tax_reliability_index': company.tax_reliability or '—',
            },
        },
        'nace_info': nace_info,
        'risk_score': {'score': risk_score, 'summary': risk_summary},
        'debts': debts,
        'total_debt': total_debt,
        'analysis': analysis,
        'ratio_rows': ratio_rows,
        'financial_history': financial_history,
        'executives': executives,
        'benchmark': benchmark_data,
        'benchmark_rows': benchmark_rows,
        'generated_at': timezone.now(),
    }

    # 3. Render HTML
    html = render_to_string('company_report.html', context)

    # 4. Convert to PDF
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        raise RuntimeError(
            'weasyprint is not installed. '
            'Install it with: pip install weasyprint'
        )
    except Exception as e:
        logger.exception('PDF generation failed for company %s', company.ico)
        raise RuntimeError(f'PDF generation failed: {e}') from e
