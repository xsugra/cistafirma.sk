from django.core.management.base import BaseCommand

from companies.models import Company
from registers.integrations.rpo_client import RpoClient
from registers.services.rpo_sync import RpoSyncService


class Command(BaseCommand):
    help = "Test RPO API sync for a single company by ICO."

    def add_arguments(self, parser):
        parser.add_argument("ico", type=str, help="IČO firmy na test")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Len zobrazí dáta z RPO bez uloženia do DB",
        )

    def handle(self, *args, **options):
        ico = options["ico"].strip().zfill(8)
        dry_run = options["dry_run"]

        client = RpoClient()

        self.stdout.write(f"Hľadám v RPO: ICO {ico}...")
        entity_id = client.search_by_ico(ico)
        if entity_id is None:
            self.stdout.write(self.style.ERROR(f"ICO {ico} nenájdené v RPO."))
            return

        self.stdout.write(f"Nájdené RPO ID: {entity_id}")
        entity = client.get_entity(entity_id)

        self.stdout.write(self.style.SUCCESS(f"\n=== {entity.current_name} ==="))
        self.stdout.write(f"IČO: {entity.ico}")
        self.stdout.write(f"Právna forma: {entity.legal_form} ({entity.legal_form_code})")
        self.stdout.write(f"Deň zápisu: {entity.establishment}")
        if entity.current_address:
            self.stdout.write(f"Sídlo: {entity.current_address.format()}")

        if entity.source_register:
            sr = entity.source_register
            self.stdout.write(f"Register: {sr.register_name}")
            self.stdout.write(f"Registračný súd: {sr.registration_office}")
            self.stdout.write(f"Číslo: {sr.registration_number}")

        current_statutory = [p for p in entity.statutory_bodies if p.is_current]
        if current_statutory:
            self.stdout.write(f"\nŠtatutárny orgán ({len(current_statutory)}):")
            for p in current_statutory:
                addr = p.address.format() if p.address else ""
                self.stdout.write(f"  - {p.display_name} ({p.stakeholder_type}) od {p.valid_from}")
                if addr:
                    self.stdout.write(f"    Adresa: {addr}")

        current_stakeholders = [p for p in entity.stakeholders if p.is_current]
        if current_stakeholders:
            self.stdout.write(f"\nSpoločníci ({len(current_stakeholders)}):")
            for p in current_stakeholders:
                name = p.display_name or p.full_name
                self.stdout.write(f"  - {name}")

        current_activities = [a for a in entity.activities if a.is_current]
        if current_activities:
            self.stdout.write(f"\nPredmety podnikania ({len(current_activities)}):")
            for a in current_activities[:5]:
                self.stdout.write(f"  - {a.description}")
            if len(current_activities) > 5:
                self.stdout.write(f"  ... a ďalších {len(current_activities) - 5}")

        current_equities = [e for e in entity.equities if e.is_current]
        for e in current_equities:
            if e.value is not None:
                self.stdout.write(f"\nZákladné imanie: {e.value:,.2f} {e.currency}")
            if e.value_paid is not None:
                self.stdout.write(f"Splatené: {e.value_paid:,.2f} {e.currency}")

        current_auth = next((a for a in entity.authorizations if a.is_current), None)
        if current_auth:
            self.stdout.write(f"\nKonanie: {current_auth.value[:200]}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] Dáta neboli uložené do DB."))
            return

        try:
            company = Company.objects.get(ico=ico)
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"\nFirma s ICO {ico} nie je v DB. Použite --dry-run."))
            return

        service = RpoSyncService(client=client)
        profile = service.sync_company(company)
        self.stdout.write(self.style.SUCCESS(f"\nProfil uložený: {profile}"))
