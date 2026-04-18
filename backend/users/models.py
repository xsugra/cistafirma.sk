import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="ID",
    )
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_column="Email",
    )
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        blank=True,
        db_column="Username",
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        db_column="Meno",
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        db_column="Priezvisko",
    )
    # Odkazujeme na model v inej aplikácii pomocou stringu
    subscription_plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.SET_NULL,  # Ak zmažeme plán, užívateľ ostane (bez plánu)
        null=True,
        blank=True,
        related_name="users",
        db_column="Plán",
    )
    is_staff = models.BooleanField(
        default=False,
        db_column="STAFF",
    )
    is_active = models.BooleanField(
        default=True,
        db_column="Aktívny",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="Vytvorený",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column="Aktualizovaný",
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    class Meta:
        db_table = "Users"

    def __str__(self):
        return self.email
