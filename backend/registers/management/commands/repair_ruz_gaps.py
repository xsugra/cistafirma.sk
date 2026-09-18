from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone
from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import SyncGapAnalysis, SyncJob
from registers.services.sync_engine import set_job_outcome
import time
import concurrent.futures
import threading


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
        
        analysis.status = 'repairing'
        analysis.save()

        # Heartbeat for the job the caller claimed -- without it this run looks
        # dead to the watchdog and is reaped mid-repair. See `fetch_ruz_data`.
        job_row = (
            SyncJob.objects.filter(pk=options['sync_job_id']).first()
            if options.get('sync_job_id') else None
        )
        sync_job_id = job_row.pk if job_row is not None else None

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
            self.stdout.write(self.style.SUCCESS('Všetky ID už boli opravené!'))
            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()
            return
        
        self.stdout.write(f'Zostáva opraviť: {len(missing_ids):,} ID')
        self.stdout.write(f'Používam {num_workers} workerov...')
        
        processed = 0
        start_time = time.time()
        
        try:
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
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING(
                f'\nPrerušené na ID {analysis.repair_progress_id:,}. '
                f'Pokračujte: python manage.py repair_ruz_gaps --resume'
            ))
            
        except Exception as e:
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

    def _fetch_and_save(self, ruz_id):
        """Stiahne a uloží jednu firmu podľa RUZ ID (thread-safe)."""
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
                    self.batch_stats['repaired'] += 1
                else:
                    # Existujúca firma s iným RUZ ID - aktualizujeme
                    self.batch_stats['repaired'] += 1
                    
        except Exception as e:
            with self.lock:
                self.batch_stats['errors'] += 1
