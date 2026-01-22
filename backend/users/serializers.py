from rest_framework import serializers
from django.contrib.auth import get_user_model
from subscriptions.models import SubscriptionPlan

User = get_user_model()


# 1. Serializer pre Plán (aby frontend videl detaily)
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'name',
            'slug',
            'max_watched_companies',
            'price_eur'
        )


# 2. Registrácia
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'password',
            'first_name',
            'last_name'
        )
        extra_kwargs = {
            'username': {
                'required': False
            }
        }

    def create(self, validated_data):
        # Pri registrácii zatiaľ plán neriešime (alebo defaultneme na Free v signáloch)
        return User.objects.create_user(**validated_data)


# 3. Detail profilu (Login response / Profile fetch)
class UserDetailSerializer(serializers.ModelSerializer):
    # Vložíme celý objekt plánu, nie len ID
    subscription_plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'subscription_plan'
        )
