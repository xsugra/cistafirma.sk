from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse
from .models import Company, Watchlist, SearchHistory
from .serializers import CompanyListSerializer, CompanyDetailSerializer, WatchlistSerializer, SearchHistorySerializer
from .services.pdf_report import generate_company_report

import logging
logger = logging.getLogger(__name__)


@api_view(['GET'])
@perm_classes([permissions.AllowAny])
def landing_stats(request):
    today = timezone.now().date()
    companies_indexed = Company.objects.count()
    risky = Company.objects.filter(
        Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
    ).count()
    daily_checks = Company.objects.filter(
        datum_poslednej_upravy=today
    ).count()
    return Response({
        'companiesIndexed': companies_indexed,
        'dailyChecks': daily_checks,
        'riskyCompaniesDetected': risky,
    })


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).select_related('company')

    def create(self, request, *args, **kwargs):
        ico = request.data.get('ico', '').strip()
        if not ico:
            return Response({'detail': 'IČO je povinné.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            company = Company.objects.get(ico=ico)
        except Company.DoesNotExist:
            return Response({'detail': 'Firma s týmto IČO neexistuje.'}, status=status.HTTP_404_NOT_FOUND)
        obj, created = Watchlist.objects.get_or_create(user=request.user, company=company)
        if not created:
            return Response({'detail': 'Firma je už vo watchliste.'}, status=status.HTTP_200_OK)
        return Response(WatchlistSerializer(obj).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchHistoryViewSet(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin):
    """User's search history (read-only list)."""

    serializer_class = SearchHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SearchHistory.objects.filter(user=self.request.user).order_by('-searched_at')[:50]


def _save_search_history(user, ico: str, name: str):
    """Save a search history entry, deduplicating recent same-ICO entries."""
    if not user or not user.is_authenticated:
        return
    # Update timestamp if same ICO was searched in last 5 minutes (dedup)
    recent = SearchHistory.objects.filter(
        user=user, ico=ico,
        searched_at__gte=timezone.now() - timezone.timedelta(minutes=5),
    ).first()
    if recent:
        recent.name = name
        recent.save(update_fields=['name', 'searched_at'])
    else:
        SearchHistory.objects.create(user=user, ico=ico, name=name)


class CompanyListPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows companies to be viewed or searched.
    """
    queryset = Company.objects.all()
    serializer_class = CompanyListSerializer
    permission_classes = [permissions.AllowAny] # Zmena z predvoleného IsAuthenticated
    pagination_class = CompanyListPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['ico', 'nazov_UJ']
    lookup_field = 'ico'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CompanyDetailSerializer
        return CompanyListSerializer

    def retrieve(self, request, *args, **kwargs):
        ico = kwargs.get('ico')
        logger.info(f"Retrieving company with ICO: {ico}")
        try:
            company = Company.objects.select_related('orsr_profile').prefetch_related('financial_results').get(ico=ico)
            _save_search_history(request.user, ico, company.nazov_UJ)
            logger.info(f"Found company: {company.nazov_UJ}, starting serialization...")
            serializer = CompanyDetailSerializer(company)
            data = serializer.data
            logger.info("Serialization finished, returning response.")
            return Response(data)
        except Company.DoesNotExist:
            logger.warning(f"Company with ICO {ico} not found.")
            return Response(
                {"detail": "Firma s týmto IČO nebola nájdená v našej databáze."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in retrieve: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '').strip()
        logger.info(f"Searching for: {query}")
        if not query:
            return Response({"results": []})
        
        try:
            if query.isdigit():
                company = Company.objects.filter(ico=query).first()
                if company:
                    _save_search_history(request.user, query, company.nazov_UJ)
                    logger.info(f"Found exact ICO match: {company.nazov_UJ}")
                    return Response({"results": [CompanyListSerializer(company).data]})
            
            companies = Company.objects.filter(
                nazov_UJ__istartswith=query
            ).order_by('nazov_UJ')[:10]
            
            logger.info(f"Found {len(companies)} results for name search, serializing...")
            serializer = CompanyListSerializer(companies, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            logger.error(f"Error in search: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, ico=None):
        """Generate and download a PDF company report."""
        logger.info(f"Generating PDF report for company with ICO: {ico}")
        try:
            company = Company.objects.select_related('orsr_profile').prefetch_related('financial_results').get(ico=ico)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Firma s týmto IČO nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            pdf_bytes = generate_company_report(company)
        except Exception as e:
            logger.error(f"PDF generation error for ICO {ico}: {e}", exc_info=True)
            return Response(
                {"detail": f"Nepodarilo sa vygenerovať PDF: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        filename = f"{company.ico}_{company.nazov_UJ[:40].replace(' ', '_')}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
