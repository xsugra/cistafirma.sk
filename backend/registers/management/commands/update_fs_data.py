from django.core.management.base import BaseCommand
from django.utils import timezone
from thefuzz import fuzz
from registers.scrapers.scraper_links_dph import FS_DATASET_URLS
from registers.scrapers.financna_sprava_scraper import download_and_parse_fs_data
from companies.models import Company
from registers.utils import clean_company_name, parse_money

class Command(BaseCommand):
    help = 'Downloads and updates company data from Financna Sprava.'

    def handle(self, *args, **options):
        for key, url in FS_DATASET_URLS.items():
            self.stdout.write(f"Processing {key} from {url}")
            items = download_and_parse_fs_data(url)
            
            if not items:
                self.stderr.write(self.style.ERROR(f"Failed to get data for {key}"))
                continue

            self.stdout.write(f"Found {len(items)} items for {key}.")
            
            for item in items:
                company = self.find_company(item)

                if company:
                    self.update_company_data(company, item, key)
                else:
                    cleaned_name = clean_company_name(item.get('NAZOV_SUBJEKTU', ''))
                    # self.stdout.write(f"Could not find a match for {cleaned_name}")

        self.stdout.write(self.style.SUCCESS('Successfully updated data from Financna Sprava.'))

    def find_company(self, item: dict) -> Company | None:
        """
        Finds a company in the database based on the item data from the XML.
        Tries to match by ICO, then by name and address.
        """
        # Try to find by ICO if present
        ico = item.get('ICO')
        if ico and ico.isdigit():
            company = Company.objects.filter(ico=ico).first()
            if company:
                return company

        # If no ICO, try to match by name and address
        cleaned_name = clean_company_name(item.get('NAZOV_SUBJEKTU', ''))
        if not cleaned_name:
            return None
            
        psc = item.get('PSC', '').replace(' ', '')
        obec = item.get('OBEC', '')

        candidate_companies = Company.objects.all()
        if psc:
            candidate_companies = candidate_companies.filter(psc=psc)
        if obec:
            candidate_companies = candidate_companies.filter(mesto__icontains=obec)

        # If we have candidates, perform fuzzy matching on the name
        if candidate_companies.exists():
            best_match = None
            highest_ratio = 0
            
            # This can be slow, for a large number of companies we would need a better approach
            for company in candidate_companies:
                db_cleaned_name = clean_company_name(company.nazovUJ)
                ratio = fuzz.ratio(cleaned_name, db_cleaned_name)
                
                if ratio > highest_ratio:
                    highest_ratio = ratio
                    best_match = company
            
            if highest_ratio > 90: # Confidence threshold
                return best_match

        return None

    def update_company_data(self, company: Company, item: dict, source_key: str):
        """
        Updates the company model with data from the item.
        This is a placeholder and should be adapted based on the data from each source.
        """
        # Specific handler for tax debtors
        if source_key == 'tax_debtors':
            amount_str = item.get('CIASTKA')
            if amount_str:
                try:
                    debt_amount = parse_money(amount_str)
                    company.tax_debt = debt_amount
                    self.stdout.write(self.style.SUCCESS(f"Updated tax debt for {company.nazovUJ} to {debt_amount}"))
                except (ValueError, TypeError):
                    self.stderr.write(self.style.ERROR(f"Could not parse money from '{amount_str}' for {company.nazovUJ}"))

        # Add handlers for other source_keys here
        # e.g., if source_key == 'vat_payers': ...
        
        company.fs_update_date = timezone.now()
        company.save()

