from rest_framework import viewsets

from adminapi.permissions import IsAdminStaff
from adminapi.serializers import AdminSubscriptionPlanSerializer
from subscriptions.models import SubscriptionPlan


class AdminSubscriptionPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminStaff]
    queryset = SubscriptionPlan.objects.all()
    serializer_class = AdminSubscriptionPlanSerializer
