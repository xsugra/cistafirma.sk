import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    email = models.EmailField(
        _('email address'),
        unique=True
    )
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        blank=True
    )

    first_name = models.CharField(
        max_length=100,
        blank=True
    )
    last_name = models.CharField(
        max_length=100,
        blank=True
    )

    # Odkazujeme na model v inej aplikácii pomocou stringu
    subscription_plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.SET_NULL,  # Ak zmažeme plán, užívateľ ostane (bez plánu)
        null=True,
        blank=True,
        related_name="users"
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    def __str__(self):
        return self.email
