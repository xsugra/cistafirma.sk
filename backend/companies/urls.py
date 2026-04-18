from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet

router = DefaultRouter()
router.register(r'', CompanyViewSet, basename='company')

urlpatterns = [
    # Router handles:
    # GET /api/companies/ - list
    # GET /api/companies/search/ - search action
    # GET /api/companies/<ico>/ - retrieve
    path('', include(router.urls)),
]
