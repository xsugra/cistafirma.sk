"""Serializers for saved admin company filters."""

from rest_framework import serializers

from adminapi.models import SavedCompanyFilter


class SavedCompanyFilterSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)
    filters = serializers.JSONField()

    class Meta:
        model = SavedCompanyFilter
        fields = [
            "id",
            "user",
            "user_email",
            "name",
            "description",
            "filters",
            "is_favorite",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "user_email", "created_at", "updated_at"]

