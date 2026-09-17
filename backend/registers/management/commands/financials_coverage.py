from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from companies.models import Company, CompanyFinancialResult
from registers.eligibility import ORSR_ELIGIBLE_LEGAL_FORMS
from registers.models import CompanySyncStatus
from registers.services.sync_engine import sync_due_q


class Command(BaseCommand):
    """Read-only instrumentation for the financials import.

    Written because the defect being fixed was invisible: coverage had stopped
    at 309 companies and nothing anywhere said so. A number that has to be
    reconstructed with an ad-hoc shell one-liner is a number nobody checks, so
    "how far has this import actually got?" is now a command that writes
    nothing and can be run at any time, including against production.

    The split that matters is `attempted` versus `never attempted`. Before this,
    both read as "no financial data", which is precisely the ambiguity that let
    the rotation stand still for 32 runs.
    """

    help = "Vypise pokrytie importu uctovnych zavierok (read-only, nic nemeni)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--top",
            type=int,
            default=0,
            help="Kolko najnovsich rokov rozpisat (0 = ziadne).",
        )

    def handle(self, *args, **options):
        eligible = Company.objects.filter(
            pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
            datum_zrusenia__isnull=True,
        )
        eligible_total = eligible.count()

        statuses = CompanySyncStatus.objects.filter(
            source=CompanySyncStatus.SOURCE_FINANCIALS
        )
        attempted = statuses.count()
        blocked = statuses.filter(is_blocked=True).count()
        failing = statuses.filter(consecutive_failures__gt=0).count()
        ever_succeeded = statuses.filter(last_succeeded_at__isnull=False).count()

        with_results = (
            CompanyFinancialResult.objects.values("company_id").distinct().count()
        )
        rows = CompanyFinancialResult.objects.count()

        self.stdout.write("Pokrytie importu uctovnych zavierok (RUZ)")
        self.stdout.write("")
        self.stdout.write(f"  Firmy celkom                              {Company.objects.count()}")
        self.stdout.write(f"  Eligible (ORSR formy, nezrusene)          {eligible_total}")
        self.stdout.write(f"  Eligible bez statusu = NIKDY NESKUSANE    {self._never_attempted(eligible)}")
        self.stdout.write("")
        self.stdout.write(f"  Pokusy (CompanySyncStatus=financials)     {attempted}")
        self.stdout.write(f"    z toho niekedy uspesne                  {ever_succeeded}")
        self.stdout.write(f"    z toho so zlyhaniami                    {failing}")
        self.stdout.write(f"    z toho blokovane                        {blocked}")
        due = statuses.filter(is_blocked=False).filter(
            sync_due_q("next_retry_at", timezone.now())
        ).count()
        self.stdout.write(f"  Due teraz (opakovania)                    {due}")
        self.stdout.write("")
        self.stdout.write(f"  Firmy s ulozenym vysledkom                {with_results}")
        self.stdout.write(f"  Riadkov CompanyFinancialResult            {rows}")

        top = options["top"]
        if top:
            self.stdout.write("")
            self.stdout.write(f"  Najnovsie roky (top {top}):")
            for row in (
                CompanyFinancialResult.objects.values("year")
                .annotate(companies=Count("company_id", distinct=True))
                .order_by("-year")[:top]
            ):
                self.stdout.write(
                    f"    {row['year']}: {row['companies']} firiem"
                )
            newest = (
                CompanyFinancialResult.objects.order_by("-year")
                .values_list("year", flat=True)
                .first()
            )
            if newest:
                latest = CompanyFinancialResult.objects.filter(year=newest)
                self.stdout.write(
                    f"    rok {newest}: obrat spolu "
                    f"{latest.aggregate(total=Sum('revenue'))['total']}"
                )

    def _never_attempted(self, eligible) -> int:
        return eligible.exclude(
            id__in=CompanySyncStatus.objects.filter(
                source=CompanySyncStatus.SOURCE_FINANCIALS
            ).values("company_id")
        ).count()
