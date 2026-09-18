"""The first repair command. Superseded, and it cannot run.

`repair_ruz_sync_v2` does this job, and it is the one dispatch actually uses
(`registers/tasks.py`), the one the admin button starts, and the one #186 gave a
`SyncJob` row, a heartbeat and the `ruz:global` lock.

This file is not that command with a different name. It is a half-finished
rewrite that was left in place, and it stops on its first non-empty page:

* `self._fetch_and_save_company` has never existed on this class -- the method
  defined below is `_update_or_create_company`.
* `api.get_company_details` inside `handle` names a local that is never bound;
  the client is `self.api`.
* `total_missing` and `total_downloaded` / `total_skipped` / `total_errors` are
  read before they are ever assigned.
* the thread pool and the sequential loop below it fetch the *same*
  `missing_ids` twice, and the pool's own counters (`batch_downloaded` and
  friends) are never read again.
* there are two `def handle` methods. The second one wins, which is why the
  first thing anyone does with this file -- read its `handle` -- tells them
  nothing about what runs.

It is therefore harmless today -- it raises before it writes anything -- but not
by design, and not visibly: an operator who types the obvious name gets an
`AttributeError` from inside a thread pool, and the `except Exception` at the end
of `handle` first flips the shared `sync_type='repair'` progress row to `failed`.
That row is `repair_ruz_sync_v2`'s own cursor, so the failure is not even
contained to this command.

`handle` now refuses at the top and names the command to use, so the obvious
name gives an answer instead of a traceback. The write path is delegated all the
same: it is the pattern someone would copy, and no copy of the identity swap
described in `registers.services.ruz_repair_writer` should be left in the tree.

Recommendation: delete this file. It is kept only because it was not mine to
remove, and because deleting a management command is a decision for the person
who owns the deploy.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncProgress
from registers.services.ruz_repair_writer import RepairWriter
import time
import concurrent.futures


class Command(BaseCommand):
    help = (
        'NEPOUŽÍVAŤ - nahradené príkazom repair_ruz_sync_v2. '
        'Tento súbor je nedokončený a spadne.'
    )

    def handle(self, *args, **options):
        raise CommandError(
            'repair_ruz_sync je nahradený a nefunkčný -- použite '
            '`python manage.py repair_ruz_sync_v2`. '
            'Dôvod je v docstringu tohto modulu.'
        )

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

    # NOT `handle`. This was the second `def handle` in the file, and the last
    # definition wins -- so while it kept that name, `handle` above was dead code
    # and the refusal never ran: `call_command('repair_ruz_sync')` went straight
    # into this body and died on `Company` at the work-list line, which is the
    # traceback the v1 test caught. Nothing dispatches a name that is not
    # `handle`, so renaming it is what makes the refusal real; the body stays
    # because it is the record of what the half-finished rewrite did.
    def _handle_unfinished(self, *args, **options):
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
        """Uloží firmu do DB -- cez ten istý zapisovač, aký používa walk.

        Telo tejto metódy bol tretí `defaults` dict v repozitári: `ruz_id`
        v `defaults`, ale lookup na `ico`, takže druhá entita pod už držaným IČO
        si riadok prevzala; holé `parse_date`, takže nečitateľný dátum prepísal
        uložený; a žiadne smerovanie SZCO právnych foriem do `IndividualEntity`.

        Metóda je nedosiahnuteľná -- `handle` odmietne na prvom riadku -- a to je
        zámer: opraviť ju znamená vzkriesiť príkaz, ktorý nemá job riadok,
        heartbeat ani globálny zámok (#186). Deleguje sa preto, aby tá chyba
        neostala v strome ako vzor na skopírovanie, a aby platilo, že všetky tri
        opravné príkazy ukladajú rovnako (#187).
        """
        if not hasattr(self, 'writer'):
            self.writer = RepairWriter(self.stdout, self.stderr)
        outcome, _ = self.writer.store(data.get('id'), data)
        return outcome == 'created', outcome == 'updated'
