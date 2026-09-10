from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date
from django.utils import timezone
from companies.models import Company
from registers.models import IndividualEntity, SyncJob, SyncProgress
from registers.integrations.ruz_api import RuzApi
import logging
import time

logger = logging.getLogger(__name__)

# Legal form codes for SZCO (individual entities)
SZCO_LEGAL_FORMS = {
    '100', '101', '102', '103', '104', '105', '106', '107', '108', '109', '110',  # Natural persons
    '422'  # Foreign natural person
}


class Command(BaseCommand):
    help = 'Fetches and updates company data from the RUZ API with progress tracking. Separates companies from SZCO/individuals.'

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
        parser.add_argument(
            '--entity-type',
            choices=['companies', 'individuals', 'both'],
            default='both',
            help='Sync specific entity types: companies (LPO), individuals (SZCO), or both. Default: both',
        )
        parser.add_argument(
            '--sync-job-id',
            type=int,
            help='Internal durable SyncJob correlation ID for a Celery-dispatched RUZ run.',
        )

    def handle(self, *args, **options):
        api = RuzApi()
        entity_type = options.get('entity_type', 'both')
        owns_job_lifecycle = False

        # Determine sync_type based on entity_type and full_resync flag
        if entity_type == 'companies':
            sync_type = 'full_companies' if options['full_resync'] else 'incremental_companies'
        elif entity_type == 'individuals':
            sync_type = 'full_individuals' if options['full_resync'] else 'incremental_individuals'
        else:  # both
            sync_type = 'full' if options['full_resync'] else 'incremental'

        sync_job_id = options.get("sync_job_id")
        if sync_job_id is None:
            from registers.services.sync_engine import claim_ruz_job, enqueue_ruz_job

            job_type = {
                "full": "ruz_full",
                "full_companies": "ruz_full_firmy",
                "full_individuals": "ruz_full_szco",
            }.get(sync_type, "ruz_incremental")
            job, created = enqueue_ruz_job(
                job_type=job_type,
                parameters={"sync_type": sync_type, "entity_type": entity_type},
                triggered_via="cli",
            )
            if not created:
                raise CommandError(
                    f"RUZ sync job #{job.pk} is already active; refusing concurrent import."
                )
            if claim_ruz_job(job.pk) is None:
                raise CommandError(f"Unable to claim RUZ sync job #{job.pk}.")
            sync_job_id = job.pk
            owns_job_lifecycle = True

        # Pri resume najprv nájdeme existujúci pozastavený sync
        if options['resume']:
            # Hľadáme sync s kompatibilnými typmi (pre backward compatibility)
            progress = SyncProgress.objects.filter(
                sync_type=sync_type,
                status__in=['paused', 'failed', 'running']
            ).first()

            # Ak nenajdeme presný typ, skúsime hľadať podľa starých typov
            if not progress and sync_type in ['full_companies', 'full_individuals']:
                progress = SyncProgress.objects.filter(
                    sync_type='full',
                    status__in=['paused', 'failed', 'running']
                ).first()
            elif not progress and sync_type in ['incremental_companies', 'incremental_individuals']:
                progress = SyncProgress.objects.filter(
                    sync_type='incremental',
                    status__in=['paused', 'failed', 'running']
                ).first()

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
            if entity_type == 'companies':
                sync_type = 'full_companies' if options['full_resync'] else 'incremental_companies'
            elif entity_type == 'individuals':
                sync_type = 'full_individuals' if options['full_resync'] else 'incremental_individuals'
            else:  # both
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

        from registers.services.sync_engine import set_job_outcome

        # Nothing else beats this job's heart. Heartbeats come from
        # `record_item`, which only the per-company `tracked_sync_task` tasks
        # call, and this command never does -- so a multi-hour resync looked
        # exactly like a dead job. That is why the watchdog could not be
        # switched on until this existed.
        job_row = SyncJob.objects.filter(pk=sync_job_id).first()

        def beat() -> None:
            if job_row is not None:
                job_row.heartbeat()

        # This run's own numbers. `progress` cannot supply them: its row is
        # reused between runs and `start()` resets only `started_at`, so its
        # counters accumulate -- the 12:22 run logged 6350 before it began and
        # 6367 after handling 17 records. The job row is per-run, so the counts
        # belong there.
        run = {"processed": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            while True:
                beat()
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

                for index, company_id in enumerate(company_ids, start=1):
                    try:
                        details = api.get_company_details(company_id)
                        if details:
                            created_new, updated_existing = self.update_or_create_company(details, entity_type)
                            progress.record_progress(
                                ruz_id=company_id,
                                created=created_new,
                                updated=updated_existing
                            )
                            run["processed"] += 1
                            if created_new:
                                run["created"] += 1
                            elif updated_existing:
                                run["updated"] += 1
                        else:
                            progress.record_progress(ruz_id=company_id, skipped=True)
                            run["processed"] += 1
                            run["skipped"] += 1
                    except Exception as e:
                        self.stderr.write(f"Error processing company ID {company_id}: {e}")
                        progress.record_progress(ruz_id=company_id, error=True)
                        progress.last_error = str(e)
                        run["processed"] += 1
                        run["errors"] += 1

                    # Be a good API citizen
                    time.sleep(0.1)

                    # A page is up to 1000 companies, so at 0.1s each the
                    # per-page beat alone would be minutes apart. Every 50
                    # keeps the gap far below any sane staleness threshold.
                    if index % 50 == 0:
                        beat()

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
            if owns_job_lifecycle:
                from registers.services.sync_engine import complete_job
                complete_job(job)
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
            if owns_job_lifecycle:
                from registers.services.sync_engine import pause_job
                pause_job(job, reason="Interrupted by operator")
            
        except Exception as e:
            # Neočakávaná chyba
            progress.fail(str(e))
            if owns_job_lifecycle:
                from registers.services.sync_engine import fail_job
                fail_job(job, error=f"{type(e).__name__}: {e}")
            self.stderr.write(self.style.ERROR(f'Synchronizácia zlyhala: {e}'))
            raise
        finally:
            # Recorded on every exit path -- completed, interrupted, or failed --
            # so a job's counters always describe the work that was actually
            # done. A job that reports zero cannot be told apart from one that
            # did nothing, which is exactly how 17 created companies came to be
            # stored as `processed_items=0`.
            set_job_outcome(
                sync_job_id,
                processed=run["processed"],
                succeeded=run["created"] + run["updated"],
                failed=run["errors"],
                skipped=run["skipped"],
            )

    def update_or_create_company(self, data: dict, entity_type: str = 'both'):
        """
        Maps API data and saves it to Company or IndividualEntity model depending on legal form.
        Returns (created, updated) tuple.

        - SZCO/Natural persons (legal forms 100-110, 422) → IndividualEntity
        - Companies (LPO, s.r.o., a.s., etc.) → Company

        Args:
            data: Dictionary with company/individual data from RUZ API
            entity_type: Filter by entity type: 'companies', 'individuals', or 'both' (default)
        """

        if 'ico' not in data:
            self.stderr.write(f"Skipping record with RUZ ID {data.get('id')} because it has no ICO.")
            return False, False

        # Determine if this is a SZCO/individual or a company
        pravna_forma = str(data.get('pravnaForma', '')).strip()
        is_szco = pravna_forma in SZCO_LEGAL_FORMS

        # Filter by entity_type if specified
        if entity_type == 'companies' and is_szco:
            return False, False  # Skip individuals when syncing companies only
        elif entity_type == 'individuals' and not is_szco:
            return False, False  # Skip companies when syncing individuals only

        # Common fields for both models
        common_defaults = {
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


        if is_szco:
            # Save to IndividualEntity
            entity, created = IndividualEntity.objects.update_or_create(
                ico=data['ico'],
                defaults=common_defaults
            )

            if created:
                self.stdout.write(f"Created new SZCO/individual: {entity.nazov_UJ}, IČO: {entity.ico}")
            else:
                self.stdout.write(f"Updated SZCO/individual: {entity.nazov_UJ}, IČO: {entity.ico}")
        else:
            # Save to Company (LPO - legal entities)
            # Add company-specific fields if needed

            # `update_or_create` discards the row it matched, so once the write
            # lands there is no way to tell whether the company was already
            # dissolved. Read the previous value first -- and only when the
            # incoming record HAS a dissolution date, which keeps this extra
            # query off the 73% of the batch that is not being dissolved.
            new_zrusenie = common_defaults['datum_zrusenia']
            previous_zrusenie = None
            if new_zrusenie is not None:
                previous_zrusenie = (
                    Company.objects.filter(ico=data['ico'])
                    .values_list('datum_zrusenia', flat=True)
                    .first()
                )

            company, created = Company.objects.update_or_create(
                ico=data['ico'],
                defaults=common_defaults
            )

            if created:
                # A company first seen already dissolved is not a transition --
                # we never knew it as active, so there is nothing to announce.
                # This branch being the `created` one is what enforces that.
                self.stdout.write(f"Created new company: {company.nazov_UJ}, IČO: {company.ico}")
            else:
                try:
                    from notifications.services import detect_status_change
                    detect_status_change(
                        company_ico=company.ico,
                        company_name=company.nazov_UJ,
                        old_datum_zrusenia=previous_zrusenie,
                        new_datum_zrusenia=company.datum_zrusenia,
                    )
                except Exception:
                    logger.error(
                        "Failed to detect status change for %s", company.ico, exc_info=True
                    )
                self.stdout.write(f"Updated company: {company.nazov_UJ}, IČO: {company.ico}")

        return created, not created
