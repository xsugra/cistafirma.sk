# pri settings.py v priecinku backend/urls.py
import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include, re_path
from django.views.generic import TemplateView

from companies.views import landing_stats, WatchlistViewSet, SearchHistoryViewSet
from core.metrics import metrics_view


def frontend_or_api_info(request):
    """Serve frontend if available, otherwise show API info."""
    # Check if frontend is built
    frontend_index = settings.FRONTEND_DIR / 'dist' / 'index.html'
    if os.path.exists(frontend_index):
        return TemplateView.as_view(template_name='index.html')(request)

    # Return API info for backend-only mode
    return JsonResponse({
        'status': 'ok',
        'message': 'CistaFirma Backend API',
        'admin': '/admin/',
        'api_endpoints': {
            'auth': '/api/auth/',
            'registers': '/api/registers/',
        }
    })


def healthz(request):
    """Readiness probe: verifies the DB and Redis, not just the WSGI process.

    Returns HTTP 503 when a critical dependency is unreachable so that
    orchestrators (Docker healthchecks, K8s probes) treat a degraded app as
    unhealthy instead of reporting a healthy process against a dead datastore.

    The body names *which* dependency is down and nothing more, unless the
    caller is on a private or loopback address. It used to interpolate the
    exception itself, and a Redis connection error's text carries the DSN it
    failed to reach -- `redis://:password@host:6379/0`. No probe reads this
    body; a human debugging a degraded stack reads the container log, where
    `logger.exception` has already put the traceback. So the detail cost
    nothing to withhold here and had a credential in it. In-cluster probes and
    the Docker healthcheck both arrive from private addresses, so they keep the
    full text; see `core.metrics.is_internal_client`.
    """
    import logging
    import time

    from django.core.cache import cache

    from core.metrics import is_internal_client

    logger = logging.getLogger(__name__)
    verbose = is_internal_client(request.META.get("REMOTE_ADDR"))
    status_code = 200
    health = {"status": "ok", "db": "unknown", "redis": "unknown"}

    try:
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        health["db"] = "ok"
    except Exception as exc:
        logger.exception("healthz: database check failed")
        health["db"] = f"error: {exc}" if verbose else "error"
        status_code = 503

    try:
        start = time.monotonic()
        # Round-trip through the configured Django Redis cache backend.
        cache.set("__healthz__", "1", timeout=5)
        cache.get("__healthz__")
        health["redis"] = f"ok ({time.monotonic() - start:.0f}ms)"
    except Exception as exc:
        logger.exception("healthz: redis check failed")
        health["redis"] = f"error: {exc}" if verbose else "error"
        status_code = 503

    if status_code != 200:
        health["status"] = "degraded"

    return JsonResponse(health, status=status_code)


watchlist_list = WatchlistViewSet.as_view({'get': 'list', 'post': 'create'})
watchlist_detail = WatchlistViewSet.as_view({'delete': 'destroy'})
history_list = SearchHistoryViewSet.as_view({'get': 'list'})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz),
    # Prometheus scrape target. Internal-only — see core/metrics.py: private and
    # loopback clients, or a bearer METRICS_TOKEN when one is configured;
    # everyone else gets the same 404 as an unknown URL. Both spellings are
    # registered so a scrape never depends on an APPEND_SLASH redirect.
    path("metrics", metrics_view),
    path("metrics/", metrics_view),
    path('api/auth/', include('users.urls')),
    path('api/registers/', include('registers.urls')),
    path('api/stats/landing/', landing_stats),
    path('api/companies/', include('companies.urls')),
    path('api/watchlist/', watchlist_list, name='watchlist-list'),
    path('api/watchlist/<int:pk>/', watchlist_detail, name='watchlist-detail'),
    path('api/history/', history_list, name='history-list'),
    path('api/admin/', include('adminapi.urls')),
    path('api/lead-scoring/', include('lead_scoring.urls')),
    path('api/', include('connections.urls')),
    path('api/notifications/', include('notifications.urls')),
]

# Add frontend catch-all only if frontend is built, otherwise just root info
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Catch-all for SPA - but gracefully handle missing frontend
urlpatterns += [
    re_path(r'^$', frontend_or_api_info),  # Root URL
]
