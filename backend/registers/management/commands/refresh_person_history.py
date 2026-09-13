from django.core.management.base import BaseCommand, CommandError

from companies.models import Company
from registers.models import OrsrCompanyProfile
from registers.services.rpo_sync import PERSON_HISTORY_KEY, pending_person_history
from registers.tasks import read_person_history


class Command(BaseCommand):
    help = (
        "Znovu precita historii osob (zanik funkcii) pre firmy, ktore stary "
        "citac nechal bez nej. Fronta orsr bezi na 15/m, takze plny prechod "
        "trva zhruba den a je bezpecne ho prerusit."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ico",
            action="append",
            dest="icos",
            help=(
                "ICO na precitanie historie osob (moze byt uvedene viac krat). "
                "Bezi rovno, nie cez Celery -- na overenie jednej firmy. "
                "Precita sa historia osob, nie cely profil: na obnovu profilu "
                "je 'sync_single_company_from_ruz'."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=2000,
            help="Kolko firiem naplanovat v batch rezime (default 2000).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Iba vypise, kolko firiem caka a ktore su prve v poradi. "
                "Nedispatchuje ziadnu ulohu a nic nezapisuje."
            ),
        )

    def handle(self, *args, **options):
        icos = list(options.get("icos") or [])
        if icos:
            self._sync_by_ico(icos)
            return

        limit = options["limit"]
        # The same queryset the rotation selects from, so a dry run counts
        # exactly what a real run would dispatch.
        pending = pending_person_history()
        total = pending.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Firmy bez precitanej historie osob: {total} z "
                f"{OrsrCompanyProfile.objects.filter(raw_payload__has_key='rpo_id').count()} "
                "RPO profilov"
            )
        )
        if total == 0:
            self.stdout.write("Nie je co robit -- vsetky profily historii maju.")
            return

        company_ids = list(pending.values_list("company_id", flat=True)[:limit])

        if options["dry_run"]:
            by_id = Company.objects.in_bulk(company_ids)
            for company_id in company_ids:
                company = by_id.get(company_id)
                if company:
                    self.stdout.write(f"  {company.ico}  {company.nazov_UJ}")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run: {len(company_ids)} firiem by sa naplanovalo, "
                    "nic sa nezapisalo."
                )
            )
            return

        for company_id in company_ids:
            read_person_history.delay(company_id)

        remaining = total - len(company_ids)
        self.stdout.write(
            self.style.SUCCESS(
                f"Naplanovanych {len(company_ids)} firiem. "
                f"Zostava {remaining} na dalsie kolo."
            )
        )
        # Said out loud because the queue is the only thing that writes the
        # marker: if the `orsr` worker is running the code from before this
        # change, every one of these tasks reads the company and writes the
        # profile without `osoby_historia` -- so the next run selects the same
        # companies, and the population never shrinks. The symptom is a count
        # that does not move, not an error.
        self.stdout.write(
            "Pozor: worker 'orsr' musi bezat s aktualnym kodom, inak sa "
            "historia nezapise a vyber sa nezuzi."
        )

    def _sync_by_ico(self, icos: list[str]):
        """Run one company now, in this process, and report what happened.

        Not dispatched, for the reason `fetch_ruz_financials --ico` is not: the
        operator naming a company wants the answer in front of them, and the
        interesting answer here is not "queued" but which relations changed.
        """
        companies = list(Company.objects.filter(ico__in=icos).order_by("ico"))
        missing = sorted(set(icos) - {company.ico for company in companies})
        if missing:
            raise CommandError(f"ICO sa v databaze nenaslo: {', '.join(missing)}")

        for company in companies:
            before = self._relation_state(company)
            self.stdout.write(f"{company.ico}  {company.nazov_UJ}")
            try:
                read_person_history(company.id)
            except Exception as exc:  # noqa: BLE001 -- reported, then re-raised
                raise CommandError(
                    f"Sync pre {company.ico} zlyhal: {type(exc).__name__}: {exc}"
                ) from exc

            profile = OrsrCompanyProfile.objects.filter(company=company).first()
            has_history = bool(
                profile and isinstance((profile.raw_payload or {}).get("structured", {}).get(PERSON_HISTORY_KEY), list)
            )
            after = self._relation_state(company)

            self.stdout.write(
                f"  historia osob: {'zapisana' if has_history else 'CHYBA (nie je v profile)'}"
            )
            self.stdout.write(
                f"  vazby: {before} -> {after}"
            )

    @staticmethod
    def _relation_state(company) -> str:
        from connections.models import PersonCompanyRelation

        relations = PersonCompanyRelation.objects.filter(company=company)
        ended = relations.filter(is_active=False).count()
        unknown = relations.filter(is_active__isnull=True).count()
        current = relations.filter(is_active=True).count()
        return f"spolu={relations.count()} aktualne={current} ukoncene={ended} nevieme={unknown}"
