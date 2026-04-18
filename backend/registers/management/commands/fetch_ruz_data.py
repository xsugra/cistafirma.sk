from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncProgress
import time


class Command(BaseCommand):
    help = 'Fetches and updates company data from the RUZ API with progress tracking.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full-resync',
            action='store_true',
            help='Performs a full resync from 2000-01-01 instead of an incremental update.',
        )
        parser.add_argument(
            '--resume',
            action='store_true',
            help='Resume a previously paused or failed sync from where it stopped.',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset sync progress and start fresh.',
        )

    def handle(self, *args, **options):
        api = RuzApi()
        
        # Pri resume najprv nájdeme existujúci pozastavený sync
        if options['resume']:
            # Najprv hľadáme podľa špecifikovaného typu, potom akýkoľvek
            if options['full_resync']:
                progress = SyncProgress.objects.filter(
                    sync_type='full',
                    status__in=['paused', 'failed', 'running']
                ).first()
            else:
                progress = SyncProgress.objects.filter(
                    status__in=['paused', 'failed', 'running']
                ).order_by('-last_activity').first()
            
            if progress:
                sync_type = progress.sync_type
                self.stdout.write(self.style.SUCCESS(
                    f'Nájdený {progress.get_sync_type_display()} sync na pokračovanie. '
                    f'RUZ ID: {progress.last_processed_ruz_id}, Spracovaných: {progress.total_processed}'
                ))
            else:
                self.stdout.write(self.style.ERROR('Nenájdený žiadny sync na pokračovanie.'))
                return
        else:
            # Určíme typ synchronizácie
            sync_type = 'full' if options['full_resync'] else 'incremental'
            progress = None
        
        # Získame alebo vytvoríme záznam o synchronizácii
        if options['reset']:
            # Vymažeme všetky predchádzajúce záznamy daného typu
            SyncProgress.objects.filter(sync_type=sync_type).delete()
            self.stdout.write(self.style.WARNING('Vymazaný predchádzajúci progress. Začínam odznova...'))
            progress = None
        
        if not progress:
            progress, created = SyncProgress.get_or_create_active(sync_type)
        else:
            created = False
        
        # Ak pokračujeme v existujúcej synchronizácii
        if options['resume'] and not created:
            if progress.status in ['paused', 'failed']:
                self.stdout.write(self.style.SUCCESS(
                    f'Pokračujem v synchronizácii od RUZ ID {progress.last_processed_ruz_id}. '
                    f'Už spracovaných: {progress.total_processed}'
                ))
                pokracovat_za_id = progress.last_processed_ruz_id
            elif progress.status == 'running':
                self.stdout.write(self.style.WARNING(
                    f'Synchronizácia už beží. Pokračujem od RUZ ID {progress.last_processed_ruz_id}.'
                ))
                pokracovat_za_id = progress.last_processed_ruz_id
            else:
                pokracovat_za_id = progress.last_processed_ruz_id
        else:
            pokracovat_za_id = progress.last_processed_ruz_id if not created else None
        
        # Determine the start date for fetching
        if sync_type == 'full':
            zmenene_od = '2000-01-01'
            self.stdout.write(self.style.WARNING('Performing a full resync from 2000-01-01...'))
        else:
            if progress.zmenene_od:
                zmenene_od = progress.zmenene_od.strftime('%Y-%m-%d')
            else:
                last_company = Company.objects.order_by('-datum_poslednej_upravy').first()
                if last_company and last_company.datum_poslednej_upravy:
                    zmenene_od = last_company.datum_poslednej_upravy.strftime('%Y-%m-%d')
                    self.stdout.write(f"Performing incremental update from {zmenene_od}...")
                else:
                    zmenene_od = '2020-01-01'
                    self.stdout.write(f"No previous data found. Starting sync from {zmenene_od}...")
        
        # Spustíme synchronizáciu
        progress.start(zmenene_od=parse_date(zmenene_od))
        
        self.stdout.write(self.style.SUCCESS(
            f'Synchronizácia spustená. Typ: {sync_type}, Od: {zmenene_od}, '
            f'Pokračujem za ID: {pokracovat_za_id or 0}'
        ))

        try:
            while True:
                self.stdout.write(
                    f"[{progress.total_processed}] Fetching company IDs changed since {zmenene_od}, "
                    f"starting after ID {pokracovat_za_id or 0}..."
                )
                
                id_data = api.get_changed_company_ids(zmenene_od=zmenene_od, pokracovat_za_id=pokracovat_za_id)

                if not id_data or not id_data.get('id'):
                    self.stdout.write(self.style.SUCCESS("No more company IDs to fetch."))
                    break

                company_ids = id_data['id']
                self.stdout.write(f"Found {len(company_ids)} company IDs to process.")

                for company_id in company_ids:
                    try:
                        details = api.get_company_details(company_id)
                        if details:
                            created_new, updated_existing = self.update_or_create_company(details)
                            progress.record_progress(
                                ruz_id=company_id,
                                created=created_new,
                                updated=updated_existing
                            )
                        else:
                            progress.record_progress(ruz_id=company_id, skipped=True)
                    except Exception as e:
                        self.stderr.write(f"Error processing company ID {company_id}: {e}")
                        progress.record_progress(ruz_id=company_id, error=True)
                        progress.last_error = str(e)
                    
                    # Be a good API citizen
                    time.sleep(0.1) 

                if not id_data.get('existujeDalsieId'):
                    self.stdout.write(self.style.SUCCESS("Reached the end of the list."))
                    break
                
                # Prepare for the next page
                pokracovat_za_id = company_ids[-1]
                
                # Uložíme progress po každej stránke
                progress.last_processed_ruz_id = pokracovat_za_id
                progress.save()
                
                time.sleep(1)  # Wait a bit before fetching the next page of IDs
            
            # Synchronizácia dokončená
            progress.complete()
            self.stdout.write(self.style.SUCCESS(
                f'Successfully finished RUZ sync.\n'
                f'  Processed: {progress.total_processed}\n'
                f'  Created: {progress.total_created}\n'
                f'  Updated: {progress.total_updated}\n'
                f'  Skipped: {progress.total_skipped}\n'
                f'  Errors: {progress.total_errors}'
            ))
            
        except KeyboardInterrupt:
            # Používateľ prerušil synchronizáciu
            progress.pause('Prerušené používateľom (Ctrl+C)')
            self.stdout.write(self.style.WARNING(
                f'\nSynchronizácia pozastavená. Spracovaných: {progress.total_processed}. '
                f'Pokračujte s: python manage.py fetch_ruz_data --resume'
            ))
            
        except Exception as e:
            # Neočakávaná chyba
            progress.fail(str(e))
            self.stderr.write(self.style.ERROR(f'Synchronizácia zlyhala: {e}'))
            raise

    def update_or_create_company(self, data: dict):
        """Maps API data and saves it to the Company model. Returns (created, updated) tuple."""
        
        if 'ico' not in data:
            self.stderr.write(f"Skipping record with RUZ ID {data.get('id')} because it has no ICO.")
            return False, False

        # Map API fields (camelCase) to model fields (snake_case)
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
            'id_uctovnych_zavierok': data.get('idUctovnychZavierok', list()),
            'id_vyrocnych_sprav': data.get('idVyrocnychSprav', list()),
            'zdroj_dat': data.get('zdrojDat'),
            'datum_poslednej_upravy': parse_date(data.get('datumPoslednejUpravy', '')),
        }

        # Use ICO as the unique identifier for finding existing records
        company, created = Company.objects.update_or_create(
            ico=data['ico'],
            defaults=defaults
        )

        if created:
            self.stdout.write(f"Created new company: {company.nazov_UJ}, IČO: {company.ico}")
        else:
            self.stdout.write(f"Updated company: {company.nazov_UJ}, IČO: {company.ico}")
        
        return created, not created
