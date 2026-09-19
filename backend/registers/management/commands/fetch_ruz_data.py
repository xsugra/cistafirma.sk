from django.core.management.base import BaseCommand, CommandError
from django.db import DataError, IntegrityError
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import timedelta
from companies.models import Company
from registers.models import IndividualEntity, SyncJob, SyncProgress
from registers.integrations.ruz_api import RuzApi, apply_ruz_dates
from registers.services.sync_engine import record_ruz_date_outcome
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
        # Strict on purpose. The loose default answers `None` for two different
        # things -- a company the register says does not exist (a 404, or
        # `stav: ZMAZANÉ`) and a registry that never answered at all -- and the
        # walk below files both under `skipped`, writing no per-company row for
        # either. Since a completed walk now moves the window past everything
        # it read, the second kind would never be read again: the only place it
        # is remembered is the window, and the window would have moved. Strict
        # turns it into an item error instead, which holds the window where it
        # is (see the advance at the end of the walk) and re-reads it next run.
        api = RuzApi(raise_on_transport_error=True)
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
        
        # The resume cursor belongs to the run that set it. Only `--resume` may
        # pick it up again.
        #
        # This branch used to fall back to `progress.last_processed_ruz_id` for
        # a *fresh* run too, and that is what stopped the incremental sync
        # dead from 2026-09-11 without ever reporting a failure. A run that
        # walks its window to the end leaves the field on that window's last
        # id; the next run then asked RUZ for changes *after the end of a list
        # it had already finished*, got an empty page, and `break` reads an
        # empty page as "reached the end". So it called `complete_job` and was
        # stored as `completed` with zero items -- ten times, every six hours,
        # while `zmenene_od` sat still and the window it described grew.
        #
        # Verified against the live register: `zmenene-od=2026-08-04` alone
        # returned 1000 ids, the same request with `pokracovat-za-id=2624307`
        # returned none. A cursor that outlives its run turns a working sync
        # into a no-op that reports success.
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
            pokracovat_za_id = None
        
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

        from registers.services.sync_engine import heartbeat_gate, set_job_outcome

        # Nothing else beats this job's heart. Heartbeats were meant to come
        # from `record_item`, called by the per-company `tracked_sync_task`
        # tasks -- but that decorator was applied to no task and both are now
        # deleted, so in practice nothing wrote a heartbeat at all and a
        # multi-hour resync looked exactly like a dead job. That is why the
        # watchdog could not be switched on until this explicit beat existed.
        job_row = SyncJob.objects.filter(pk=sync_job_id).first()
        if job_row is None:
            # Only reachable if the row went away under a running walk, and it
            # has to stop the walk rather than be shrugged off: with no row
            # there is no heartbeat, so the job the watchdog would reap does not
            # exist at all -- and `set_job_outcome` below is a
            # `filter(pk=...).update()`, which reports nothing when the row it
            # writes to is gone. The run would import into `SyncProgress` while
            # the keeper, seeing no live job, dispatched a second walk over the
            # same window. Loud beats silent here.
            raise CommandError(
                f"RUZ sync job #{sync_job_id} is gone; refusing to walk untracked."
            )

        # Gated on the clock, so it can be called on every record without
        # writing a row each time. See `HEARTBEAT_INTERVAL_SECONDS` for why
        # this replaced an `index % 50` count.
        beat = heartbeat_gate(job_row)

        # This run's own numbers. `progress` cannot supply them: its row is
        # reused between runs and `start()` resets only `started_at`, so its
        # counters accumulate -- the 12:22 run logged 6350 before it began and
        # 6367 after handling 17 records. The job row is per-run, so the counts
        # belong there.
        run = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            # Two kinds of failure that need opposite responses from the window
            # guard below, so they are counted apart even though both raise:
            #
            # - `unreadable`: the call never returned a record. A hole, and the
            #   window is the only place it could be remembered, so the window
            #   holds and the next run reads it again.
            # - `unstorable`: the record came back and our schema cannot hold
            #   it. Measured on 2026-09-13: RUZ id 1520199 fails with `value too
            #   long for type character varying(8)`, because RUZ gives
            #   organisational units a 12-character IČO (`001781521576` --
            #   parent `00178152` plus a serial) and `Company.ico` is
            #   `varchar(8)`. Re-reading returns the same value, so holding the
            #   window would never help; it would only re-read everything inside
            #   it, forever, and pin the gate red.
            "unreadable": 0,
            "unstorable": 0,
        }
        # The records we read but could not store, kept so the hole is named
        # rather than only counted. See the note written to `progress` below.
        unstorable_ids: list[str] = []

        # The day this run started, read once. It is what the window advances
        # to if the walk completes -- see the end of the loop.
        run_started_on = timezone.localdate()

        try:
            while True:
                beat()
                self.stdout.write(
                    f"[{progress.total_processed}] Fetching company IDs changed since {zmenene_od}, "
                    f"starting after ID {pokracovat_za_id or 0}..."
                )
                
                id_data = api.get_changed_company_ids(zmenene_od=zmenene_od, pokracovat_za_id=pokracovat_za_id)

                # A registry we cannot reach raises out of the call above and
                # fails the run. Only a page that genuinely carries no IDs ends
                # the loop, because an unreachable registry and an empty one
                # used to arrive here as the same falsy value -- and that stored
                # a transport failure as `completed`, processed_items=0.
                if not id_data or not id_data.get('id'):
                    self.stdout.write(self.style.SUCCESS("No more company IDs to fetch."))
                    break

                company_ids = id_data['id']
                self.stdout.write(f"Found {len(company_ids)} company IDs to process.")

                for company_id in company_ids:
                    # Bound before the call so the handler below can name the
                    # record from whatever arrived, without risking a NameError
                    # on the first iteration if the fetch itself is what raised.
                    details = None
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
                    except (DataError, IntegrityError) as e:
                        # The record arrived and our schema refused it. Filed
                        # apart from the transport case on purpose: this one
                        # will not fix itself by being read again. See `run`.
                        #
                        # `IntegrityError` belongs here with `DataError`, and the
                        # distinction matters more than it looks: a unique-index
                        # refusal (a second entity under an IČO we already hold)
                        # is just as deterministic as an over-long value. Filed
                        # as `unreadable` it would hold the window, and because
                        # re-reading returns the same collision, it would hold it
                        # **forever** while every beat re-walked the whole window
                        # -- the exact failure #83 closed.
                        self.stderr.write(
                            f"Unstorable record ID {company_id}: {e}"
                        )
                        progress.record_progress(
                            ruz_id=company_id, error=True, error_message=str(e)
                        )
                        unstorable_ids.append(
                            f"{company_id} ({details.get('ico') if details else '?'})"
                        )
                        run["processed"] += 1
                        run["errors"] += 1
                        run["unstorable"] += 1
                    except Exception as e:
                        self.stderr.write(f"Error processing company ID {company_id}: {e}")
                        progress.record_progress(
                            ruz_id=company_id, error=True, error_message=str(e)
                        )
                        run["processed"] += 1
                        run["errors"] += 1
                        run["unreadable"] += 1

                    # Be a good API citizen
                    time.sleep(0.1)

                    # Called on every record, and writes only when the clock
                    # says a write is due. A page is up to 1000 companies, so
                    # the per-page beat alone would be minutes apart -- but so
                    # would "every 50 records" once a record can cost two
                    # minutes instead of 0.1s, which is why the gate is on the
                    # gap rather than on a count of items.
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
            
            # The window this run walked is finished, so the next run must not
            # walk it again from the start. Clearing the cursor alone would
            # have every beat run re-scan everything back to 2026-08-04; the
            # cursor and the window have to move together or the sync is either
            # stuck or wasteful.
            #
            # `zmenene_od` is a `DateField`, so the finest cursor *we can
            # store* is a day. That is our schema rather than the register's --
            # its API takes a timestamp -- and it is why the new start is the
            # run's own start day minus one day of overlap. Without the overlap
            # a company that changed in the last hours of the window -- after
            # the page carrying its id had already been read -- would fall
            # between the two windows and never be seen at all. With it, the
            # tail day is simply re-read, which the upserts absorb.
            #
            # Two conditions gate the move, and both are about what "this
            # window was walked" has to mean for the claim to be honest:
            #
            # - **No item failed.** Moving the window asserts that everything
            #   inside it was read. A company whose read failed gets no
            #   per-company row at all, so the window is the only thing that
            #   remembers it was skipped -- and moving the window would drop it
            #   silently and permanently. Holding the window re-reads it next
            #   run. Measured before relying on this: no RUZ job in this
            #   database has ever recorded a failed or skipped item, so the
            #   condition costs nothing in practice.
            # - **Only the incremental walk.** The `full*` types choose their
            #   start elsewhere: `full` hardcodes 2000-01-01, while
            #   `full_companies` and `full_individuals` read it back out of
            #   this very column. Writing `today - 1` into the column a full
            #   resync reads would shrink the next one to a single day.
            #
            # `>` and not `>=`: a run that finishes on the same day it started
            # would otherwise write the window backwards.
            window_end = run_started_on - timedelta(days=1)
            holds_window = sync_type.startswith('full') or run["unreadable"] > 0
            if holds_window:
                reason = (
                    f'{run["unreadable"]} položiek sa nepodarilo prečítať'
                    if run["unreadable"]
                    else f'typ {sync_type} si okno nespravuje'
                )
                self.stdout.write(self.style.WARNING(
                    f'Okno neposunuté ({reason}): zostáva od {zmenene_od}.'
                ))
            elif window_end > parse_date(zmenene_od):
                progress.zmenene_od = window_end
                progress.save(update_fields=['zmenene_od'])
                self.stdout.write(self.style.SUCCESS(
                    f'Okno posunuté: ďalšia synchronizácia pôjde od {window_end}.'
                ))

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

            # A record we read and could not store leaves no row anywhere: the
            # window moves past it and the next run never looks at it again. So
            # it is named here, on the row that survives, and written out --
            # otherwise the hole is invisible and a later fix would have nothing
            # to backfill from. Deliberately not filed under
            # `CompanySyncStatus(source='ruz')`: that lane means "we re-read
            # this company's dates", and 9 244 rows of it currently say that
            # succeeded. Mixing a walk failure into it would make both readings
            # wrong at once.
            if unstorable_ids:
                listed = ', '.join(unstorable_ids[:50])
                more = (
                    f' (+{len(unstorable_ids) - 50} more)'
                    if len(unstorable_ids) > 50
                    else ''
                )
                progress.notes = (
                    f'{len(unstorable_ids)} záznamov sa nedalo uložiť, '
                    f'okno ich preskočilo: {listed}{more}'
                )
                progress.save(update_fields=['notes'])
                self.stdout.write(self.style.WARNING(
                    f'  Unstorable: {len(unstorable_ids)} -- read but not '
                    f'stored, and the window moved past them: {listed}{more}'
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

        # The register's own key, and the only thing that identifies a *record*.
        # `ruz_id` is `unique` and every record the walk can see carries one.
        #
        # Keying the upsert on `ico` instead was a silent identity swap, not
        # merely a collision: `update_or_create(ico=X, defaults={'ruz_id': Y})`
        # finds the row **by IČO** and then re-stamps its `ruz_id` to `Y` --
        # which succeeds without error whenever no row holds `Y` yet. The row
        # that was entity `Z` then claims to be entity `Y`. Measured 2026-09-13:
        # the register answers `00177474` with three distinct entities
        # (ruz_id 1677, 1049449, 1070716).
        ruz_id = data.get('id')

        # `.strip()` and nothing else. The register pads old 6- and 7-digit IČO
        # to eight characters with spaces (`'177474  '`), so an unstripped value
        # never matches a lookup -- every lookup path does `.strip().zfill(8)`.
        # But `.zfill(8)` must NOT be applied here: `'177474  '` (DHZ
        # Sološnica) and `'00177474'` (DHZ Nová Kelča) are two *different*
        # organisational units, and padding the first would merge them into one.
        # Zero-padding is a query parameter, not a stored identity.
        ico = str(data.get('ico') or '').strip()

        if not ico:
            self.stderr.write(
                f"Skipping record with RUZ ID {ruz_id} because it has no usable ICO."
            )
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
            'ruz_id': ruz_id,
            'ico': ico,
            'dic': data.get('dic'),
            'sid': data.get('sid'),
            'nazov_UJ': data.get('nazovUJ', ''),
            'mesto': data.get('mesto'),
            'ulica': data.get('ulica'),
            'psc': data.get('psc'),
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
        }

        # The three date fields go in together, and a field whose value we
        # cannot read is left out entirely -- `update_or_create` then keeps
        # what is stored instead of overwriting it with `None`. See
        # `apply_ruz_dates` for why those two cases have to be told apart.
        refused_dates = apply_ruz_dates(common_defaults, data)

        if is_szco:
            # Save to IndividualEntity
            entity, created = IndividualEntity.objects.update_or_create(
                ruz_id=ruz_id,
                defaults=common_defaults
            )

            if created:
                self.stdout.write(f"Created new SZCO/individual: {entity.nazov_UJ}, IČO: {entity.ico}")
            else:
                self.stdout.write(f"Updated SZCO/individual: {entity.nazov_UJ}, IČO: {entity.ico}")

            # An SZCO has no `Company` row, and `CompanySyncStatus.company` is a
            # non-nullable FK to one, so a refused date here has nowhere to be
            # recorded. Reported on stderr rather than dropped in silence: the
            # gap is real, and a warning that names the field is the difference
            # between a known limitation and a lost signal.
            if refused_dates:
                self.stderr.write(
                    f"Unreadable date(s) for SZCO {entity.ico} could not be "
                    f"recorded against the source (no Company row): "
                    + ", ".join(f"{key}={raw!r}" for key, raw in refused_dates)
                )
        else:
            # Save to Company (LPO - legal entities)
            # Add company-specific fields if needed

            # `update_or_create` discards the row it matched, so once the write
            # lands there is no way to tell whether the company was already
            # dissolved. Read the previous value first -- and only when the
            # incoming record HAS a dissolution date, which keeps this extra
            # query off the 73% of the batch that is not being dissolved.
            # `.get`, not `[...]`: an unreadable `datumZrusenia` is left out of
            # the defaults, so the key may genuinely be missing -- and in that
            # case nothing about the company's status is changing, which is
            # exactly what a `None` here means to `detect_status_change`.
            new_zrusenie = common_defaults.get('datum_zrusenia')
            previous_zrusenie = None
            if new_zrusenie is not None:
                # Keyed on `ruz_id`, matching the write below: reading the
                # previous date by IČO would, for a duplicated IČO, compare this
                # company's dissolution against a sibling's -- announcing a
                # transition that did not happen, or missing one that did.
                previous_zrusenie = (
                    Company.objects.filter(ruz_id=ruz_id)
                    .values_list('datum_zrusenia', flat=True)
                    .first()
                )

            company, created = Company.objects.update_or_create(
                ruz_id=ruz_id,
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
                        # `new_zrusenie`, not `company.datum_zrusenia`: the
                        # latter reads the row back, so when `apply_ruz_dates`
                        # has just declined to write an unreadable value it
                        # would hand `detect_status_change` the *stored* date
                        # as though it were new -- announcing an untouched
                        # date as a dissolution.
                        new_datum_zrusenia=new_zrusenie,
                    )
                except Exception:
                    logger.error(
                        "Failed to detect status change for %s", company.ico, exc_info=True
                    )
                self.stdout.write(f"Updated company: {company.nazov_UJ}, IČO: {company.ico}")

            # One row per company per run, carrying either the success or the
            # refusal -- see `record_ruz_date_outcome` for why both halves have
            # to be written for either to be worth anything. Called with the
            # whole list so two refused fields are one attempt, not two.
            #
            # This is the write that puts a refused date in front of the four
            # admin surfaces; before it, `ruz` had no success path at all and
            # the refusal was visible only to `source_health`.
            record_ruz_date_outcome(company_id=company.id, refused=refused_dates)

        return created, not created
