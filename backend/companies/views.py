from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse
from .models import Company, Watchlist, SearchHistory
from .serializers import CompanyListSerializer, CompanyDetailSerializer, WatchlistSerializer, SearchHistorySerializer
from .services.pdf_report import get_company_report
from .services.peers import PEER_SCOPES, peers_for
from .throttles import PeersThrottle, ReportThrottle

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
        # `company__financial_results` because `riskScore` is now the real
        # score, and the real score reads the analysis. Without the prefetch
        # that is one query per watched company.
        return (
            Watchlist.objects.filter(user=self.request.user)
            .select_related('company')
            .prefetch_related('company__financial_results')
        )

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

    def get_throttles(self):
        """Limit the two actions that cost real work, and only those.

        `report` renders a PDF and `peers` counts across the whole register;
        both are reachable without an account. Listing, searching and
        retrieving a single company are unchanged -- a limit fitted to an
        endpoint nobody has abused yet is a limit that breaks a working page
        for the sake of a diagram. See `companies.throttles`.
        """
        if self.action == 'report':
            return [ReportThrottle()]
        if self.action == 'peers':
            return [PeersThrottle()]
        return []

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
        except Exception:
            # The traceback goes to the log and nowhere else. This endpoint is
            # public, and an exception's own text names tables, columns, file
            # paths and library internals -- a 500 is not a reason to hand a
            # reader the inside of the process.
            logger.exception(f"Error in retrieve for ICO {ico}")
            return Response(
                {"detail": "Pri načítaní firmy došlo k chybe. Skúste to prosím znova."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
        except Exception:
            # Same reason as `retrieve` above: the client gets a sentence, the
            # log gets the traceback.
            logger.exception(f"Error in search for {query!r}")
            return Response(
                {"detail": "Vyhľadávanie zlyhalo. Skúste to prosím znova."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
            pdf_bytes = get_company_report(company)
        except Exception:
            # Third site of the same shape as `retrieve` and `search` above, and
            # the one that leaked the most: the renderer wraps its own failure in
            # a `RuntimeError` whose text is the underlying exception, so this
            # endpoint answered an anonymous caller with an ImportError's module
            # path or a weasyprint traceback sentence. `CompanyViewSet` is
            # AllowAny, so there was no login between the two.
            logger.exception(f"PDF generation error for ICO {ico}")
            return Response(
                {"detail": "Report sa nepodarilo vygenerovať. Skúste to prosím znova."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        filename = f"{company.ico}_{company.nazov_UJ[:40].replace(' ', '_')}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['get'], url_path='peers')
    def peers(self, request, ico=None):
        """Companies ranked next to this one, in one scope.

        Four company-page sections read this. `scope` is required and closed:
        an unknown value is a 400 rather than a default, because every scope
        answers a different question and silently picking one would put the
        wrong ranking under the wrong heading.

        The rows are returned as the service built them rather than through a
        serializer. `CompanyDetailSerializer` exists to walk a model graph; a
        peer row is ten fields assembled by hand in `services/peers.py`, and a
        second declaration of that shape here is a second thing to update --
        `_row` is the one place it is defined.
        """
        scope = request.query_params.get('scope', '').strip()
        if scope not in PEER_SCOPES:
            return Response(
                {'detail': f'Neznámy rozsah "{scope}". Povolené: {", ".join(PEER_SCOPES)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            company = Company.objects.get(ico=ico)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Firma s týmto IČO nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return Response(peers_for(company, scope))
        except Exception:
            # Same contract as `retrieve`, `search` and `report` above: the
            # sentence goes to the caller, the traceback to the log.
            logger.exception(f"Peer ranking error for ICO {ico}, scope {scope}")
            return Response(
                {"detail": "Podobné firmy sa nepodarilo načítať. Skúste to prosím znova."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
