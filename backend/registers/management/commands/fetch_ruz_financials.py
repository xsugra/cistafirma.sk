from django.core.management.base import BaseCommand

from companies.models import Company
from registers.services.ruz_financials_sync import RuzFinancialsSyncService


class Command(BaseCommand):
    help = "Stiahne hospodarske vysledky firmy/iriem z RUZ API a ulozi ich do CompanyFinancialResult."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ico",
            action="append",
            dest="icos",
            help="ICO na synchronizaciu (moze byt uvedene viac krat).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Limit poctu firiem pri batch rezime (default 100).",
        )

    def handle(self, *args, **options):
        service = RuzFinancialsSyncService()
        icos = options.get("icos") or []
        limit = options["limit"]

        if icos:
            companies = Company.objects.filter(ico__in=icos).order_by("ico")
        else:
            companies = Company.objects.order_by("id")[:limit]

        total = companies.count()
        self.stdout.write(self.style.SUCCESS(f"RUZ financial sync: planovanych {total} firiem"))

        synced_companies = 0
        synced_rows = 0

        for company in companies:
            upserts = service.sync_company(company)
            synced_rows += upserts
            if upserts > 0:
                synced_companies += 1
            self.stdout.write(
                f"[{synced_companies}/{total}] {company.ico}: ulozene roky={upserts}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Dokoncene. Firmy s datami: {synced_companies}/{total}, ulozenych riadkov: {synced_rows}"
            )
        )

