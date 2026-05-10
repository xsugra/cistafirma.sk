from django.urls import path
from . import views

urlpatterns = [
    path('trigger-ruz-fetch/', views.trigger_fetch_ruz_data, name='trigger_ruz_fetch'),
    path('trigger-insurance-debt-check/', views.trigger_insurance_debt_data, name='trigger_insurance_debt_check'),
    path('trigger-fs-update/', views.trigger_fetch_fs_data, name='trigger_fs_update'),
    path('sync-dashboard/', views.sync_dashboard, name='registers_sync_dashboard'),
]
