"""
PDF company report generation service.

Uses weasyprint to render an HTML template into a PDF document.
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

from django.template.loader import render_to_string
from django.utils import timezone

from ..models import Company, SectorBenchmark
from .financial_analysis import FinancialAnalysisService
from .nace import get_nace_info

logger = logging.getLogger(__name__)

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
                    'interpretation': interp.get(key, 'bad'),
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
                bench_metrics = [
                    ('ROA', company_ratios.get('roa'), float(bm.median_roa) if bm.median_roa else None, '%'),
                    ('ROE', company_ratios.get('roe'), float(bm.median_roe) if bm.median_roe else None, '%'),
                    ('ROS', company_ratios.get('ros'), float(bm.median_ros) if bm.median_ros else None, '%'),
                    ('Zadĺženosť', company_ratios.get('debt_to_equity'), float(bm.median_debt_ratio) if bm.median_debt_ratio else None, '%'),
                    ('L3 Likvidita', company_ratios.get('current_ratio'), float(bm.median_current_ratio) if bm.median_current_ratio else None, '×'),
                    ('Samofinancovanie', company_ratios.get('self_financing_ratio'), float(bm.median_self_financing_ratio) if bm.median_self_financing_ratio else None, '%'),
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
