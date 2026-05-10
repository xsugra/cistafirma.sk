from rest_framework import viewsets

from adminapi.permissions import IsAdminStaff
from adminapi.serializers import AuditLogSerializer
from registers.models import AuditLog


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminStaff]
    queryset = AuditLog.objects.all().select_related("actor")
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if actor := params.get("actor"):
            qs = qs.filter(actor_id=actor)
        if action_filter := params.get("action"):
            qs = qs.filter(action__icontains=action_filter)
        if target_type := params.get("target_type"):
            qs = qs.filter(target_type=target_type)
        if target_id := params.get("target_id"):
            qs = qs.filter(target_id=target_id)
        return qs.order_by("-created_at")
