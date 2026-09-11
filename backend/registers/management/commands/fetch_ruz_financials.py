from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from companies.models import Company
from registers.services.ruz_financials_sync import FinancialsOutcome, sync_company_and_record
from registers.tasks import financials_sync_batch


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
            "--ico-file",
            dest="ico_file",
            help=(
                "Subor s ICO, jedno na riadok (prazdne riadky a riadky zacinajuce "
                "'#' sa preskocia). Pre vzorky vacsie ako par firiem."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Limit poctu firiem pri batch rezime (default 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Iba vypise vybranu mnozinu firiem. Nespravi ziadny sietovy "
                "poziadavok a nic nezapise -- na overenie vyberu pred spustenim."
            ),
        )

    def handle(self, *args, **options):
        icos = self._collect_icos(options)
        limit = options["limit"]
        dry_run = options["dry_run"]

        if icos:
            companies = list(Company.objects.filter(ico__in=icos).order_by("ico"))
            missing = sorted(set(icos) - {company.ico for company in companies})
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"V databaze sa nenaslo {len(missing)} ICO: {', '.join(missing[:10])}"
                        + (" ..." if len(missing) > 10 else "")
                    )
                )
        else:
            # The batch rotation, not `order_by("id")[:limit]`. The old selection
            # had no cursor, so running this twice with the same `--limit`
            # processed the same companies both times -- the same defect the
            # beat had, on the path an operator uses to catch up by hand.
            #
            # This narrows the population to what the beat draws from:
            # ORSR-eligible legal forms, not dissolved. That is
            # `financials_sync_batch`'s default and therefore the backlog the
            # scheduled run is working through, which is the one a manual
            # catch-up should be helping with. `--ico` / `--ico-file` are
            # unchanged and still reach any company at all.
            company_ids = financials_sync_batch(limit)
            by_id = Company.objects.in_bulk(company_ids)
            # Rebuilt in the batch's order rather than the database's: retries
            # first, which is the order they are about to be processed in.
            companies = [by_id[pk] for pk in company_ids if pk in by_id]

        total = len(companies)
        self.stdout.write(
            self.style.SUCCESS(f"RUZ financial sync: planovanych {total} firiem")
        )

        if dry_run:
            for company in companies:
                self.stdout.write(f"  {company.ico}  {company.nazov_UJ}")
            self.stdout.write(
                self.style.SUCCESS(f"Dry-run: {total} firiem, nic sa nezapisalo.")
            )
            return

        outcomes = Counter()
        failures = []
        synced_rows = 0

        # A `RuzUnreachable` comes back as an outcome, not an exception, so one
        # unreachable registry no longer kills the batch -- which is what the
        # previous version would have done the moment the client stopped
        # folding transport errors into `None`. Anything that *does* raise is a
        # bug in the reading code; it is recorded against the company and the
        # batch keeps going, because a 136-company sample that dies on company
        # 91 tells the operator nothing about the other 135.
        for index, company in enumerate(companies, start=1):
            try:
                result = sync_company_and_record(company)
            except Exception as exc:  # noqa: BLE001 -- reported, batch continues
                failures.append((company.ico, f"{type(exc).__name__}: {exc}"))
                self.stdout.write(
                    self.style.ERROR(f"[{index}/{total}] {company.ico}: CHYBA {exc}")
                )
                continue

            outcomes[result.outcome] += 1
            synced_rows += result.rows
            self.stdout.write(
                f"[{index}/{total}] {company.ico}: {result.outcome.value} "
                f"roky={result.rows}"
                + (f" ({result.detail})" if result.detail else "")
            )

        self.stdout.write("")
        for outcome in FinancialsOutcome:
            self.stdout.write(f"  {outcome.value:<14} {outcomes[outcome]}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Dokoncene. Firiem so zaznamenanymi datami: "
                f"{outcomes[FinancialsOutcome.RECORDED]}/{total}, "
                f"ulozenych riadkov: {synced_rows}, nezodpovedanych: "
                f"{outcomes[FinancialsOutcome.UNREACHABLE]}, chyb: {len(failures)}"
            )
        )
        if failures:
            self.stdout.write(self.style.ERROR("Chyby:"))
            for ico, message in failures:
                self.stdout.write(self.style.ERROR(f"  {ico}: {message}"))

    def _collect_icos(self, options) -> list[str]:
        icos = list(options.get("icos") or [])
        ico_file = options.get("ico_file")
        if not ico_file:
            return icos

        try:
            with open(ico_file, encoding="utf-8") as handle:
                for line in handle:
                    entry = line.strip()
                    if entry and not entry.startswith("#"):
                        icos.append(entry)
        except OSError as exc:
            raise CommandError(f"Subor s ICO sa nepodarilo precitat: {exc}") from exc
        return icos
