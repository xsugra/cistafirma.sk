"""Celery tasks for lead scoring."""

import logging

from celery import shared_task

from lead_scoring.services.scoring import LeadScoringService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def score_companies_task(self, city=None, nace=None, limit=None):
    """
    Background task to score companies.

    Args:
        city: Optional city filter
        nace: Optional NACE code filter
        limit: Optional limit on companies to score

    Returns:
        dict with scored_count, created_count, updated_count
    """
    try:
        from companies.models import Company

        service = LeadScoringService()

        # Build queryset
        queryset = Company.objects.filter(datum_zrusenia__isnull=True)

        if city:
            queryset = queryset.filter(mesto__icontains=city)

        if nace:
            queryset = queryset.filter(sk_NACE__contains=nace)

        if limit:
            queryset = queryset[:int(limit)]

        # Run scoring
        scored_count, created_count, updated_count = service.score_companies(queryset=queryset)

        logger.info(f"Scoring complete: {scored_count} scored, {created_count} created, {updated_count} updated")

        return {
            'scored_count': scored_count,
            'created_count': created_count,
            'updated_count': updated_count,
        }

    except Exception as exc:
        logger.error(f"Error in score_companies_task: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def score_single_company(company_ico):
    """
    Score a single company by ICO.

    Args:
        company_ico: Company ICO code

    Returns:
        dict with score data
    """
    try:
        from companies.models import Company
        from lead_scoring.models import CompanyScore

        company = Company.objects.get(ico=company_ico)
        service = LeadScoringService()

        score_data = service.calculate_score(company)

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

        logger.info(f"Scored company {company_ico}: {score_data['score']} points")

        return score_data

    except Company.DoesNotExist:
        logger.error(f"Company not found: {company_ico}")
        return None
    except Exception as exc:
        logger.error(f"Error scoring company {company_ico}: {str(exc)}")
        raise
