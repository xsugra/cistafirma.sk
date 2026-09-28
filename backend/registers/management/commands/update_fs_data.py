"""
Management command pre aktualizáciu dát z Finančnej správy.
Sťahuje a spracováva datasety: daňoví dlžníci, platitelia DPH, bankové účty, atď.
"""
import logging
import re

from django.core.management.base import BaseCommand
from django.utils import timezone
from collections import defaultdict

from registers.scrapers.scraper_links_dph import FS_DATASET_URLS
from registers.scrapers.financna_sprava_scraper import download_and_parse_fs_data
from registers.services import fs_company_matcher
from registers.services.fs_company_matcher import CompanyNameMatcher
from registers.services.fs_data_handlers import FSDataHandlers
from companies.models import Company


logger = logging.getLogger(__name__)


# Mapovanie datasetov na polia pre bulk_update
UPDATE_FIELDS_MAP = {
    'tax_debtors': ['tax_debt'],
    'bank_accounts': ['bank_accounts'],
    'vat_payers': ['vat_payer', 'ic_dph', 'datum_reg_dph'],
    'vat_deleted': ['vat_payer', 'vat_deleted_date', 'vat_deleted_reason'],
    'tax_reliability': ['tax_reliability'],
}


# Datasety, pri ktorých sa riadok bez IČO smie dohľadať názvom a PSČ.
#
# `ds_dsdd` (daňoví dlžníci) je jediný dataset, ktorý IČO nemá vôbec -- a ani
# nemôže mať, pozri `fs_company_matcher`. Ostatné štyri nesú IČO v každom
# riadku; keď tam raz chýba, znamená to, že ho nemá zdroj, a hádať sa nechce:
# riadok sa zahodí.
NAME_MATCHED_DATASETS = {'tax_debtors'}


def normalise_ico(value) -> str:
    """IČO z riadku, alebo `''`.

    Parser ukladá `child.text`, a ten je pri prázdnom elemente (`<ICO/>`)
    `None`. Pôvodné `item.get('ICO', '').isdigit()` preto na prázdnom `<ICO/>`
    spadlo na `AttributeError` -- `dict.get` vráti default len vtedy, keď kľúč
    **chýba**, nie keď je jeho hodnota `None` -- a zhodilo **celý denný
    import** skôr, než stihol vypísať čokoľvek. Dnes je to latentné (0 prázdnych
    hodnôt v štyroch datasetoch s IČO), ale presne takáto chyba sa navonok
    prejaví ako „dnes sa FS nesynchronizovalo" bez jedinej stopy v logu.

    Berú sa len číslice, takže IČO s medzerou („1234 5678") sa dohľadá namiesto
    tichého zahodenia.
    """
    return re.sub(r"\D", "", value or "")


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

        total_stats = {}

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

    def _empty_stats(self) -> dict:
        """Štatistiky datasetu. Každý kľúč má **jeden** význam.

        Predtým tu boli `not_found` a `unverified`, ktoré sa zvyšovali vždy
        spolu -- `unverified` teda nesie nula informácie. Nahradili ich tri
        rozlíšené dôvody, prečo sa riadok nepriradil, plus samostatný počet
        riadkov dohľadaných menom (nie IČO).
        """
        return {
            'updated': 0,
            'skipped': 0,
            'name_matched': 0,     # priradené názvom a PSČ, nie IČO
            'ambiguous': 0,        # viac firiem s tým istým názvom aj PSČ -> odmietnuté
            'unmatched': 0,        # názov a PSČ nesedia na žiadnu firmu
            'no_ico': 0,           # riadok nemá IČO a dataset sa menom nedohľadáva
            'not_in_register': 0,  # IČO poznáme, firmu s ním nemáme
            'errors': 0,
        }

    def _process_dataset(self, key: str, url: str, handlers: FSDataHandlers, dry_run: bool) -> dict:
        """Spracuje jeden dataset z FS."""
        stats = self._empty_stats()

        items = download_and_parse_fs_data(url)
        if not items:
            self.stderr.write(self.style.ERROR(f"Nepodarilo sa získať dáta pre {key}"))
            logger.error("FS dataset %s: nepodarilo sa získať dáta (%s)", key, url)
            return stats

        self.stdout.write(f"Nájdených {len(items)} položiek.")

        resolved = self._resolve_items(items, key, stats)

        # Dataset, z ktorého sa nepodarilo priradiť **ani jeden** riadok, je
        # porucha, nie tichý deň. Presne takto vyzeral `tax_debtors` roky:
        # 90 902 položiek, 0 zhôd, a v logu to bolo na nerozoznanie od
        # normálneho dňa.
        if not resolved:
            message = (
                f"POZOR: {key} -- z {len(items)} položiek sa nepodarilo priradiť "
                f"ani jednu firmu (bez IČO: {stats['no_ico']}, "
                f"bez zhody menom: {stats['unmatched']}, "
                f"viac kandidátov: {stats['ambiguous']})."
            )
            self.stderr.write(self.style.ERROR(message))
            logger.error("FS dataset %s: %s", key, message)

        companies_by_ico = self._load_companies_by_ico([ico for _, ico in resolved])
        self.stdout.write(f"Načítaných {len(companies_by_ico)} firiem")

        companies_to_save = {}
        total = len(resolved) or 1
        for idx, (item, ico) in enumerate(resolved):
            if idx > 0 and idx % (total // 10 or 1) == 0:
                self.stdout.write(f"  Progress: {(idx * 100) // total}%")

            company = companies_by_ico.get(ico)
            if not company:
                stats['not_in_register'] += 1
                continue

            try:
                if handlers.update_company(company, item, key):
                    company.fs_update_date = timezone.now()
                    companies_to_save[company.ico] = company
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Chyba: {e}"))
                logger.exception("FS dataset %s: chyba pri firme %s", key, ico)
                stats['errors'] += 1

        # Uloženie
        if companies_to_save and not dry_run:
            fields = ['fs_update_date'] + UPDATE_FIELDS_MAP.get(key, [])
            Company.objects.bulk_update(list(companies_to_save.values()), fields, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"Uložených {len(companies_to_save)} firiem"))

        return stats

    def _resolve_items(self, items: list, key: str, stats: dict) -> list:
        """Priradí každému riadku IČO -- z dát, alebo bezpečným párovaním menom.

        Vracia len riadky, ktoré sa dajú priradiť. Zvyšok sa spočíta do
        `stats`, aby bolo vidieť, koľko ich bolo a prečo.
        """
        matcher = None
        resolved = []

        for item in items:
            ico = normalise_ico(item.get('ICO'))
            if ico:
                resolved.append((item, ico))
                continue

            if key not in NAME_MATCHED_DATASETS:
                stats['no_ico'] += 1
                continue

            if matcher is None:
                # Index sa stavia len raz, a len keď je naozaj potrebný: štyri
                # z piatich datasetov nesú IČO v každom riadku, takže sa pre ne
                # nestavia vôbec a nič to nestojí.
                matcher = CompanyNameMatcher.build()
                self.stdout.write(
                    f"  Riadky bez IČO -- index firiem podľa názvu a PSČ: "
                    f"{len(matcher)} kľúčov"
                )

            ico, stav = matcher.resolve(item)
            if stav == fs_company_matcher.UNIQUE:
                stats['name_matched'] += 1
                resolved.append((item, ico))
            elif stav == fs_company_matcher.AMBIGUOUS:
                # Nikdy sa nehádame: radšej riadok zahodiť, než pripísať dlh
                # nesprávnej firme.
                stats['ambiguous'] += 1
            else:
                stats['unmatched'] += 1

        return resolved

    def _load_companies_by_ico(self, ico_list: list) -> dict:
        """Batch načítanie firiem podľa IČO."""
        companies_by_ico = {}

        # Duplicity sú bežné (ten istý IČO vo viacerých riadkoch) a zbytočne
        # nafukujú `IN (...)`.
        unique = list(dict.fromkeys(ico for ico in ico_list if ico))

        for i in range(0, len(unique), 500):  # SQLite limit
            batch = unique[i:i + 500]
            for company in Company.objects.filter(ico__in=batch):
                companies_by_ico[company.ico] = company

        return companies_by_ico

    def _print_stats(self, key: str, stats: dict):
        """Vypíše štatistiky pre dataset."""
        self.stdout.write(
            f"  {key}: {self.style.SUCCESS(f'{stats['updated']} updated')}, "
            f"{stats['skipped']} skipped, "
            f"{stats['name_matched']} podľa názvu, "
            f"{stats['not_in_register']} mimo registra, "
            f"{stats['unmatched']} bez zhody, "
            f"{stats['ambiguous']} nejednoznačných, "
            f"{stats['no_ico']} bez IČO, "
            f"{self.style.ERROR(f'{stats['errors']} errors') if stats['errors'] else '0 errors'}"
        )
