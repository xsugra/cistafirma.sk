from django.contrib.auth import get_user_model
from rest_framework import serializers

from subscriptions.models import SubscriptionPlan

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    subscription_plan_name = serializers.CharField(
        source="subscription_plan.name", read_only=True, default=None
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "subscription_plan",
            "subscription_plan_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created_at",
        ]
        read_only_fields = ["id", "last_login", "created_at"]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "password",
            "first_name",
            "last_name",
            "subscription_plan",
            "is_active",
            "is_staff",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
