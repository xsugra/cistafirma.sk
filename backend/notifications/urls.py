from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register(r'events', NotificationViewSet, basename='notification-events')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preferences')

urlpatterns = [
    path('', include(router.urls)),
]
