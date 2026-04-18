# pri settings.py v priecinku backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
import os


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
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz),
    path('api/auth/', include('users.urls')),
    path('api/registers/', include('registers.urls')),
    path('api/companies/', include('companies.urls')),
]

# Add frontend catch-all only if frontend is built, otherwise just root info
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Catch-all for SPA - but gracefully handle missing frontend
urlpatterns += [
    re_path(r'^$', frontend_or_api_info),  # Root URL
]
