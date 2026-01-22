import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class SubscriptionPlan(models.Model):
    """
    Definuje parametre pre Plus, Pro, Business plány.
    """
    PLAN_TYPES = (
        ('free', 'Free'),
        ('plus', 'Plus'),
        ('pro', 'Pro'),
        ('business', 'Business'),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(max_length=100)  # Napr. "Business Plan"
    slug = models.SlugField(
        max_length=50,
        unique=True,
        choices=PLAN_TYPES
    )  # Napr. "business" - pre kód

    # Limity
    max_watched_companies = models.IntegerField(
        default=10,
        help_text="Koľko firiem môže sledovať"
    )
    pdf_reports_per_month = models.IntegerField(
        default=1,
        help_text="Koľko reportov môže stiahnuť"
    )

    # Cena (pre info, reálna platba pôjde cez Stripe/Gateway)
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.price_eur}€)"
