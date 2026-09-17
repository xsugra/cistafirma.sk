from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from .models import User
# Tu musíme importovať model, aby ho Django Admin vedel zobraziť v dropdown menu
from subscriptions.models import SubscriptionPlan


class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'subscription_plan',
            'is_active',
            'is_staff',
            'is_superuser',
        )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError({'password2': 'Passwords do not match.'})

        if password1:
            password_validation.validate_password(password1, self.instance)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.save_m2m()
        return user


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
