from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'individuals', views.IndividualEntityViewSet, basename='individual')

urlpatterns = [
    # Legacy Django view paths
    path('trigger-ruz-fetch/', views.trigger_fetch_ruz_data, name='trigger_ruz_fetch'),
    path('trigger-insurance-debt-check/', views.trigger_insurance_debt_data, name='trigger_insurance_debt_check'),
    path('trigger-fs-update/', views.trigger_fetch_fs_data, name='trigger_fs_update'),
    path('sync-dashboard/', views.sync_dashboard, name='registers_sync_dashboard'),

    # REST API routes
    path('', include(router.urls)),
]
