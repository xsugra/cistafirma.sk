# pri settings.py v priecinku backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/registers/', include('registers.urls')),

    # Používame re_path s regexom, ktorý zachytí všetko okrem existujúcich ciest
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]

# Iba pre lokálny vývoj bez Whitenoise (ak by si ho vypol)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
