"""Admin company CRUD with rich filtering."""
from rest_framework import viewsets

from adminapi.permissions import IsAdminStaff
from adminapi.serializers import (
    AdminCompanyDetailSerializer,
    AdminCompanyListSerializer,
)
from companies.models import Company


class AdminCompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminStaff]
    queryset = Company.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return AdminCompanyListSerializer
        return AdminCompanyDetailSerializer

    def get_queryset(self):
        qs = Company.objects.all()
        if self.action == "retrieve":
            qs = qs.prefetch_related("financial_results", "sync_statuses")
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(
                # Match ICO or name (case-insensitive)
                ico__icontains=q
            ) | qs.filter(nazov_UJ__icontains=q)
        if pf := params.get("pravna_forma"):
            qs = qs.filter(pravna_forma=pf)
        if active := params.get("active"):
            if active in ("1", "true", "True"):
                qs = qs.filter(datum_zrusenia__isnull=True)
            else:
                qs = qs.filter(datum_zrusenia__isnull=False)
        return qs.order_by("-id")
