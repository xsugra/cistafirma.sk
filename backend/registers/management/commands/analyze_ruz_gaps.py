from django.core.management.base import BaseCommand
from django.utils import timezone
from companies.models import Company
from registers.models import IndividualEntity, SyncGapAnalysis
import time


class Command(BaseCommand):
    help = 'Analyzuje databázu a nájde diery v RUZ ID sekvenciách.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-id',
            type=int,
            default=None,
            help='Minimálne RUZ ID na analýzu (default: min v DB)',
        )
        parser.add_argument(
            '--max-id',
            type=int,
            default=None,
            help='Maximálne RUZ ID na analýzu (default: max v DB)',
        )
        parser.add_argument(
            '--expected-max',
            type=int,
            default=None,
            help='Očakávané maximálne RUZ ID (ak chcete skontrolovať aj za aktuálny max)',
        )

    def handle(self, *args, **options):
        start_time = time.time()
        
        self.stdout.write(self.style.WARNING('=== ANALÝZA DIER V RUZ ID ==='))
        
        # Vytvoríme nový záznam analýzy
        analysis = SyncGapAnalysis.objects.create(status='analyzing')
        
        try:
            # Získame základné štatistiky z DB efektívne
            self.stdout.write('Načítavam existujúce RUZ ID z databázy...')

            from django.db.models import Min, Max, Count
            stats = Company.objects.filter(ruz_id__isnull=False).aggregate(
                min_id=Min('ruz_id'),
                max_id=Max('ruz_id'),
                total=Count('ruz_id'),
            )
            db_min, db_max, total_count = stats['min_id'], stats['max_id'], stats['total']
            
            if db_min is None:
                self.stdout.write(self.style.ERROR('Žiadne záznamy s RUZ ID v databáze!'))
                analysis.status = 'failed'
                analysis.last_error = 'Žiadne záznamy s RUZ ID'
                analysis.save()
                return
            
            # Nastavíme rozsah analýzy
            min_id = options['min_id'] or db_min
            max_id = options['expected_max'] or options['max_id'] or db_max
            
            self.stdout.write(f'DB obsahuje {total_count:,} firiem s RUZ ID')
            self.stdout.write(f'Rozsah v DB: {db_min:,} - {db_max:,}')
            self.stdout.write(f'Analyzujem rozsah: {min_id:,} - {max_id:,}')
            
            analysis.analyzed_min_id = min_id
            analysis.analyzed_max_id = max_id
            analysis.total_existing = total_count
            analysis.save()
            
            # Načítame všetky existujúce RUZ ID do setu.
            #
            # Z *oboch* tabuliek. `IndividualEntity` drží živnostníkov a iné
            # fyzické osoby, ktoré register vydáva pod vlastným RUZ ID; ani jedno
            # z tých ID nie je v `Company` (merané na dell 2026-09-18: 35 339
            # riadkov a **ani jeden** z nich v `Company`; počet je snímka a rastie
            # ako beží walk, nulový prienik je to trvalé). Kým sa počítali len
            # `Company`, celá tá populácia vyzerala ako diera -- analýza ju
            # hlásila ako chýbajúcu a oprava ju potom donekonečna sťahovala a
            # znova ukladala. `total_existing` nižšie zostáva počet `Company`
            # riadkov: je to informatívny údaj, nie vstup do hľadania dier.
            self.stdout.write('Načítavam všetky RUZ ID do pamäte...')
            existing_ids = set(
                Company.objects.filter(
                    ruz_id__isnull=False,
                    ruz_id__gte=min_id,
                    ruz_id__lte=max_id
                ).values_list('ruz_id', flat=True)
            ) | set(
                IndividualEntity.objects.filter(
                    ruz_id__isnull=False,
                    ruz_id__gte=min_id,
                    ruz_id__lte=max_id
                ).values_list('ruz_id', flat=True)
            )
            
            self.stdout.write(f'Načítaných {len(existing_ids):,} unikátnych RUZ ID')
            
            # Nájdeme diery
            self.stdout.write('Hľadám diery v sekvencii...')
            gaps = self._find_gap_ranges(existing_ids, min_id, max_id)
            
            total_missing = sum(end - start + 1 for start, end in gaps)
            
            # Uložíme výsledky
            analysis.gap_ranges = gaps
            analysis.total_gaps = len(gaps)
            analysis.total_missing = total_missing
            analysis.status = 'ready'
            analysis.analyzed_at = timezone.now()
            analysis.save()
            
            elapsed = time.time() - start_time
            
            # Výstup
            self.stdout.write(self.style.SUCCESS(f'\n=== ANALÝZA DOKONČENÁ za {elapsed:.1f}s ==='))
            self.stdout.write(f'Celkom existujúcich: {len(existing_ids):,}')
            self.stdout.write(f'Celkom chýbajúcich ID: {total_missing:,}')
            self.stdout.write(f'Počet dier (rozsahov): {len(gaps):,}')
            
            if gaps:
                self.stdout.write(f'\nNajväčšie diery (top 10):')
                sorted_gaps = sorted(gaps, key=lambda x: x[1] - x[0], reverse=True)
                for i, (start, end) in enumerate(sorted_gaps[:10]):
                    size = end - start + 1
                    self.stdout.write(f'  {i+1}. ID {start:,} - {end:,} ({size:,} ID)')
                
                self.stdout.write(
                    f'\n✅ Analýza ID #{analysis.id} je pripravená.'
                    f'\nSpustite opravu: python manage.py repair_ruz_gaps --analysis-id={analysis.id}'
                )
            else:
                self.stdout.write(self.style.SUCCESS('\n✅ Žiadne diery nenájdené! Databáza je kompletná.'))
            
        except Exception as e:
            analysis.status = 'failed'
            analysis.last_error = str(e)
            analysis.save()
            raise

    def _find_gap_ranges(self, existing_ids: set, min_id: int, max_id: int) -> list:
        """
        Nájde súvislé rozsahy chýbajúcich ID.
        Vracia zoznam [(start, end), ...] kde start a end sú vrátane.
        """
        if not existing_ids:
            return [[min_id, max_id]]
        
        gaps = []
        current_gap_start = None
        
        # Iterujeme cez celý rozsah
        for i in range(min_id, max_id + 1):
            if i not in existing_ids:
                # Začiatok novej diery
                if current_gap_start is None:
                    current_gap_start = i
            else:
                # Koniec diery (ak nejaká bola)
                if current_gap_start is not None:
                    gaps.append([current_gap_start, i - 1])
                    current_gap_start = None
        
        # Nezabudneme na poslednú dieru
        if current_gap_start is not None:
            gaps.append([current_gap_start, max_id])
        
        return gaps
