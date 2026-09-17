"""Views for lead scoring API endpoints."""

from django.db import models
from django.db.models import Avg, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from companies.models import Company
from .models import CompanyScore, CompanyEnrichment
from .serializers import CompanyScoreSerializer, CompanyEnrichmentSerializer, LeadScoreReportSerializer
from .services.scoring import LeadScoringService


class CompanyScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for company lead scores.
    
    Endpoints:
    - GET /api/lead-scores/
    - GET /api/lead-scores/{id}/
    - GET /api/lead-scores/top/
    - GET /api/lead-scores/report/
    """

    queryset = CompanyScore.objects.select_related('company').order_by('-score')
    serializer_class = CompanyScoreSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ('score', 'nace_relevance_score')
    ordering_fields = ('score', 'updated_at', 'nace_relevance_score')
    search_fields = ('company__ico', 'company__nazov_UJ')

    @action(detail=False, methods=['get'])
    def top(self, request):
        """Get top-scoring companies."""
        limit = int(request.query_params.get('limit', 20))
        min_score = int(request.query_params.get('min_score', 0))

        top_scores = self.queryset.filter(score__gte=min_score)[:limit]
        serializer = self.get_serializer(top_scores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def report(self, request):
        """Get lead scoring report with statistics."""
        from django.db.models import Case, When, Value, IntegerField

        queryset = CompanyScore.objects.all()

        # Optimized: Single aggregate query for counts and avg
        counts = queryset.aggregate(
            total=Count('id'),
            avg_score=Avg('score'),
            high_count=Count('id', filter=Q(score__gte=70)),
            medium_count=Count('id', filter=Q(score__gte=50, score__lt=70)),
            low_count=Count('id', filter=Q(score__lt=50)),
        )

        total = counts['total']
        avg_score = counts['avg_score'] or 0
        high_count = counts['high_count']
        medium_count = counts['medium_count']
        low_count = counts['low_count']

        # Distribution by 10-point ranges - optimized
        distribution_data = queryset.values(
            score_range=Case(
                *[When(score__gte=i*10, score__lt=(i+1)*10, then=Value(f'{i*10}-{(i+1)*10}'))
                  for i in range(0, 11)],
                output_field=models.CharField(),
            )
        ).annotate(count=Count('id')).filter(score_range__isnull=False).order_by('score_range')

        distribution = {item['score_range']: item['count'] for item in distribution_data}

        top_companies = queryset.order_by('-score')[:10]
        last_scored = queryset.values_list('updated_at', flat=True).order_by('-updated_at').first()

        data = {
            'total_companies': total,
            'avg_score': round(avg_score, 2),
            'high_score_count': high_count,
            'medium_score_count': medium_count,
            'low_score_count': low_count,
            'top_companies': CompanyScoreSerializer(top_companies, many=True).data,
            'score_distribution': distribution,
            'last_scored_at': last_scored,
        }

        serializer = LeadScoreReportSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """
        Calculate scores for companies.
        
        Query params:
        - city: Filter by city
        - nace: Filter by NACE code
        - limit: Limit number of companies to score
        
        Returns: {scored_count, created_count, updated_count}
        """
        # Check permission
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff members can trigger scoring'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Build queryset
        queryset = Company.objects.filter(datum_zrusenia__isnull=True)

        city = request.query_params.get('city')
        if city:
            queryset = queryset.filter(mesto__icontains=city)

        nace = request.query_params.get('nace')
        if nace:
            queryset = queryset.filter(sk_NACE__contains=nace)

        limit = request.query_params.get('limit')
        if limit:
            queryset = queryset[:int(limit)]

        # Run scoring
        service = LeadScoringService()
        scored_count, created_count, updated_count = service.score_companies(queryset=queryset)

        return Response({
            'scored_count': scored_count,
            'created_count': created_count,
            'updated_count': updated_count,
        })


class CompanyEnrichmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for company enrichment data.
    
    Endpoints:
    - GET /api/enrichments/
    - GET /api/enrichments/{id}/
    - GET /api/enrichments/high-confidence/
    """

    queryset = CompanyEnrichment.objects.select_related('company').order_by('-confidence_score')
    serializer_class = CompanyEnrichmentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ('confidence_score',)
    ordering_fields = ('confidence_score', 'updated_at')
    search_fields = ('company__ico', 'company__nazov_UJ', 'company_summary')

    @action(detail=False, methods=['get'])
    def high_confidence(self, request):
        """Get enrichments with high confidence (>= 80)."""
        threshold = int(request.query_params.get('threshold', 80))
        enrichments = self.queryset.filter(confidence_score__gte=threshold)[:20]
        serializer = self.get_serializer(enrichments, many=True)
        return Response(serializer.data)
