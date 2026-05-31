from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import NotificationEvent, NotificationPreference
from .serializers import NotificationEventSerializer, NotificationPreferenceSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """User's notification events (read-only)."""

    serializer_class = NotificationEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationEvent.objects.filter(user=self.request.user).order_by('-created_at')[:50]


class NotificationPreferenceViewSet(viewsets.GenericViewSet):
    """User's notification preferences (get + update)."""

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        pref, _ = NotificationPreference.objects.get_or_create(
            user=self.request.user,
            defaults={
                'email_enabled': True,
                'on_debt_change': True,
                'on_status_change': True,
                'on_executive_change': False,
            },
        )
        return pref

    def list(self, request):
        pref = self.get_object()
        return Response(NotificationPreferenceSerializer(pref).data)

    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        pref = self.get_object()
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
