"""
Management command pre aktualizáciu dát z Finančnej správy.
Sťahuje a spracováva datasety: daňoví dlžníci, platitelia DPH, bankové účty, atď.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from collections import defaultdict

from registers.scrapers.scraper_links_dph import FS_DATASET_URLS
from registers.scrapers.financna_sprava_scraper import download_and_parse_fs_data
from registers.services.fs_data_handlers import FSDataHandlers
from registers.services.fs_company_matcher import find_company_by_fuzzy_match
from companies.models import Company


# Mapovanie datasetov na polia pre bulk_update
UPDATE_FIELDS_MAP = {
    'tax_debtors': ['tax_debt'],
    'bank_accounts': ['bank_accounts'],
    'vat_payers': ['vat_payer', 'ic_dph', 'datum_reg_dph'],
    'vat_deleted': ['vat_payer', 'vat_deleted_date', 'vat_deleted_reason'],
    'tax_reliability': ['tax_reliability'],
}


class Command(BaseCommand):
    help = 'Downloads and updates company data from Financna Sprava.'

    SUPPORTED_DATASETS = set(UPDATE_FIELDS_MAP.keys())
    verbose: bool = False

    def add_arguments(self, parser):
        parser.add_argument('--datasets', nargs='+', type=str,
                          help='Datasety na spracovanie (napr. --datasets tax_debtors bank_accounts)')
        parser.add_argument('--dry-run', action='store_true',
                          help='Spustí bez ukladania zmien do databázy')
        parser.add_argument('--verbose-output', action='store_true', dest='verbose_output',
                          help='Podrobný výstup pre každú aktualizáciu')

    def handle(self, *args, **options):
        datasets_to_process = options.get('datasets') or self.SUPPORTED_DATASETS
        dry_run = options.get('dry_run', False)
        self.verbose = options.get('verbose_output', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - žiadne zmeny sa neuložia'))

        # Inicializácia handlerov
        handlers = FSDataHandlers(
            stdout_write=self.stdout.write,
            stderr_write=self.stderr.write,
            style_success=self.style.SUCCESS,
            style_error=self.style.ERROR,
            style_warning=self.style.WARNING,
            verbose=self.verbose
        )

        total_stats = defaultdict(lambda: {'updated': 0, 'skipped': 0, 'not_found': 0, 'errors': 0})

        for key, url in FS_DATASET_URLS.items():
            if key not in datasets_to_process or key not in self.SUPPORTED_DATASETS:
                continue

            self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}\nProcessing {key}\n{'='*60}"))

            stats = self._process_dataset(key, url, handlers, dry_run)
            total_stats[key] = stats
            self._print_stats(key, stats)

        # Súhrn
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}\nSÚHRN\n{'='*60}"))
        for key, stats in total_stats.items():
            self._print_stats(key, stats)

    def _process_dataset(self, key: str, url: str, handlers: FSDataHandlers, dry_run: bool) -> dict:
        """Spracuje jeden dataset z FS."""
        stats = {'updated': 0, 'skipped': 0, 'not_found': 0, 'errors': 0}

        items = download_and_parse_fs_data(url)
        if not items:
            self.stderr.write(self.style.ERROR(f"Nepodarilo sa získať dáta pre {key}"))
            return stats

        self.stdout.write(f"Nájdených {len(items)} položiek.")

        # Batch load firiem podľa IČO
        companies_by_ico = self._load_companies_by_ico(items)
        self.stdout.write(f"Načítaných {len(companies_by_ico)} firiem podľa IČO")

        companies_to_save = {}
        for idx, item in enumerate(items):
            if idx > 0 and idx % (len(items) // 10 or 1) == 0:
                self.stdout.write(f"  Progress: {(idx * 100) // len(items)}%")

            company = companies_by_ico.get(item.get('ICO'))
            if not company:
                company = find_company_by_fuzzy_match(item)

            if company:
                try:
                    if handlers.update_company(company, item, key):
                        company.fs_update_date = timezone.now()
                        companies_to_save[company.ico] = company
                        stats['updated'] += 1
                    else:
                        stats['skipped'] += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Chyba: {e}"))
                    stats['errors'] += 1
            else:
                stats['not_found'] += 1

        # Uloženie
        if companies_to_save and not dry_run:
            fields = ['fs_update_date'] + UPDATE_FIELDS_MAP.get(key, [])
            Company.objects.bulk_update(list(companies_to_save.values()), fields, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"Uložených {len(companies_to_save)} firiem"))

        return stats

    def _load_companies_by_ico(self, items: list) -> dict:
        """Batch načítanie firiem podľa IČO."""
        ico_list = [item.get('ICO') for item in items if item.get('ICO', '').isdigit()]
        companies_by_ico = {}

        for i in range(0, len(ico_list), 500):  # SQLite limit
            batch = ico_list[i:i + 500]
            for company in Company.objects.filter(ico__in=batch):
                companies_by_ico[company.ico] = company

        return companies_by_ico

    def _print_stats(self, key: str, stats: dict):
        """Vypíše štatistiky pre dataset."""
        self.stdout.write(
            f"  {key}: {self.style.SUCCESS(f'{stats['updated']} updated')}, "
            f"{stats['skipped']} skipped, {stats['not_found']} not found, "
            f"{self.style.ERROR(f'{stats['errors']} errors') if stats['errors'] else '0 errors'}"
        )
