from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Company
from .serializers import CompanyListSerializer, CompanyDetailSerializer
from django.db.models import Q


import logging
logger = logging.getLogger(__name__)


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
