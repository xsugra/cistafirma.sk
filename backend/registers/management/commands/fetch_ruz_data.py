from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
import time

class Command(BaseCommand):
    help = 'Fetches and updates company data from the RUZ API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full-resync',
            action='store_true',
            help='Performs a full resync from 2000-01-01 instead of an incremental update.',
        )

    def handle(self, *args, **options):
        api = RuzApi()
        
        # Determine the start date for fetching
        # A real implementation would store the last successful sync date
        # For now, we'll hardcode it unless --full-resync is used.
        if options['full_resync']:
            zmenene_od = '2000-01-01'
            self.stdout.write(self.style.WARNING('Performing a full resync from 2000-01-01...'))
        else:
            # For incremental updates, get the last modified date from our DB
            # and fetch changes since then. Fallback to a recent date.
            last_company = Company.objects.order_by('-datumPoslednejUpravy').first()
            if last_company and last_company.datumPoslednejUpravy:
                zmenene_od = last_company.datumPoslednejUpravy.strftime('%Y-%m-%d')
                self.stdout.write(f"Performing incremental update from {zmenene_od}...")
            else:
                zmenene_od = '2020-01-01'
                self.stdout.write(f"No previous data found. Starting sync from {zmenene_od}...")


        pokracovat_za_id = None
        total_companies_processed = 0
        
        while True:
            self.stdout.write(f"Fetching company IDs changed since {zmenene_od}, starting after ID {pokracovat_za_id or 0}...")
            
            id_data = api.get_changed_company_ids(zmenene_od=zmenene_od, pokracovat_za_id=pokracovat_za_id)

            if not id_data or not id_data.get('id'):
                self.stdout.write(self.style.SUCCESS("No more company IDs to fetch."))
                break

            company_ids = id_data['id']
            self.stdout.write(f"Found {len(company_ids)} company IDs to process.")

            for company_id in company_ids:
                details = api.get_company_details(company_id)
                if details:
                    self.update_or_create_company(details)
                    total_companies_processed += 1
                
                # Be a good API citizen
                time.sleep(0.1) 

            if not id_data.get('existujeDalsieId'):
                self.stdout.write(self.style.SUCCESS("Reached the end of the list."))
                break
            
            # Prepare for the next page
            pokracovat_za_id = company_ids[-1]
            time.sleep(1) # Wait a bit before fetching the next page of IDs

        self.stdout.write(self.style.SUCCESS(f'Successfully finished RUZ sync. Processed {total_companies_processed} companies.'))

    def update_or_create_company(self, data: dict):
        """Maps API data and saves it to the Company model."""
        
        if 'ico' not in data:
            self.stderr.write(f"Skipping record with RUZ ID {data.get('id')} because it has no ICO.")
            return

        # Map API fields (camelCase) to model fields (snake_case)
        defaults = {
            'ruz_id': data.get('id'),
            'dic': data.get('dic'),
            'sid': data.get('sid'),
            'nazov_UJ': data.get('nazovUJ', ''), # Corrected field name
            'mesto': data.get('mesto'),
            'ulica': data.get('ulica'),
            'psc': data.get('psc'),
            'datum_zalozenia': parse_date(data.get('datumZalozenia', '')), # Corrected field name
            'datum_zrusenia': parse_date(data.get('datumZrusenia', '')), # Corrected field name
            'pravna_forma': data.get('pravnaForma'), # Corrected field name
            'sk_NACE': data.get('skNace'), # Corrected field name
            'velkost_organizacie': data.get('velkostOrganizacie'), # Corrected field name
            'druh_vlastnictva': data.get('druhVlastnictva'), # Corrected field name
            'kraj': data.get('kraj'),
            'okres': data.get('okres'),
            'sidlo': data.get('sidlo'),
            'konsolidovana': data.get('konsolidovana', False),
            'id_uctovnych_zavierok': data.get('idUctovnychZavierok', list()), # Corrected field name
            'id_vyrocnych_sprav': data.get('idVyrocnychSprav', list()), # Corrected field name
            'zdroj_dat': data.get('zdrojDat'), # Corrected field name
            'datum_poslednej_upravy': parse_date(data.get('datumPoslednejUpravy', '')), # Corrected field name
        }

        # Use ICO as the unique identifier for finding existing records
        company, created = Company.objects.update_or_create(
            ico=data['ico'],
            defaults=defaults
        )

        if created:
            self.stdout.write(f"Created new company: {company.nazov_UJ} (IČO: {company.ico})")
        else:
            self.stdout.write(f"Updated company: {company.nazov_UJ} (IČO: {company.ico})")
