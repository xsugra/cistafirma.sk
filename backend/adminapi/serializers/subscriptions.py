from rest_framework import serializers

from subscriptions.models import SubscriptionPlan


class AdminSubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
