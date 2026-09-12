import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class SubscriptionPlan(models.Model):
    """
    Definuje parametre pre Plus, Pro, Business plány.

    **Both limits below are decorative: nothing reads them to allow or deny
    anything.** Grep confirms it -- `max_watched_companies` appears in the admin,
    in two serializers and in a test, and in no view; `pdf_reports_per_month`
    appears only in the admin. The only limits this project actually applies are
    the DRF throttles in `companies/throttles.py`.

    That is a recorded decision and not an oversight, for
    `pdf_reports_per_month` in particular:

    - Nothing counts a reader's report downloads. Enforcing a monthly quota
      needs a usage row (or a cache counter) written on every report, which puts
      a new failure mode in the download path -- a quota check that cannot read
      its counter either blocks a working feature or silently allows it.
    - The server-side report endpoint (`GET /api/companies/<ico>/report/`) has
      no frontend caller; the page builds its PDF in the browser
      (`frontend/utils/pdfExport.ts`). A server quota would therefore gate a
      route nobody uses while the real download path stayed unlimited. A
      control that reads healthy while doing nothing is the defect class this
      codebase treats as a bug -- see `docs/OBSERVABILITY.md`.
    - No plan is demonstrably sold: there is no payment integration, and the
      price field exists only as a comment about Stripe.

    What would have to be true first: a metered resource, a paying customer, and
    an endpoint that is the only way to reach it. Until then the honest state is
    that these are labels: `subscriptions/admin.py` prints them in a column and
    `users/serializers.py` publishes them to the profile, and neither claims
    they are enforced. This docstring is the claim, so that the next person does
    not have to grep to find out whether a limit they can see is a limit that
    runs.
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
        editable=False,
        db_column="ID",
    )
    name = models.CharField(
        max_length=100,
        db_column="Názov",
    )  # Napr. "Business Plan"

    slug = models.SlugField(
        max_length=50,
        unique=True,
        choices=PLAN_TYPES,
        db_column="Slug",
    )  # Napr. "business" - pre kód

    # Limity
    max_watched_companies = models.IntegerField(
        default=10,
        help_text="Koľko firiem môže sledovať",
        db_column="Max. Firiem",
    )
    pdf_reports_per_month = models.IntegerField(
        default=1,
        help_text="Koľko reportov môže stiahnuť",
        db_column="Max. PDF reportov",
    )

    # Cena (pre info, reálna platba pôjde cez Stripe/Gateway)
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        db_column="Cena",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="Vytvorený",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column="Upravený",
    )

    class Meta:
        db_table = "Subscription Plans"

    def __str__(self):
        return f"{self.name} ({self.price_eur}€)"
