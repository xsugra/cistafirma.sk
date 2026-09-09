"""Admin endpoints for persisted company filters."""

from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets

from adminapi.models import SavedCompanyFilter
from adminapi.permissions import IsAdminStaff
from adminapi.serializers.filters import SavedCompanyFilterSerializer


class SavedCompanyFilterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminStaff]
    serializer_class = SavedCompanyFilterSerializer
    pagination_class = PageNumberPagination

    class _Pagination(PageNumberPagination):
        page_size = 50

    pagination_class = _Pagination

    def get_queryset(self):
        qs = SavedCompanyFilter.objects.select_related("user")
        if not self.request.user.is_authenticated:
            return qs.none()
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

