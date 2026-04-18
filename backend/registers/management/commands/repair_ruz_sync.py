from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncProgress
import time
import concurrent.futures


class Command(BaseCommand):
    help = 'Opraví RUZ sync - stiahne všetky chýbajúce firmy ktoré neboli spracované.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-id',
            type=int,
            default=0,
            help='Začať od tohto RUZ ID (default: 0)',
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
            default=5,
            help='Počet paralelných workerov (default: 5)',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Menej výpisov - len súhrny',
        )

    def handle(self, *args, **options):
        self.api = RuzApi()
        start_id = options['start_id']
        batch_size = options['batch_size']
        num_workers = options['workers']
        self.quiet = options['quiet']
        
        # Vytvoríme alebo nájdeme repair progress
        progress, created = SyncProgress.objects.get_or_create(
            sync_type='repair',
            defaults={
                'status': 'idle',
                'last_processed_ruz_id': start_id,
            }
        )
        
        if not created and progress.status in ['paused', 'failed']:
            start_id = progress.last_processed_ruz_id
            self.stdout.write(self.style.SUCCESS(
                f'Pokračujem v oprave od RUZ ID {start_id}. '
                f'Už spracovaných: {progress.total_processed}'
            ))
        
        progress.status = 'running'
        progress.started_at = timezone.now()
        progress.save()
        
        self.stdout.write(self.style.WARNING(
            f'Spúšťam opravu RUZ sync od ID {start_id} s {num_workers} workermi...'
        ))
        
        pokracovat_za_id = start_id
        batch_downloaded = 0
        batch_skipped = 0
        batch_errors = 0
        
        try:
            while True:
                self.stdout.write(
                    f'[{progress.total_processed:,}] Načítavam ID od {pokracovat_za_id:,}...'
                )
                
                # Získame ďalšiu stránku ID z RUZ API
                id_data = self.api.get_changed_company_ids(
                    zmenene_od='2000-01-01',
                    pokracovat_za_id=pokracovat_za_id,
                    max_zaznamov=batch_size
                )
                
                if not id_data or not id_data.get('id'):
                    self.stdout.write(self.style.SUCCESS('Koniec zoznamu - všetky ID spracované.'))
                    break
                
                company_ids = id_data['id']
                
                # Zistíme ktoré ID chýbajú v DB
                existing_ids = set(
                    Company.objects.filter(ruz_id__in=company_ids)
                    .values_list('ruz_id', flat=True)
                )
                missing_ids = [id for id in company_ids if id not in existing_ids]
                
                self.stdout.write(
                    f'  Existujúcich: {len(existing_ids)}, Chýbajúcich: {len(missing_ids)}'
                )
                
                # Paralelne stiahneme chýbajúce firmy
                if missing_ids:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                        results = list(executor.map(self._fetch_and_save_company, missing_ids))
                    
                    for result in results:
                        if result == 'created':
                            batch_downloaded += 1
                        elif result == 'skipped':
                            batch_skipped += 1
                        elif result == 'error':
                            batch_errors += 1
                
                self.stdout.write(
                    f'  Existujúcich: {len(existing_ids)}, Chýbajúcich: {len(missing_ids)}'
                )
                
                total_missing += len(missing_ids)
                
                # Stiahneme len chýbajúce
                for company_id in missing_ids:
                    try:
                        details = api.get_company_details(company_id)
                        if details:
                            if 'ico' not in details:
                                self.stdout.write(
                                    f'  Preskakujem RUZ ID {company_id} - bez IČO'
                                )
                                total_skipped += 1
                                continue
                            
                            created_new, updated = self._update_or_create_company(details)
                            if created_new:
                                total_downloaded += 1
                                self.stdout.write(
                                    f'  ✓ Stiahnutá: {details.get("nazovUJ", "N/A")[:40]}'
                                )
                        else:
                            total_skipped += 1
                    except Exception as e:
                        self.stderr.write(f'  ✗ Chyba pre ID {company_id}: {e}')
                        total_errors += 1
                    
                    time.sleep(0.1)  # Rate limiting
                
                # Aktualizujeme progress
                pokracovat_za_id = company_ids[-1]
                progress.last_processed_ruz_id = pokracovat_za_id
                progress.total_processed += len(company_ids)
                progress.total_created += total_downloaded
                progress.total_skipped += total_skipped
                progress.total_errors += total_errors
                progress.save()
                
                # Reset pre ďalšiu iteráciu
                total_downloaded = 0
                total_skipped = 0
                total_errors = 0
                
                if not id_data.get('existujeDalsieId'):
                    self.stdout.write(self.style.SUCCESS('Koniec zoznamu.'))
                    break
                
                time.sleep(0.5)  # Pauza medzi stránkami
            
            # Dokončené
            progress.status = 'completed'
            progress.completed_at = timezone.now()
            progress.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'\n=== OPRAVA DOKONČENÁ ===\n'
                f'Skontrolovaných ID: {progress.total_processed}\n'
                f'Stiahnutých chýbajúcich: {progress.total_created}\n'
                f'Preskočených: {progress.total_skipped}\n'
                f'Chýb: {progress.total_errors}'
            ))
            
        except KeyboardInterrupt:
            progress.status = 'paused'
            progress.notes = f'Prerušené používateľom. Posledné ID: {pokracovat_za_id}'
            progress.save()
            self.stdout.write(self.style.WARNING(
                f'\nOprava pozastavená na RUZ ID {pokracovat_za_id}. '
                f'Pokračujte príkazom: python manage.py repair_ruz_sync'
            ))
            
        except Exception as e:
            progress.status = 'failed'
            progress.last_error = str(e)
            progress.save()
            self.stderr.write(self.style.ERROR(f'Chyba: {e}'))
            raise

    def _update_or_create_company(self, data: dict):
        """Uloží firmu do DB."""
        defaults = {
            'ruz_id': data.get('id'),
            'dic': data.get('dic'),
            'sid': data.get('sid'),
            'nazov_UJ': data.get('nazovUJ', ''),
            'mesto': data.get('mesto'),
            'ulica': data.get('ulica'),
            'psc': data.get('psc'),
            'datum_zalozenia': parse_date(data.get('datumZalozenia', '')),
            'datum_zrusenia': parse_date(data.get('datumZrusenia', '')),
            'pravna_forma': data.get('pravnaForma'),
            'sk_NACE': data.get('skNace'),
            'velkost_organizacie': data.get('velkostOrganizacie'),
            'druh_vlastnictva': data.get('druhVlastnictva'),
            'kraj': data.get('kraj'),
            'okres': data.get('okres'),
            'sidlo': data.get('sidlo'),
            'konsolidovana': data.get('konsolidovana', False),
            'id_uctovnych_zavierok': data.get('idUctovnychZavierok', []),
            'id_vyrocnych_sprav': data.get('idVyrocnychSprav', []),
            'zdroj_dat': data.get('zdrojDat'),
            'datum_poslednej_upravy': parse_date(data.get('datumPoslednejUpravy', '')),
        }
        
        company, created = Company.objects.update_or_create(
            ico=data['ico'],
            defaults=defaults
        )
        return created, not created
