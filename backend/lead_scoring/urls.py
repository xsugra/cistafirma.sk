"""URL routing for lead scoring app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CompanyScoreViewSet, CompanyEnrichmentViewSet

router = DefaultRouter()
router.register(r'scores', CompanyScoreViewSet, basename='company-score')
router.register(r'enrichments', CompanyEnrichmentViewSet, basename='company-enrichment')

urlpatterns = [
    path('', include(router.urls)),
]
