from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncGapAnalysis, SyncJob
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
# has to be bounded.
ERRORS_KEPT = 20


class Command(BaseCommand):
    help = 'Opraví chýbajúce RUZ záznamy podľa výsledkov analýzy dier.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--analysis-id',
            type=int,
            default=None,
            help='ID analýzy (SyncGapAnalysis) na opravu. Ak nie je zadané, použije poslednú.',
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=5,
            help='Počet paralelných workerov (default: 5)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Veľkosť batch-u pre progress update (default: 100)',
        )
        parser.add_argument(
            '--resume',
            action='store_true',
            help='Pokračovať od posledného opravenéha ID',
        )
        parser.add_argument(
            '--sync-job-id',
            type=int,
            help='Internal durable SyncJob correlation ID for a Celery-dispatched RUZ run.',
        )

    def handle(self, *args, **options):
        self.api = RuzApi()
        num_workers = options['workers']
        batch_size = options['batch_size']
        self.lock = threading.Lock()
        self.batch_stats = {'repaired': 0, 'skipped': 0, 'errors': 0}
        # Every write goes through the walk's own writer. See
        # `registers.services.ruz_repair_writer` for why a private `defaults`
        # dict and an `ico`-keyed upsert were not merely a second style.
        self.writer = RepairWriter(self.stdout, self.stderr)
        self.recent_errors = []
        
        # Nájdeme analýzu
        if options['analysis_id']:
            analysis = SyncGapAnalysis.objects.filter(id=options['analysis_id']).first()
            if not analysis:
                self.stdout.write(self.style.ERROR(f'Analýza #{options["analysis_id"]} nenájdená!'))
                return
        else:
            analysis = SyncGapAnalysis.objects.filter(
                status__in=['ready', 'repairing']
            ).order_by('-created_at').first()
            
            if not analysis:
                self.stdout.write(self.style.ERROR(
                    'Žiadna analýza pripravená na opravu!\n'
                    'Najskôr spustite: python manage.py analyze_ruz_gaps'
                ))
                return
        
        self.stdout.write(self.style.WARNING(f'=== OPRAVA DIER - Analýza #{analysis.id} ==='))
        self.stdout.write(f'Rozsah: {analysis.analyzed_min_id:,} - {analysis.analyzed_max_id:,}')
        self.stdout.write(f'Celkom chýbajúcich: {analysis.total_missing:,}')
        self.stdout.write(f'Počet dier: {analysis.total_gaps}')
        
        if options['resume'] and analysis.repair_progress_id:
            self.stdout.write(f'Pokračujem od ID: {analysis.repair_progress_id:,}')
        
        # Heartbeat for the job this run holds -- the one a Celery dispatcher
        # claimed and handed down, or, for a command typed by an operator, the
        # one claimed further down. `beat` closes over `job_row`, so rebinding
        # that name after the claim is what makes the write loop below beat the
        # row this run claimed. Without a heartbeat this run looks dead to the
        # watchdog and is reaped mid-repair. See `fetch_ruz_data`.
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

        # This run's own numbers: `analysis` is reused by a resume, so its
        # counters accumulate. The job row is per-run and gets the difference.
        baseline = (
            analysis.repaired_count,
            analysis.skipped_count,
            analysis.error_count,
        )

        # Zozbierame všetky chýbajúce ID do zoznamu
        self.stdout.write('Pripravujem zoznam chýbajúcich ID...')

        missing_ids = []
        for gap_range in analysis.gap_ranges:
            beat()
            start, end = gap_range
            for ruz_id in range(start, end + 1):
                # Skip už opravené ID
                if options['resume'] and analysis.repair_progress_id and ruz_id <= analysis.repair_progress_id:
                    continue
                missing_ids.append(ruz_id)

        if not missing_ids:
            # Nothing is claimed yet at this point, so this return has no job to
            # close -- and must not have one. A run with no work to do did no
            # work; a row claimed above this would be a job for having done
            # nothing, and if anything raised between claiming it and here it
            # would hold `ruz:global` until the watchdog reaped it.
            self.stdout.write(self.style.SUCCESS('Všetky ID už boli opravené!'))
            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()
            return

        self.stdout.write(f'Zostáva opraviť: {len(missing_ids):,} ID')
        self.stdout.write(f'Používam {num_workers} workerov...')

        # The slot is claimed here, and both "here" and "now" are the point.
        #
        # A claimed row holds `ruz:global`: migration 0012's partial unique index
        # keeps it for `queued` and `running` only. So every statement between
        # this claim and the `try` below is a window in which a raise leaves that
        # row open, refusing every later RUZ run until `detect_and_fail_stuck_jobs`
        # reaps it -- up to the 30-minute staleness threshold. Claiming above the
        # work-list build would open that window across a loop with one iteration
        # per missing RUZ id, minutes on a real analysis, and a Ctrl+C in there is
        # caught by nothing: `except KeyboardInterrupt` is inside the `try`. The
        # only statements left between the claim and the `try` are assignments and
        # a read of the in-memory `analysis`; the first database write this run
        # makes after claiming is the first statement inside the `try`.
        #
        # A command typed by an operator is the one RUZ entry point nothing
        # upstream claims the slot for: no task and no admin dispatch hands it a
        # `--sync-job-id`, so it wrote company rows beside whatever else was
        # running. This is also the path the Ctrl+C message at the end of
        # `handle` sends operators down.
        owns_job_lifecycle = False
        job = None
        if sync_job_id is None:
            job = claim_ruz_slot_for_cli(
                job_type="ruz_repair",
                # What this run was actually typed with, for the same reason
                # `repair_ruz_sync_v2` records its own: `ruz_repair` covers two
                # commands and the row has to say which one, and how.
                parameters={
                    "command": "repair_ruz_gaps",
                    "command_args": [
                        f'--workers={num_workers}',
                        f'--batch-size={batch_size}',
                        f'--analysis-id={analysis.pk}',
                    ] + (['--resume'] if options['resume'] else []),
                },
            )
            sync_job_id = job.pk
            # `beat` closes over this name; see its comment above.
            job_row = job
            owns_job_lifecycle = True

        processed = 0
        start_time = time.time()

        try:
            # Marked repairing only now: the slot is held, the work list is
            # built, and the next thing that happens is the first write. That is
            # what keeps the claim -> `try` window free of database writes, which
            # is what the comment above the claim is about -- and it is also why
            # a refusal leaves the analysis row exactly as it was.
            analysis.status = 'repairing'
            analysis.save()

            # Spracujeme v batch-och pre lepší progress tracking
            for i in range(0, len(missing_ids), batch_size):
                beat()
                batch = missing_ids[i:i + batch_size]
                self.batch_stats = {'repaired': 0, 'skipped': 0, 'errors': 0}
                
                # Paralelne stiahneme batch
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                    list(executor.map(self._fetch_and_save, batch))
                
                # Aktualizujeme progress
                processed += len(batch)
                last_id = batch[-1]
                
                analysis.repair_progress_id = last_id
                analysis.repaired_count += self.batch_stats['repaired']
                analysis.skipped_count += self.batch_stats['skipped']
                analysis.error_count += self.batch_stats['errors']
                # Assigned *before* the save, not after it: this save is what
                # writes the column, so a reason set afterwards would sit in
                # memory while the row kept the old one. The same mistake is
                # recorded on `SyncProgress.record_progress`.
                if self.recent_errors:
                    analysis.last_error = '\n'.join(self.recent_errors)
                analysis.save()

                # Progress výstup
                elapsed = time.time() - start_time
                rate = processed / (elapsed / 3600) if elapsed > 0 else 0
                pct = (processed / len(missing_ids)) * 100

                self.stdout.write(
                    f'[{pct:5.1f}%] {processed:,}/{len(missing_ids):,} | '
                    f'ID {last_id:,} | '
                    f'+{self.batch_stats["repaired"]} | '
                    f'skip {self.batch_stats["skipped"]} | '
                    f'err {self.batch_stats["errors"]} | '
                    f'{int(rate):,}/hod'
                )
                
                # Krátka pauza medzi batch-mi
                time.sleep(0.1)
            
            # Hotovo
            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()
            
            elapsed = time.time() - start_time
            self.stdout.write(self.style.SUCCESS(
                f'\n=== OPRAVA DOKONČENÁ za {elapsed/60:.1f} min ===\n'
                f'Opravených (nových firiem): {analysis.repaired_count:,}\n'
                f'Preskočených (404/deleted): {analysis.skipped_count:,}\n'
                f'Chýb: {analysis.error_count:,}'
            ))
            if analysis.error_count:
                self.stdout.write(self.style.ERROR(
                    f'Dôvody chýb sú v `SyncGapAnalysis(id={analysis.pk}).last_error`.'
                ))
            if owns_job_lifecycle:
                # Only when this run holds the job itself; a Celery dispatch
                # owns the status of the row it handed down. See
                # `set_job_outcome` for why the counters are a separate writer.
                complete_job(job)

        except KeyboardInterrupt:
            if owns_job_lifecycle:
                # `paused`, not `completed`. The command catches the interrupt
                # and returns normally, so nothing else would mark this job --
                # and this is exactly the run the message below tells the
                # operator to resume. A paused row releases `ruz:global`: the
                # partial unique index holds the slot only for `queued` and
                # `running`.
                pause_job(job, reason="Interrupted by operator (Ctrl+C)")
            self.stdout.write(self.style.WARNING(
                f'\nPrerušené na ID {analysis.repair_progress_id:,}. '
                f'Pokračujte: python manage.py repair_ruz_gaps --resume'
            ))

        except Exception as e:
            if owns_job_lifecycle:
                # Before the `analysis.save()` below, not after it. This handler
                # runs because the run just died, most likely on the database,
                # and the write that records the failure is then the write most
                # likely to raise again -- if it did, the exception would leave
                # this handler with `fail_job` never called, and the claimed row
                # would sit `running`, holding `ruz:global` until the watchdog
                # reaped it. Freeing the slot must not depend on a write that can
                # fail.
                fail_job(job, error=f"{type(e).__name__}: {e}")
            analysis.status = 'failed'
            analysis.last_error = str(e)
            analysis.save()
            raise

        finally:
            # Every exit path, so a completed job never reads as one that did
            # nothing -- see `sync_engine.set_job_outcome`.
            if sync_job_id is not None:
                set_job_outcome(
                    sync_job_id,
                    processed=(
                        analysis.repaired_count - baseline[0]
                        + analysis.skipped_count - baseline[1]
                        + analysis.error_count - baseline[2]
                    ),
                    succeeded=analysis.repaired_count - baseline[0],
                    skipped=analysis.skipped_count - baseline[1],
                    failed=analysis.error_count - baseline[2],
                )

    def _count_error(self, ruz_id, reason):
        """Count one failure and keep its reason.

        The old handler counted and threw the exception away: `except Exception
        as e:` incremented a counter and never read `e`, and the module did not
        import `logging` at all. A run whose every write was refused therefore
        ended `completed`, durably, with a number and no cause anywhere.
        """
        logger.error("Gap repair failed for RUZ id %s: %s", ruz_id, reason)
        with self.lock:
            self.batch_stats['errors'] += 1
            self.recent_errors.append(f"{ruz_id}: {reason}")
            del self.recent_errors[:-ERRORS_KEPT]

    def _fetch_and_save(self, ruz_id):
        """Stiahne a uloží jednu firmu podľa RUZ ID (thread-safe)."""
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

            # The walk's writer, not a private `defaults` dict. The comment that
            # used to sit on the `else` below -- "Existujúca firma s iným RUZ ID
            # - aktualizujeme" -- was this defect written down as the design: an
            # existing row with a *different* ruz_id was not the same company
            # being updated, it was another entity taking the row over. Keyed on
            # `ruz_id` that cannot happen; a second entity under a held IČO is
            # refused instead, and lands in the error counter.
            outcome, reason = self.writer.store(ruz_id, details)
        except Exception as e:
            self._count_error(ruz_id, f"{type(e).__name__}: {e}")
            return

        with self.lock:
            if outcome in (CREATED, UPDATED):
                # `repaired` covers both, and honestly: a gap id is by
                # construction absent from `Company`, so a create is the normal
                # case -- an update happens when the record belongs to an entity
                # the gap analysis does not see, i.e. an `IndividualEntity`.
                self.batch_stats['repaired'] += 1
            elif outcome is SKIPPED:
                self.batch_stats['skipped'] += 1

        if outcome is REFUSED:
            self._count_error(ruz_id, reason)
