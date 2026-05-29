import logging

from django.core.management.base import BaseCommand

from connections.services import PersonExtractionService
from registers.models import OrsrCompanyProfile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate Person and PersonCompanyRelation from existing OrsrCompanyProfile data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ico",
            type=str,
            help="Process only a specific company by ICO",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count without creating records",
        )

    def handle(self, *args, **options):
        service = PersonExtractionService()
        ico = options.get("ico")
        dry_run = options.get("dry_run", False)

        profiles = OrsrCompanyProfile.objects.select_related("company").all()
        if ico:
            profiles = profiles.filter(ico=ico)

        total_profiles = profiles.count()
        self.stdout.write(f"Processing {total_profiles} ORSR profiles...")

        total_persons = 0
        total_relations = 0

        for i, profile in enumerate(profiles.iterator(), 1):
            if dry_run:
                structured = service._get_structured(profile)
                count = sum(
                    len(structured.get(key, []))
                    for key in ("statutarny_organ", "spolocnici", "prokura",
                                "predstavenstvo", "kontrolna_komisia", "dozorna_rada", "akcionari")
                )
                total_relations += count
            else:
                persons_created, relations_created = service.extract_from_profile(profile)
                total_persons += persons_created
                total_relations += relations_created

            if i % 100 == 0:
                self.stdout.write(f"  Processed {i}/{total_profiles}...")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would process ~{total_relations} person entries from {total_profiles} profiles"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. Created {total_persons} persons, {total_relations} relations "
                f"from {total_profiles} profiles."
            ))
