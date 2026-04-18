from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import connection
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncProgress
import time
import concurrent.futures
import threading


class Command(BaseCommand):
    help = 'Opraví RUZ sync - stiahne všetky chýbajúce firmy (paralelne).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-id',
            type=int,
            default=None,
            help='Začať od tohto RUZ ID (default: pokračovať kde sa skončilo)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Počet ID na jednu stránku (default: 1000)',
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=10,
            help='Počet paralelných workerov (default: 10)',
        )

    def handle(self, *args, **options):
        self.api = RuzApi()
        batch_size = options['batch_size']
        num_workers = options['workers']
        self.lock = threading.Lock()
        self.batch_stats = {'created': 0, 'skipped': 0, 'errors': 0}
        
        # Nájdeme alebo vytvoríme repair progress
        progress, created = SyncProgress.objects.get_or_create(
            sync_type='repair',
            defaults={
                'status': 'idle',
                'last_processed_ruz_id': 0,
            }
        )
        
        # Určíme štartovacie ID
        if options['start_id'] is not None:
            start_id = options['start_id']
        elif progress.status in ['paused', 'failed'] and progress.last_processed_ruz_id:
            start_id = progress.last_processed_ruz_id
            self.stdout.write(self.style.SUCCESS(
                f'Pokračujem od RUZ ID {start_id:,}. Doteraz: {progress.total_created:,} nových firiem'
            ))
        else:
            start_id = 0
        
        progress.status = 'running'
        progress.started_at = timezone.now()
        progress.save()
        
        self.stdout.write(self.style.WARNING(
            f'Repair sync: štart od ID {start_id:,}, {num_workers} workerov, batch {batch_size}'
        ))
        
        pokracovat_za_id = start_id
        
        try:
            while True:
                # Získame ďalšiu stránku ID z RUZ API
                id_data = self.api.get_changed_company_ids(
                    zmenene_od='2000-01-01',
                    pokracovat_za_id=pokracovat_za_id,
                    max_zaznamov=batch_size
                )
                
                if not id_data or not id_data.get('id'):
                    self.stdout.write(self.style.SUCCESS('Koniec zoznamu.'))
                    break
                
                company_ids = id_data['id']
                
                # Zistíme ktoré ID chýbajú v DB (rýchly SQL query)
                existing_ids = set(
                    Company.objects.filter(ruz_id__in=company_ids)
                    .values_list('ruz_id', flat=True)
                )
                missing_ids = [cid for cid in company_ids if cid not in existing_ids]
                
                # Reset batch stats
                self.batch_stats = {'created': 0, 'skipped': 0, 'errors': 0}
                
                # Paralelne stiahneme chýbajúce
                if missing_ids:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                        list(executor.map(self._fetch_and_save, missing_ids))
                
                # Aktualizujeme progress
                pokracovat_za_id = company_ids[-1]
                progress.last_processed_ruz_id = pokracovat_za_id
                progress.total_processed += len(company_ids)
                progress.total_created += self.batch_stats['created']
                progress.total_skipped += self.batch_stats['skipped']
                progress.total_errors += self.batch_stats['errors']
                progress.save()
                
                # Výpis progresu
                self.stdout.write(
                    f'[{progress.total_processed:,}] ID {pokracovat_za_id:,} | '
                    f'exist: {len(existing_ids)} | miss: {len(missing_ids)} | '
                    f'new: +{self.batch_stats["created"]} | total: {progress.total_created:,}'
                )
                
                if not id_data.get('existujeDalsieId'):
                    self.stdout.write(self.style.SUCCESS('Dosiahnutý koniec.'))
                    break
                
                time.sleep(0.2)  # Krátka pauza medzi stránkami
            
            # Hotovo
            progress.status = 'completed'
            progress.completed_at = timezone.now()
            progress.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'\n=== REPAIR DOKONČENÝ ===\n'
                f'Skontrolovaných: {progress.total_processed:,}\n'
                f'Nových firiem: {progress.total_created:,}\n'
                f'Preskočených: {progress.total_skipped:,}\n'
                f'Chýb: {progress.total_errors:,}'
            ))
            
        except KeyboardInterrupt:
            progress.status = 'paused'
            progress.notes = f'Prerušené. Posledné ID: {pokracovat_za_id}'
            progress.save()
            self.stdout.write(self.style.WARNING(
                f'\nPozastavené na ID {pokracovat_za_id:,}. '
                f'Pokračujte: python manage.py repair_ruz_sync_v2'
            ))
            
        except Exception as e:
            progress.status = 'failed'
            progress.last_error = str(e)
            progress.save()
            raise

    def _fetch_and_save(self, ruz_id):
        """Stiahne a uloží jednu firmu (thread-safe)."""
        try:
            # Každé vlákno potrebuje vlastné DB connection
            details = self.api.get_company_details(ruz_id)
            
            if not details:
                with self.lock:
                    self.batch_stats['skipped'] += 1
                return
            
            if 'ico' not in details:
                with self.lock:
                    self.batch_stats['skipped'] += 1
                return
            
            # Uložíme do DB
            defaults = {
                'ruz_id': details.get('id'),
                'dic': details.get('dic'),
                'sid': details.get('sid'),
                'nazov_UJ': details.get('nazovUJ', ''),
                'mesto': details.get('mesto'),
                'ulica': details.get('ulica'),
                'psc': details.get('psc'),
                'datum_zalozenia': parse_date(details.get('datumZalozenia', '')),
                'datum_zrusenia': parse_date(details.get('datumZrusenia', '')),
                'pravna_forma': details.get('pravnaForma'),
                'sk_NACE': details.get('skNace'),
                'velkost_organizacie': details.get('velkostOrganizacie'),
                'druh_vlastnictva': details.get('druhVlastnictva'),
                'kraj': details.get('kraj'),
                'okres': details.get('okres'),
                'sidlo': details.get('sidlo'),
                'konsolidovana': details.get('konsolidovana', False),
                'id_uctovnych_zavierok': details.get('idUctovnychZavierok', []),
                'id_vyrocnych_sprav': details.get('idVyrocnychSprav', []),
                'zdroj_dat': details.get('zdrojDat'),
                'datum_poslednej_upravy': parse_date(details.get('datumPoslednejUpravy', '')),
            }
            
            company, created = Company.objects.update_or_create(
                ico=details['ico'],
                defaults=defaults
            )
            
            with self.lock:
                if created:
                    self.batch_stats['created'] += 1
                else:
                    self.batch_stats['skipped'] += 1
                    
        except Exception as e:
            with self.lock:
                self.batch_stats['errors'] += 1
