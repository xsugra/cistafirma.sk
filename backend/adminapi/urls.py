"""URL routing for /api/admin/*."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from adminapi.views import (
    AdminCompanyViewSet,
    AdminSubscriptionPlanViewSet,
    AdminUserViewSet,
    AuditLogViewSet,
    CompanySyncStatusViewSet,
    SyncJobViewSet,
    dashboard_business,
    dashboard_overview,
    dashboard_sync,
    dashboard_system,
    enter_focus_mode_view,
    exit_focus_mode_view,
    focus_mode_state,
    impersonate_user_view,
    queue_depths_view,
    scheduled_tasks_view,
    system_health_view,
    system_info_view,
    toggle_scheduled_task_view,
)

router = DefaultRouter()
router.register(r"sync/jobs", SyncJobViewSet, basename="syncjob")
router.register(r"sync/companies", CompanySyncStatusViewSet, basename="companysyncstatus")
router.register(r"companies", AdminCompanyViewSet, basename="admincompany")
router.register(r"users", AdminUserViewSet, basename="adminuser")
router.register(r"subscription-plans", AdminSubscriptionPlanViewSet, basename="adminplan")
router.register(r"audit", AuditLogViewSet, basename="auditlog")

urlpatterns = [
    # Dashboard / metrics
    path("metrics/overview/", dashboard_overview),
    path("metrics/sync/", dashboard_sync),
    path("metrics/business/", dashboard_business),
    path("metrics/system/", dashboard_system),

    # Focus mode
    path("sync/focus-mode/", focus_mode_state),
    path("sync/focus-mode/enter/", enter_focus_mode_view),
    path("sync/focus-mode/exit/", exit_focus_mode_view),

    # Queues + scheduled tasks
    path("sync/queues/", queue_depths_view),
    path("sync/scheduled/", scheduled_tasks_view),
    path("sync/scheduled/<int:pk>/toggle/", toggle_scheduled_task_view),

    # Impersonation (superuser only)
    path("users/<int:pk>/impersonate/", impersonate_user_view),

    # System
    path("system/health/", system_health_view),
    path("system/info/", system_info_view),

    # Routers (sync/jobs, sync/companies, companies, users, plans, audit)
    path("", include(router.urls)),
]
