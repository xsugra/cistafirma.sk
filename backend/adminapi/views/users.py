"""Admin user management + impersonation."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from adminapi.permissions import IsAdminStaff, IsSuperUser
from adminapi.serializers import AdminUserCreateSerializer, AdminUserSerializer
from registers.models import AuditLog

User = get_user_model()


class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminStaff]
    queryset = User.objects.all().select_related("subscription_plan")

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(email__icontains=q) | qs.filter(username__icontains=q)
        if plan := params.get("plan"):
            qs = qs.filter(subscription_plan_id=plan)
        if is_staff := params.get("is_staff"):
            qs = qs.filter(is_staff=is_staff in ("1", "true", "True"))
        if is_active := params.get("is_active"):
            qs = qs.filter(is_active=is_active in ("1", "true", "True"))
        return qs.order_by("-created_at")


@api_view(["POST"])
@permission_classes([IsSuperUser])
def impersonate_user_view(request, pk: int):
    """Generate a JWT pair for the target user. Superuser only."""
    target = get_object_or_404(User, pk=pk)
    refresh = RefreshToken.for_user(target)
    AuditLog.objects.create(
        actor=request.user,
        action="user.impersonate",
        target_type="user",
        target_id=str(target.pk),
        payload={"target_email": target.email},
    )
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user_email": target.email,
    })
