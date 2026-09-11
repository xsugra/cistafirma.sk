from django.core.management.base import BaseCommand

from companies.models import Company
from registers.scrapers.orsr_scraper import OrsrScraperError
from registers.services.orsr_sync import OrsrSyncService
from registers.services.sync_engine import _classify_error, record_orsr_outcome


class Command(BaseCommand):
    help = "Stiahne a uloží ORSR údaje pre firmy podľa IČO."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ico",
            action="append",
            dest="icos",
            help="IČO na synchronizáciu (možno zadať viac krát).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Max počet firiem pri dávkovom režime (default 100).",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Spracovať len firmy bez ORSR profilu.",
        )

    def handle(self, *args, **options):
        service = OrsrSyncService()
        icos = options.get("icos") or []
        only_missing = options["only_missing"]
        limit = options["limit"]

        if icos:
            companies = Company.objects.filter(ico__in=icos).order_by("ico")
        else:
            companies = Company.objects.all().order_by("id")
            if only_missing:
                companies = companies.filter(orsr_profile__isnull=True)
            companies = companies[:limit]

        total = companies.count() if hasattr(companies, "count") else len(companies)
        self.stdout.write(self.style.SUCCESS(f"ORSR sync: plánovaných {total} firiem"))

        ok = 0
        failed = 0

        for company in companies:
            try:
                profile = service.sync_company(company)
                # Recorded here as well as in the Celery task, because this is
                # a real ORSR driver and not a diagnostic: an attempt that
                # leaves no `CompanySyncStatus` row is invisible to
                # `source_health` and enters no retry lane, which is the whole
                # reason ORSR had no writer.
                record_orsr_outcome(
                    company, fetch_ok=profile.fetch_ok, error=profile.last_error
                )
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{ok + failed}/{total}] OK {company.ico} -> oddiel={profile.oddiel} vlozka={profile.vlozka_cislo}"
                    )
                )
            except OrsrScraperError as exc:
                failed += 1
                record_orsr_outcome(
                    company,
                    fetch_ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    error_type="network",
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"[{ok + failed}/{total}] FAIL {company.ico}: {exc}"
                    )
                )
            except Exception as exc:
                # Not caught before, so it aborted the batch -- and still does.
                # Recorded on the way out for the same reason the task does:
                # otherwise the company leaves no trace of having been
                # attempted, and this command is one of the paths that can put
                # it there.
                record_orsr_outcome(
                    company,
                    fetch_ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    error_type=_classify_error(exc),
                )
                raise

        self.stdout.write(
            self.style.SUCCESS(
                f"ORSR sync dokončený. Úspech: {ok}, Neúspech: {failed}, Spolu: {total}"
            )
        )

