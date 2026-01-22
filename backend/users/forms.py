from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User
# Tu musíme importovať model, aby ho Django Admin vedel zobraziť v dropdown menu
from subscriptions.models import SubscriptionPlan


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'first_name',
            'last_name'
        )


class CustomUserChangeForm(UserChangeForm):
    # Pridáme queryset pre subscription_plan, aby admin vedel, čo ponúknuť
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.all(),
        required=False
    )

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'subscription_plan',
            'is_active'
        )
