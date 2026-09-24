from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import IndividualEntity, SyncJob, SyncProgress
from registers.services.ruz_repair_writer import (
    CREATED, REFUSED, SKIPPED, UPDATED, RepairWriter,
)
from registers.services.sync_engine import (
    claim_ruz_slot_for_cli, complete_job, fail_job, pause_job, set_job_outcome,
)
import logging
import time
import concurrent.futures
import threading

logger = logging.getLogger(__name__)

# How many failure reasons one run keeps. `last_error` is a single column, so it
# has to be bounded; the last 20 is what an operator reading a 449k-row repair
# actually gets through.
ERRORS_KEPT = 20


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
        parser.add_argument(
            '--sync-job-id',
            type=int,
            help='Internal durable SyncJob correlation ID for a Celery-dispatched RUZ run.',
        )

    def handle(self, *args, **options):
        self.api = RuzApi()
        batch_size = options['batch_size']
        num_workers = options['workers']
        self.lock = threading.Lock()
        self.batch_stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        # Every write goes through the walk's own writer. See
        # `registers.services.ruz_repair_writer` for why a private `defaults`
        # dict and an `ico`-keyed upsert were not merely a second style.
        self.writer = RepairWriter(self.stdout, self.stderr)
        self.recent_errors = []

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
        elif (
            progress.status in ['paused', 'failed', 'running']
            and progress.last_processed_ruz_id
        ):
            # `running` belongs here with `paused` and `failed`: a hard kill
            # leaves `running` behind, `REPAIR_RESUMABLE_STATUSES` deliberately
            # admits it (a live run is excluded by the `ruz:global` slot, not by
            # the status), and `resume_repair_sync` logs that it is resuming from
            # this very cursor. Without it the log named a cursor the command
            # then ignored, and a resumed repair started at 0.
            #
            # `completed` is deliberately NOT here, and that is not an oversight.
            # A repair's job is to find the ruz_ids the database lacks, and which
            # those are changes between runs -- ids below a stored cursor would
            # never be looked at again. The cursor is only meaningful for a run
            # that was interrupted, where the prefix really was scanned.
            start_id = progress.last_processed_ruz_id
            self.stdout.write(self.style.SUCCESS(
                f'Pokračujem od RUZ ID {start_id:,}. Doteraz: {progress.total_created:,} nových firiem'
            ))
        else:
            start_id = 0
        
        pokracovat_za_id = start_id

        # Heartbeat for the job this run holds -- the one a Celery dispatcher
        # claimed and handed down, or, for a command typed by an operator, the
        # one claimed just below. `beat` closes over `job_row`, so rebinding that
        # name after the claim is what makes the loop beat the row this run
        # claimed. Without a heartbeat the run looks dead to the watchdog: the
        # loop below can sit inside a single page for minutes, and nothing else
        # writes `last_heartbeat`. Same shape as `fetch_ruz_data`, which is the
        # pattern this follows.
        #
        # `--sync-job-id` names the row this run reports against, and a run
        # given one that names no row has to refuse: every write below would go
        # untracked -- `beat` a no-op, `set_job_outcome` an UPDATE that matches
        # nothing. `fetch_ruz_data` refuses the same input for the same reason
        # ("refusing to walk untracked"). The test is `is not None` rather than
        # truthiness, and that is the whole of it: `--sync-job-id 0` is falsy,
        # so the claim further down was skipped as well and the run imported
        # company rows beside a live walk, unguarded and unrecorded.
        sync_job_id = options.get('sync_job_id')
        job_row = SyncJob.objects.filter(pk=sync_job_id).first() if sync_job_id else None
        if sync_job_id is not None and job_row is None:
            raise CommandError(
                f"RUZ sync job #{sync_job_id} does not exist; refusing to walk untracked."
            )

        def beat() -> None:
            if job_row is not None:
                job_row.heartbeat()

        # The slot is claimed here, after the progress bookkeeping and
        # immediately before the `try`, and both halves of that are the point.
        #
        # A claimed row holds `ruz:global`: migration 0012's partial unique index
        # keeps it for `queued` and `running` only. Every statement between this
        # claim and the `try` is therefore a window in which a raise leaves the
        # row open, refusing every later RUZ run until
        # `detect_and_fail_stuck_jobs` reaps it -- up to the 30-minute staleness
        # threshold. Claiming above `get_or_create` and the progress save would
        # widen that window to two database writes; here the only statements left
        # between the claim and the `try` are assignments and a read of the
        # in-memory `progress`, and the run's first write after claiming is the
        # first statement inside the `try`.
        #
        # A run typed by an operator arrives with no `--sync-job-id`, so nothing
        # had claimed `ruz:global` for it and it wrote company rows beside
        # whatever else was running. It claims its own job here and refuses to
        # start when the slot is taken -- the same thing `fetch_ruz_data` does,
        # and the reason `repair_ruz_gaps`'s Ctrl+C message can point an operator
        # at `--resume` without sending them in unguarded.
        owns_job_lifecycle = False
        job = None
        if sync_job_id is None:
            job = claim_ruz_slot_for_cli(
                job_type="ruz_repair",
                # What this run was actually typed with. The Celery path records
                # the args the task passed down; a hand-run command has to record
                # its own, or the row cannot answer "what was that run?" later.
                parameters={
                    "command": "repair_ruz_sync_v2",
                    "command_args": [
                        f'--workers={num_workers}',
                        f'--batch-size={batch_size}',
                    ] + (
                        [f'--start-id={options["start_id"]}']
                        if options.get('start_id') is not None else []
                    ),
                },
            )
            sync_job_id = job.pk
            # `beat` closes over this name; see its comment above.
            job_row = job
            owns_job_lifecycle = True

        # This run's own numbers. `progress` cannot supply them on its own: its
        # row is reused between runs, so its counters accumulate. The job row is
        # per-run, so what lands there is the difference this run made.
        baseline = (
            progress.total_processed,
            progress.total_created,
            progress.total_updated,
            progress.total_skipped,
            progress.total_errors,
        )

        try:
            # Marked running only now: the slot is held, the cursor is decided,
            # and the next thing that happens is the first page. That is what
            # keeps the claim -> `try` window free of database writes, which is
            # what the comment above the claim is about -- and it is also why a
            # refusal leaves the progress row exactly as it was rather than
            # claiming to be running with nothing behind it.
            progress.status = 'running'
            progress.started_at = timezone.now()
            progress.save()

            self.stdout.write(self.style.WARNING(
                f'Repair sync: štart od ID {start_id:,}, {num_workers} workerov, batch {batch_size}'
            ))

            while True:
                beat()
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
                
                # Which of these the database already holds -- in *either* table.
                # `Company` alone was the work list's whole idea of "held", and
                # every `IndividualEntity.ruz_id` is absent from `Company`
                # (measured on dell 2026-09-18: 35 339 rows and not one of them
                # in `Company`; the count is a snapshot that only grows while the
                # walk runs -- the zero overlap is the part that does not).
                # So the register's natural persons sat in this list
                # permanently: every run re-fetched all 35k detail pages,
                # re-upserted rows that were already correct, and reported each
                # as new work. Excluding them is what makes a repair converge;
                # the walk is what keeps them current.
                held_ids = set(
                    Company.objects.filter(ruz_id__in=company_ids)
                    .values_list('ruz_id', flat=True)
                ) | set(
                    IndividualEntity.objects.filter(ruz_id__in=company_ids)
                    .values_list('ruz_id', flat=True)
                )
                missing_ids = [cid for cid in company_ids if cid not in held_ids]
                
                # Reset batch stats
                self.batch_stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

                # Paralelne stiahneme chýbajúce
                if missing_ids:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                        list(executor.map(self._fetch_and_save, missing_ids))

                # Aktualizujeme progress
                pokracovat_za_id = company_ids[-1]
                progress.last_processed_ruz_id = pokracovat_za_id
                progress.total_processed += len(company_ids)
                progress.total_created += self.batch_stats['created']
                progress.total_updated += self.batch_stats['updated']
                progress.total_skipped += self.batch_stats['skipped']
                progress.total_errors += self.batch_stats['errors']
                # Assigned *before* the save, not after it: this save is what
                # writes the column, and a reason set afterwards would sit in
                # memory while the row kept the old one. The model's own
                # `record_progress` carries the same note, from the same mistake.
                if self.recent_errors:
                    progress.last_error = '\n'.join(self.recent_errors)
                progress.save()

                # Výpis progresu
                self.stdout.write(
                    f'[{progress.total_processed:,}] ID {pokracovat_za_id:,} | '
                    f'exist: {len(held_ids)} | miss: {len(missing_ids)} | '
                    f'new: +{self.batch_stats["created"]} | '
                    f'upd: {self.batch_stats["updated"]} | '
                    f'err: {self.batch_stats["errors"]} | '
                    f'total: {progress.total_created:,}'
                )
                
                if not id_data.get('existujeDalsieId'):
                    self.stdout.write(self.style.SUCCESS('Dosiahnutý koniec.'))
                    break
                
                time.sleep(0.2)  # Krátka pauza medzi stránkami
            
            # Hotovo
            progress.status = 'completed'
            progress.completed_at = timezone.now()
            progress.save()
            if owns_job_lifecycle:
                # Only when this run holds the job itself: a Celery dispatch
                # owns the status of the row it handed down, and a second writer
                # of `status` is how a run gets marked completed before anyone
                # decided it was -- the reason `set_job_outcome` writes counters
                # and nothing else.
                complete_job(job)

            self.stdout.write(self.style.SUCCESS(
                f'\n=== REPAIR DOKONČENÝ ===\n'
                f'Skontrolovaných: {progress.total_processed:,}\n'
                f'Nových firiem: {progress.total_created:,}\n'
                f'Aktualizovaných: {progress.total_updated:,}\n'
                f'Preskočených: {progress.total_skipped:,}\n'
                f'Chýb: {progress.total_errors:,}'
            ))
            if progress.total_errors:
                # The last line of a long run is the one an operator reads, and a
                # count on its own has never been enough to act on. `last_error`
                # holds the most recent reasons; this is where they are pointed
                # at, rather than left for someone to think to look.
                self.stdout.write(self.style.ERROR(
                    f'Dôvody chýb sú v `SyncProgress(id={progress.pk}).last_error`.'
                ))
            
        except KeyboardInterrupt:
            if owns_job_lifecycle:
                # `paused`, not `completed`: the command caught the interrupt and
                # returns normally, so without this the job would read as one
                # that finished everything it meant to. A paused row also
                # releases `ruz:global` -- the partial unique index holds the
                # slot only for `queued` and `running`.
                #
                # Before the `progress.save()` below, not after it, for the
                # reason spelled out in the handler further down: freeing the
                # slot must not depend on a write that can fail.
                pause_job(job, reason="Interrupted by operator (Ctrl+C)")
            progress.status = 'paused'
            progress.notes = f'Prerušené. Posledné ID: {pokracovat_za_id}'
            progress.save()
            self.stdout.write(self.style.WARNING(
                f'\nPozastavené na ID {pokracovat_za_id:,}. '
                f'Pokračujte: python manage.py repair_ruz_sync_v2'
            ))

        except Exception as e:
            if owns_job_lifecycle:
                # Before the `progress.save()` below, not after it. This handler
                # runs because the run just died, most likely on the database,
                # and the write that records the failure is then the write most
                # likely to raise again -- if it did, the exception would leave
                # this handler with `fail_job` never called, and the claimed row
                # would sit `running`, holding `ruz:global` until the watchdog
                # reaped it. Freeing the slot must not depend on a write that can
                # fail.
                fail_job(job, error=f"{type(e).__name__}: {e}")
            progress.status = 'failed'
            progress.last_error = str(e)
            progress.save()
            raise

        finally:
            # Written on every exit path, so a completed job can never be
            # confused with one that did nothing -- the reason
            # `set_job_outcome` exists at all.
            if sync_job_id is not None:
                set_job_outcome(
                    sync_job_id,
                    processed=progress.total_processed - baseline[0],
                    succeeded=(
                        progress.total_created - baseline[1]
                        + progress.total_updated - baseline[2]
                    ),
                    skipped=progress.total_skipped - baseline[3],
                    failed=progress.total_errors - baseline[4],
                )

    def _count_error(self, ruz_id, reason):
        """Count one failure and keep its reason.

        The old handler counted and threw the exception away: `except Exception
        as e:` incremented a counter and never read `e`, and the module did not
        import `logging` at all. A run whose every write was refused therefore
        ended `completed`, durably, with a number and no cause anywhere -- not on
        the row, not in a log, not on stderr.
        """
        logger.error("Repair failed for RUZ id %s: %s", ruz_id, reason)
        with self.lock:
            self.batch_stats['errors'] += 1
            self.recent_errors.append(f"{ruz_id}: {reason}")
            # The most recent ones, not the first ones: a run that fails for
            # 40 000 records has one cause, and it is at the end too.
            del self.recent_errors[:-ERRORS_KEPT]

    def _fetch_and_save(self, ruz_id):
        """Stiahne a uloží jednu firmu (thread-safe)."""
        details = None
        try:
            details = self.api.get_company_details(ruz_id)

            if not details:
                # 404 alebo deleted
                with self.lock:
                    self.batch_stats['skipped'] += 1
                return

            if 'ico' not in details:
                with self.lock:
                    self.batch_stats['skipped'] += 1
                return

            # The walk's writer, not a private `defaults` dict. It keys on
            # `ruz_id`, so a second entity under an IČO we already hold is refused
            # instead of taking the row over; it carries `apply_ruz_dates`, so an
            # unreadable date cannot overwrite a stored one; it routes SZCO legal
            # forms to `IndividualEntity`; and it strips the IČO.
            outcome, reason = self.writer.store(ruz_id, details)
        except Exception as e:
            self._count_error(ruz_id, f"{type(e).__name__}: {e}")
            return

        with self.lock:
            if outcome is CREATED:
                self.batch_stats['created'] += 1
            elif outcome is UPDATED:
                self.batch_stats['updated'] += 1
            elif outcome is SKIPPED:
                self.batch_stats['skipped'] += 1

        if outcome is REFUSED:
            self._count_error(ruz_id, reason)
