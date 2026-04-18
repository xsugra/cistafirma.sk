from django.core.management.base import BaseCommand
from companies.models import Company
from registers.scrapers.orsr_scraper import OrsrScraperError
from registers.services.orsr_sync import OrsrSyncService

# Právne formy zapísané v obchodnom registri (ORSR)
ORSR_ELIGIBLE_LEGAL_FORMS = {
    '111',  # Verejná obchodná spoločnosť
    '112',  # Spoločnosť s ručením obmedzeným
    '113',  # Komanditná spoločnosť
    '121',  # Akciová spoločnosť
    '122',  # Európske zoskupenie hospodárskych záujmov
    '123',  # Evropská spoločnosť
    '124',  # Európske družstvo
    '205',  # Družstvo
    '301',  # Štátny podnik
    '421',  # Zahraničná právnická osoba
    '804',  # EZÚS
}


class Command(BaseCommand):
    help = "Synchronizuje ORSR údaje len pre firmy zapísané v obchodnom registri."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max počet firiem na synchronizáciu (default 50).",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Spracovať len firmy bez ORSR profilu.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Opakovať synchronizáciu aj keď profil existuje.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        only_missing = options["only_missing"]
        force = options["force"]

        # Filter pre právne formy zapísané v ORSR
        companies = Company.objects.filter(
            pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS
        ).order_by("id")

        if only_missing and not force:
            companies = companies.filter(orsr_profile__isnull=True)

        companies = companies[:limit]

        total = companies.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"🔄 ORSR synchronizácia: {total} firiem (právne formy: {', '.join(sorted(ORSR_ELIGIBLE_LEGAL_FORMS))})"
            )
        )

        service = OrsrSyncService()
        ok = 0
        failed = 0
        skipped = 0

        for idx, company in enumerate(companies, 1):
            try:
                profile = service.sync_company(company)
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{idx}/{total}] ✓ {company.ico} {company.nazov_UJ[:40]}"
                    )
                )
            except OrsrScraperError as exc:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[{idx}/{total}] ✗ {company.ico}: {exc}"
                    )
                )
            except Exception as exc:
                skipped += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{idx}/{total}] ⊘ {company.ico}: {type(exc).__name__}: {exc}"
                    )
                )

        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ ORSR sync HOTOVO\n"
                f"  Úspešne: {ok}\n"
                f"  Neúspešne: {failed}\n"
                f"  Chyby: {skipped}\n"
                f"  CELKEM: {total}"
            )
        )

