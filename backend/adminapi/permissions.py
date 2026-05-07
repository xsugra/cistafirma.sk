"""Custom DRF permissions for admin API."""

from rest_framework.permissions import BasePermission


class IsAdminStaff(BasePermission):
    """Authenticated user with `is_staff=True`."""

    message = "Admin staff access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)


class IsSuperUser(BasePermission):
    """Authenticated user with `is_superuser=True`. Use for destructive actions."""

    message = "Superuser access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_superuser)
