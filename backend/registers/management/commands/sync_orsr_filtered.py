from django.core.management.base import BaseCommand
from companies.models import Company
from registers.eligibility import ORSR_ELIGIBLE_LEGAL_FORMS
from registers.scrapers.orsr_scraper import OrsrScraperError
from registers.services.orsr_sync import OrsrSyncService



class Command(BaseCommand):
    help = "Synchronizuje ORSR údaje len pre firmy zapísané v obchodnom registri."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ico",
            action="append",
            dest="icos",
            help="IČO na synchronizáciu (možno zadať viac krát). Ak je zadané, ignorujú sa ostatné filtre.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max počet firiem na synchronizáciu (default 50). Nastav 0 pre neobmedzené.",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Spracovať len firmy bez ORSR profilu.",
        )
        parser.add_argument(
            "--stale",
            action="store_true",
            help="Spracovať len profily bez nového structured payloadu (staré parser-výstupy).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Opakovať synchronizáciu aj keď profil existuje.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        only_missing = options["only_missing"]
        stale = options["stale"]
        force = options["force"]
        icos = options.get("icos") or []

        # Filter pre právne formy zapísané v ORSR + len aktívne firmy (bez dátumu zrušenia)
        if icos:
            companies = Company.objects.filter(ico__in=icos).order_by("ico")
        else:
            companies = Company.objects.filter(
                pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
                datum_zrusenia__isnull=True  # Len existujúce firmy
            ).order_by("id")

            if only_missing and not force:
                companies = companies.filter(orsr_profile__isnull=True)

            if stale:
                # Profily bez 'structured' kľúča v raw_payload = output starého parsera.
                companies = companies.filter(orsr_profile__isnull=False).exclude(
                    orsr_profile__raw_payload__structured__isnull=False
                )

            if limit and limit > 0:
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

