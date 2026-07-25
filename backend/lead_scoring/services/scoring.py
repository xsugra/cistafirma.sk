"""
Lead scoring service.

Implements the deterministic scoring algorithm with explainable breakdowns.
Scores companies based on business fit, data quality, and financial health.
"""

import logging
from datetime import timedelta

from django.db import models
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus

logger = logging.getLogger(__name__)


class LeadScoringService:
    """
    Calculate lead scores for companies based on:
    1. Business fit (SK NACE alignment, location, size)
    2. Data quality (ORSR completeness, financial data, sync health)
    3. Financial health (debt, profitability, revenue trend)
    """

    # Target SK NACE codes for IT/Programming/Tech companies
    TARGET_NACE_CODES = [
        '62.01',  # Computer programming
        '62.02',  # IT consultancy
        '62.03',  # Computer facilities management
        '62.09',  # Other IT services
        '63.11',  # Data processing
    ]

    # Scoring weights
    NACE_WEIGHT = 40  # Business fit: SK NACE alignment
    DATA_QUALITY_WEIGHT = 30  # Data quality: ORSR, financials, sync health
    FINANCIAL_HEALTH_WEIGHT = 30  # Financial health: debts, profitability

    # Penalties
    DEBT_PENALTY = -30  # Heavy penalty for any debt
    INACTIVE_PENALTY = -100  # Company marked as deleted

    def calculate_score(self, company: Company) -> dict:
        """
        Calculate comprehensive score for a company.
        
        Returns:
            {
                'score': 0-100,
                'nace_relevance_score': 0-40,
                'data_completeness_score': 0-30,
                'financial_health_score': 0-30,
                'debt_penalty': 0 or negative,
                'breakdown': {
                    'nace': {...},
                    'data_quality': {...},
                    'financial_health': {...},
                    'debts': {...},
                }
            }
        """
        breakdown = {}

        # 1. NACE Relevance (0-40 points)
        nace_score, nace_breakdown = self._calculate_nace_score(company)
        breakdown['nace'] = nace_breakdown

        # 2. Data Quality (0-30 points)
        data_score, data_breakdown = self._calculate_data_quality_score(company)
        breakdown['data_quality'] = data_breakdown

        # 3. Financial Health (0-30 points)
        financial_score, financial_breakdown = self._calculate_financial_health_score(company)
        breakdown['financial_health'] = financial_breakdown

        # 4. Debt Penalties
        debt_penalty, debt_breakdown = self._calculate_debt_penalty(company)
        breakdown['debts'] = debt_breakdown

        # 5. Inactive Company Penalty
        inactive_penalty = 0
        if company.datum_zrusenia is not None:
            inactive_penalty = self.INACTIVE_PENALTY
            breakdown['inactive'] = {'penalty': inactive_penalty, 'reason': 'Company is deleted/inactive'}

        # Calculate total score (capped at 0-100)
        total_score = nace_score + data_score + financial_score + debt_penalty + inactive_penalty
        total_score = max(0, min(100, total_score))

        return {
            'score': total_score,
            'nace_relevance_score': nace_score,
            'data_completeness_score': data_score,
            'financial_health_score': financial_score,
            'debt_penalty': debt_penalty,
            'breakdown': breakdown,
        }

    def _calculate_nace_score(self, company: Company) -> tuple:
        """
        Calculate SK NACE relevance score (0-40 points).
        
        Scoring:
        - Exact target NACE match: 40 points
        - Related tech/business services: 20 points
        - Other: 0 points
        """
        breakdown = {'points': 0, 'nace_code': company.sk_NACE or '', 'reason': ''}

        if not company.sk_NACE:
            breakdown['reason'] = 'No SK NACE code'
            return 0, breakdown

        nace = company.sk_NACE.strip()

        # Check for exact match
        if nace in self.TARGET_NACE_CODES:
            breakdown['points'] = 40
            breakdown['reason'] = f'Target NACE code: {nace}'
            return 40, breakdown

        # Check for related tech codes (partial credit)
        if nace.startswith('62') or nace.startswith('63'):
            breakdown['points'] = 20
            breakdown['reason'] = f'Related IT/business services NACE: {nace}'
            return 20, breakdown

        breakdown['reason'] = f'Non-target NACE: {nace}'
        return 0, breakdown

    def _calculate_data_quality_score(self, company: Company) -> tuple:
        """
        Calculate data quality score (0-30 points).
        
        Scoring:
        - ORSR profile exists and synced recently: 10 points
        - Financial data available: 10 points
        - Sync health (no consecutive failures): 10 points
        """
        breakdown = {
            'points': 0,
            'orsr_present': False,
            'financials_present': False,
            'sync_health': 'unknown',
            'details': []
        }

        points = 0

        # 1. ORSR completeness
        try:
            orsr = company.orsr_profile
            if orsr and orsr.fetch_ok:
                breakdown['orsr_present'] = True
                points += 10
                breakdown['details'].append('ORSR profile synced successfully')

                # Bonus if recently synced (within 30 days)
                if orsr.last_synced_at and (timezone.now() - orsr.last_synced_at) < timedelta(days=30):
                    breakdown['details'].append('ORSR profile freshly synced (< 30 days)')
        except Exception as e:
            breakdown['details'].append(f'ORSR error: {str(e)[:50]}')

        # 2. Financial data
        try:
            if company.financial_results.exists():
                breakdown['financials_present'] = True
                points += 10
                latest_year = company.financial_results.order_by('-year').first()
                breakdown['details'].append(
                    f'Financial data available (latest: {latest_year.year if latest_year else "N/A"})')
        except Exception as e:
            breakdown['details'].append(f'Financial data error: {str(e)[:50]}')

        # 3. Sync health
        try:
            sync_statuses = CompanySyncStatus.objects.filter(company=company)
            if sync_statuses.exists():
                avg_failures = sync_statuses.aggregate(
                    avg=models.Avg('consecutive_failures')
                )['avg'] or 0

                if avg_failures < 2:
                    breakdown['sync_health'] = 'good'
                    points += 10
                    breakdown['details'].append(f'Good sync health (avg {avg_failures:.1f} failures)')
                elif avg_failures < 5:
                    breakdown['sync_health'] = 'fair'
                    points += 5
                    breakdown['details'].append(f'Fair sync health (avg {avg_failures:.1f} failures)')
                else:
                    breakdown['sync_health'] = 'poor'
                    breakdown['details'].append(f'Poor sync health (avg {avg_failures:.1f} failures)')
        except Exception as e:
            breakdown['details'].append(f'Sync health error: {str(e)[:50]}')

        breakdown['points'] = points
        return points, breakdown

    def _calculate_financial_health_score(self, company: Company) -> tuple:
        """
        Calculate financial health score (0-30 points).
        
        Scoring:
        - No debts: 20 points
        - Positive revenue trend (last 2 years): 10 points
        - Decent equity (> 30% assets): bonus
        """
        breakdown = {
            'points': 0,
            'has_debt': False,
            'debt_details': '',
            'revenue_trend': 'unknown',
            'equity_ratio': None,
            'details': []
        }

        points = 0

        # 1. Debt check
        total_debt = sum([
            float(company.debt_vszp or 0),
            float(company.debt_soc_poist or 0),
            float(company.tax_debt or 0),
        ])

        if total_debt > 0:
            breakdown['has_debt'] = True
            breakdown['debt_details'] = f'Total debt: €{total_debt:,.0f}'
            breakdown['details'].append(f'Company has debts: €{total_debt:,.0f}')
        else:
            points += 20
            breakdown['details'].append('No debts detected')

        # 2. Revenue trend
        try:
            financials = company.financial_results.order_by('-year')[:2]
            if len(financials) >= 2:
                latest = financials[0]
                previous = financials[1]

                if latest.revenue and previous.revenue:
                    latest_rev = float(latest.revenue)
                    prev_rev = float(previous.revenue)

                    if latest_rev > prev_rev:
                        breakdown['revenue_trend'] = 'growing'
                        points += 10
                        growth = ((latest_rev - prev_rev) / prev_rev) * 100
                        breakdown['details'].append(f'Revenue growing: +{growth:.1f}% YoY')
                    else:
                        breakdown['revenue_trend'] = 'declining'
                        decline = ((prev_rev - latest_rev) / prev_rev) * 100
                        breakdown['details'].append(f'Revenue declining: -{decline:.1f}% YoY')
            elif len(financials) == 1:
                breakdown['revenue_trend'] = 'single_year'
                points += 5
                breakdown['details'].append('Revenue data available (single year)')
        except Exception as e:
            breakdown['details'].append(f'Revenue trend error: {str(e)[:50]}')

        # 3. Equity ratio (bonus)
        try:
            latest_fin = company.financial_results.order_by('-year').first()
            if latest_fin and latest_fin.assets_total and latest_fin.equity:
                assets = float(latest_fin.assets_total)
                equity = float(latest_fin.equity)

                if assets > 0:
                    equity_ratio = (equity / assets) * 100
                    breakdown['equity_ratio'] = equity_ratio

                    if equity_ratio >= 30:
                        breakdown['details'].append(f'Strong equity ratio: {equity_ratio:.1f}%')
                    elif equity_ratio >= 0:
                        breakdown['details'].append(f'Equity ratio: {equity_ratio:.1f}%')
                    else:
                        breakdown['details'].append(f'Negative equity: {equity_ratio:.1f}%')
        except Exception as e:
            breakdown['details'].append(f'Equity ratio error: {str(e)[:50]}')

        breakdown['points'] = points
        return points, breakdown

    def _calculate_debt_penalty(self, company: Company) -> tuple:
        """
        Calculate debt-based penalties.
        
        - Any debt presence: -30 points
        """
        breakdown = {'penalty': 0, 'details': []}

        total_debt = sum([
            float(company.debt_vszp or 0),
            float(company.debt_soc_poist or 0),
            float(company.tax_debt or 0),
        ])

        if total_debt > 0:
            breakdown['penalty'] = self.DEBT_PENALTY
            breakdown['details'].append(f'Debt penalty: {self.DEBT_PENALTY} (total debt: €{total_debt:,.0f})')
        else:
            breakdown['details'].append('No debt penalty (clean financial status)')

        return breakdown['penalty'], breakdown

    def score_companies(self, queryset=None, target_nace_codes=None):
        """
        Score all companies (or filtered queryset) and save results.
        
        Args:
            queryset: Optional filtered queryset to score. If None, scores all active companies.
            target_nace_codes: Optional list of target NACE codes. If None, uses class default.
        
        Returns:
            tuple: (scored_count, created_count, updated_count)
        """
        from lead_scoring.models import CompanyScore

        if target_nace_codes:
            self.TARGET_NACE_CODES = target_nace_codes

        if queryset is None:
            # Score all active companies
            queryset = Company.objects.filter(datum_zrusenia__isnull=True)

        scored_count = 0
        created_count = 0
        updated_count = 0

        for company in queryset.iterator():
            try:
                score_data = self.calculate_score(company)

                score_obj, created = CompanyScore.objects.update_or_create(
                    company=company,
                    defaults={
                        'score': score_data['score'],
                        'nace_relevance_score': score_data['nace_relevance_score'],
                        'data_completeness_score': score_data['data_completeness_score'],
                        'financial_health_score': score_data['financial_health_score'],
                        'debt_penalty': score_data['debt_penalty'],
                        'breakdown': score_data['breakdown'],
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                scored_count += 1

                if scored_count % 100 == 0:
                    logger.info(f"Scored {scored_count} companies...")

            except Exception as e:
                logger.error(f"Error scoring company {company.ico}: {str(e)}")
                continue

        return scored_count, created_count, updated_count

    def get_top_companies(self, limit=20, min_score=0):
        """
        Get top-scoring companies.
        
        Returns:
            QuerySet of CompanyScore ordered by score, with company data.
        """
        from lead_scoring.models import CompanyScore

        return CompanyScore.objects.filter(
            score__gte=min_score
        ).select_related('company').order_by('-score')[:limit]
