from celery import shared_task, chain, chord, group
from django.db.models import Q
from django.db import transaction
from django.core.management import call_command
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
import logging

from .scrapers.vszp_debt import check_vszp_debt_get
from .scrapers.soc_poist_debt import check_socpoist_debt
from .integrations.ruz_api import RuzApi
from .services.rpo_sync import RpoSyncService
from .services.ruz_financials_sync import RuzFinancialsSyncService
from .eligibility import ORSR_ELIGIBLE_LEGAL_FORMS, is_orsr_eligible_company
from companies.models import Company, normalize_legal_form_code
from core.task_utils import BaseSyncTask
from .services.sync_engine import (
    claim_ruz_job,
    complete_job,
    detect_and_fail_stuck_jobs,
    enqueue_ruz_job,
    fail_job,
    update_company_status,
)

logger = logging.getLogger(__name__)


def _run_ruz_command(
    *,
    sync_job_id: int | None,
    job_type: str,
    command_args: list[str],
    celery_task_id: str = "",
):
    """Claim the global RUZ job before any command can write company data."""
    if sync_job_id is None:
        job, created = enqueue_ruz_job(
            job_type=job_type,
            parameters={"command_args": command_args},
            triggered_via="beat_schedule",
        )
        if not created and job.status == "running":
            logger.info("RUZ job #%s is already running; duplicate trigger ignored.", job.pk)
            return f"RUZ job #{job.pk} already running"
        sync_job_id = job.pk

    job = claim_ruz_job(sync_job_id, celery_task_id=celery_task_id)
    if job is None:
        logger.info("RUZ job #%s was already claimed or is no longer runnable.", sync_job_id)
        return f"RUZ job #{sync_job_id} not runnable"

    try:
        call_command("fetch_ruz_data", *command_args, sync_job_id=job.pk)
    except Exception as exc:
        fail_job(job, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        complete_job(job)
        return f"RUZ job #{job.pk} completed"


@shared_task(bind=True, queue='ruz_full')
def fetch_ruz_data_task(self, sync_job_id: int | None = None):
    """
    Celery task to fetch company data from the RUZ API.
    Runs on ruz_full/celery queue in its own worker deployment.
    Automatically resumes from last position if sync was interrupted.
    """
    logger.info("Starting RUZ data fetch...")
    result = _run_ruz_command(
        sync_job_id=sync_job_id,
        job_type="ruz_incremental",
        command_args=[],
        celery_task_id=self.request.id,
    )
    logger.info("RUZ data fetch completed.")
    return result


@shared_task(bind=True, queue='ruz_full')
def fetch_ruz_data_firmy_only(self, sync_job_id: int | None = None):
    """
    Celery task to fetch ONLY company (Firmy) data from the RUZ API.
    Filters out SZCO (self-employed, legal forms 100-110).
    Runs on ruz_full queue.
    """
    logger.info("Starting RUZ data fetch for Firmy only (excluding SZCO)...")
    result = _run_ruz_command(
        sync_job_id=sync_job_id,
        job_type="ruz_full_firmy",
        command_args=["--full-resync", "--entity-type", "companies"],
        celery_task_id=self.request.id,
    )
    logger.info("RUZ data fetch for Firmy completed.")
    return result


@shared_task(bind=True, queue='ruz_full')
def fetch_ruz_data_szco_only(self, sync_job_id: int | None = None):
    """
    Celery task to fetch ONLY SZCO (self-employed) data from the RUZ API.
    Only processes legal forms 100-110.
    Runs on ruz_full queue.
    """
    logger.info("Starting RUZ data fetch for SZCO only...")
    result = _run_ruz_command(
        sync_job_id=sync_job_id,
        job_type="ruz_full_szco",
        command_args=["--full-resync", "--entity-type", "individuals"],
        celery_task_id=self.request.id,
    )
    logger.info("RUZ data fetch for SZCO completed.")
    return result


@shared_task(base=BaseSyncTask, queue='insurance', rate_limit='20/m')
def update_insurance_debt(company_id: int):
    company = Company.objects.get(id=company_id)

    vszp_result = check_vszp_debt_get(company.ico)
    social_result = check_socpoist_debt(company.ico)

    with transaction.atomic():
        company = Company.objects.select_for_update().get(id=company_id)
        old_vszp = float(company.debt_vszp or 0)
        old_soc = float(company.debt_soc_poist or 0)

        results = {
            "vszp": ("debt_vszp", vszp_result),
            "social": ("debt_soc_poist", social_result),
        }
        update_fields = []
        for source, (field_name, result) in results.items():
            update_company_status(
                company_id=company.id,
                source=source,
                success=result.is_authoritative,
                error=result.error,
                error_type=result.error_type,
            )
            if result.is_authoritative:
                setattr(company, field_name, result.amount)
                update_fields.append(field_name)

        if vszp_result.is_authoritative and social_result.is_authoritative:
            company.last_insurance_debt = timezone.now()
            update_fields.append("last_insurance_debt")

        if update_fields:
            company.save(update_fields=update_fields)

    new_vszp = float(company.debt_vszp or 0)
    new_soc = float(company.debt_soc_poist or 0)
    changes = {}
    if old_vszp != new_vszp:
        changes["vszp"] = {"old": old_vszp, "new": new_vszp}
    if old_soc != new_soc:
        changes["soc_poist"] = {"old": old_soc, "new": new_soc}
    if changes:
        try:
            from notifications.services import create_debt_change_event
            create_debt_change_event(
                company_id=company.id,
                company_ico=company.ico,
                company_name=company.nazov_UJ,
                changes=changes,
            )
        except Exception:
            # The debt itself is already saved above; only the notification is
            # lost. That makes this survivable, not silent -- a swallowed failure
            # here is indistinguishable from a company nobody watches, so it is
            # logged as an error with the traceback rather than a warning.
            logger.error(
                "Failed to create debt change notifications for %s",
                company.ico,
                exc_info=True,
            )

    logger.info(
        "Insurance debt check finished for %s (ICO: %s, VSZP=%s, social=%s)",
        company.nazov_UJ,
        company.ico,
        vszp_result.state,
        social_result.state,
    )

@shared_task(queue='insurance')
def schedule_insurance_debt_checks():
    """
    Naplanuje kontrolu dlhov pre vsetky firmy, ktore neboli skontrolovane za poslednych 12 hodin.
    """

    # Vypocitame casovy limit 12hod dozadu
    time_threshold = timezone.now() - timedelta(hours=12)

    # Ziskanie firiem, ktore mali kontrolu naposledy pred limitom, alebo neboli kontrolovane nikdy (null)
    companies_to_check = Company.objects.filter(
        Q(last_insurance_debt__lte=time_threshold) | Q(last_insurance_debt__isnull=True)
    )

    count = companies_to_check.count()
    logger.info(f"Plánujem kontrolu dlhov pre {count} firiem.")

    # Pre kazdu firmu naplanujeme samostatnu robotnicku ulohu cez celery
    for company in companies_to_check:
        update_insurance_debt.delay(company.id)

    logger.info(f"Všetkých {count} úloh na kontrolu dlhov v poisťovniach bolo naplánovaných.")


@shared_task(queue='insurance')
def force_check_all_companies_debts():
    """
    Manuálne spustí kontrolu dlhov pre VŠETKY firmy v databáze,
    bez ohľadu na to, kedy boli naposledy kontrolované.
    """
    # Získame ID všetkých firiem, je to pamäťovo efektívnejšie
    company_ids = list(Company.objects.values_list('id', flat=True))
    count = len(company_ids)
    
    logger.info(f"Manuálny trigger: Plánujem kontrolu dlhov pre všetkých {count} firiem.")

    for company_id in company_ids:
        update_insurance_debt.delay(company_id)

    logger.info(f"Manuálny trigger: Všetkých {count} úloh na kontrolu dlhov bolo naplánovaných.")
    return f"Naplánovaná kontrola pre {count} firiem."

@shared_task(queue='celery')
def update_fs_data_task():
    """
    Celery task to trigger the update_fs_data management command.
    Runs on ruz_full/celery queue in its own worker deployment.
    """
    logger.info("Triggering update_fs_data command...")
    call_command('update_fs_data')
    logger.info("update_fs_data command finished.")


@shared_task(base=BaseSyncTask, queue='celery')
def sync_single_company_from_ruz(ico: str):
    """
    Synchronizuje jednu firmu z RUZ API podľa IČO.
    Ak firma neexistuje v DB, vytvorí ju. Ak existuje, aktualizuje ju.
    Neodpaľuje ďalšie tasky — to robí orchestrátor.
    """
    ico = ico.strip().zfill(8)
    api = RuzApi()

    existing_company = Company.objects.filter(ico=ico).first()

    if existing_company and existing_company.ruz_id:
        details = api.get_company_details(existing_company.ruz_id)
        if details:
            _update_company_from_ruz_data(details)
            logger.info("Firma %s aktualizovana z RUZ.", ico)
            return f"Aktualizovaná firma {ico}"
        logger.warning("Nepodarilo sa ziskat detaily pre RUZ ID %s", existing_company.ruz_id)
        return f"Nepodarilo sa aktualizovať firmu {ico}"

    details = api.get_company_by_ico(ico)
    if details:
        company = _update_company_from_ruz_data(details)
        if company:
            logger.info("Firma %s importovana z RUZ (RUZ ID: %s)", ico, company.ruz_id)
            return f"Importovaná firma {ico}"

    logger.warning("Firma s ICO %s nebola najdena v RUZ API.", ico)
    return f"Firma {ico} nebola nájdená v RUZ"


def _update_company_from_ruz_data(data: dict):
    """
    Pomocná funkcia pre aktualizáciu/vytvorenie firmy z RUZ dát.
    Replikuje logiku z fetch_ruz_data management command.
    """
    if 'ico' not in data:
        logger.warning(f"Preskakujem záznam s RUZ ID {data.get('id')} - chýba IČO.")
        return None
    
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
        'pravna_forma': normalize_legal_form_code(data.get('pravnaForma')),
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
    
    action = "Vytvorená" if created else "Aktualizovaná"
    logger.info(f"{action} firma: {company.nazov_UJ} (IČO: {company.ico})")
    
    return company


@shared_task(queue='celery')
def search_and_add_company_by_ico(ico: str):
    """
    Vyhľadá firmu podľa IČO v RUZ API pomocou alternatívneho prístupu.
    Používa sa pre manuálne pridávanie firiem z admin rozhrania.
    """
    return sync_single_company_from_ruz(ico)

@shared_task(queue='ruz_full')
def resume_full_ruz_sync():
    """
    Celery task to resume a paused or failed full RUZ sync.
    Can be triggered manually from admin or scheduled.
    """
    from registers.models import SyncProgress
    
    progress = SyncProgress.objects.filter(
        sync_type='full',
        status__in=['paused', 'failed']
    ).first()
    
    if not progress:
        logger.info("No paused sync found. Nothing to resume.")
        return "No sync to resume"
    
    logger.info(f"Resuming full sync from RUZ ID {progress.last_processed_ruz_id}...")
    call_command('fetch_ruz_data', '--resume')
    
    return f"Resumed sync from RUZ ID {progress.last_processed_ruz_id}"


@shared_task(bind=True, queue='ruz_full')
def start_full_ruz_sync(self, reset=False, sync_job_id: int | None = None):
    """
    Celery task to start a new full RUZ sync.
    
    Args:
        reset: If True, resets progress and starts from beginning.
    """
    args = ["--full-resync"]
    if reset:
        args.append("--reset")
    return _run_ruz_command(
        sync_job_id=sync_job_id,
        job_type="ruz_full",
        command_args=args,
        celery_task_id=self.request.id,
    )


@shared_task(queue='ruz_full', time_limit=86400)  # 24h limit
def start_full_ruz_sync_from_id(start_id: int):
    """
    Celery task na spustenie Full Sync od konkrétneho RUZ ID.
    Užitočné pre opätovné spustenie od určitého bodu.
    
    Args:
        start_id: RUZ ID od ktorého začať synchronizáciu.
    """
    from registers.models import SyncProgress
    
    logger.info(f"Starting full RUZ sync from ID {start_id}...")
    
    # Nájdeme alebo vytvoríme full sync progress
    progress, created = SyncProgress.objects.get_or_create(
        sync_type='full',
        defaults={'status': 'idle'}
    )
    
    # Nastavíme štartovacie ID
    progress.last_processed_ruz_id = start_id - 1  # -1 lebo pokračuje ZA týmto ID
    progress.status = 'paused'
    progress.save()
    
    # Spustíme --resume ktorý pokračuje od last_processed_ruz_id
    call_command('fetch_ruz_data', '--resume')
    
    return f"Full sync from ID {start_id} started"


@shared_task(bind=True, queue='ruz_full')
def start_incremental_sync(self, sync_job_id: int | None = None):
    """
    Celery task na spustenie inkrementálnej synchronizácie.
    Stiahne len firmy zmenené od posledného syncu.
    """
    return _run_ruz_command(
        sync_job_id=sync_job_id,
        job_type="ruz_incremental",
        command_args=[],
        celery_task_id=self.request.id,
    )


@shared_task(queue='ruz_full', time_limit=86400)  # 24h limit
def start_repair_sync(start_id=None, workers=3):
    """
    Celery task na spustenie repair synchronizácie.
    Prejde všetky RUZ ID a stiahne chýbajúce firmy.
    
    Args:
        start_id: Od ktorého RUZ ID začať (None = pokračovať kde sa skončilo)
        workers: Počet paralelných workerov
    """
    logger.info(f"Starting repair sync (start_id={start_id}, workers={workers})...")
    
    args = ['repair_ruz_sync_v2', f'--workers={workers}']
    if start_id is not None:
        args.append(f'--start-id={start_id}')
    
    call_command(*args)
    return "Repair sync completed"


@shared_task(queue='ruz_full')
def resume_repair_sync(workers=3):
    """
    Celery task na pokračovanie pozastavenej repair synchronizácie.
    """
    from registers.models import SyncProgress
    
    progress = SyncProgress.objects.filter(
        sync_type='repair',
        status__in=['paused', 'failed']
    ).first()
    
    if not progress:
        logger.info("No paused repair sync found.")
        return "No repair sync to resume"
    
    logger.info(f"Resuming repair sync from RUZ ID {progress.last_processed_ruz_id}...")
    call_command('repair_ruz_sync_v2', f'--workers={workers}')
    
    return f"Resumed repair sync from RUZ ID {progress.last_processed_ruz_id}"


# === GAP ANALYSIS TASKS ===

@shared_task(queue='ruz_full', time_limit=3600)  # 1h limit
def analyze_ruz_gaps(expected_max=None):
    """
    Celery task na analýzu dier v RUZ ID.
    Nájde chýbajúce záznamy v databáze.
    
    Args:
        expected_max: Očakávané maximálne RUZ ID (voliteľné)
    """
    logger.info("Starting RUZ gap analysis...")
    
    args = ['analyze_ruz_gaps']
    if expected_max:
        args.append(f'--expected-max={expected_max}')
    
    call_command(*args)
    
    from registers.models import SyncGapAnalysis
    latest = SyncGapAnalysis.objects.order_by('-created_at').first()
    
    if latest:
        return f"Analysis completed: {latest.total_missing:,} missing IDs in {latest.total_gaps} gaps"
    return "Analysis completed"


@shared_task(queue='ruz_full', time_limit=86400)  # 24h limit
def repair_ruz_gaps(analysis_id=None, workers=5, resume=False):
    """
    Celery task na opravu chýbajúcich RUZ záznamov podľa analýzy.
    
    Args:
        analysis_id: ID analýzy (SyncGapAnalysis). Ak None, použije poslednú.
        workers: Počet paralelných workerov.
        resume: Ak True, pokračuje od posledného opravenéha ID.
    """
    logger.info(f"Starting RUZ gap repair (analysis_id={analysis_id}, workers={workers}, resume={resume})...")
    
    args = ['repair_ruz_gaps', f'--workers={workers}']
    if analysis_id:
        args.append(f'--analysis-id={analysis_id}')
    if resume:
        args.append('--resume')
    
    call_command(*args)
    return "Gap repair completed"


@shared_task(queue='ruz_full')
def resume_gap_repair(workers=5):
    """
    Celery task na pokračovanie pozastavenej opravy dier.
    """
    from registers.models import SyncGapAnalysis
    
    analysis = SyncGapAnalysis.objects.filter(
        status='repairing'
    ).order_by('-created_at').first()
    
    if not analysis:
        logger.info("No paused gap repair found.")
        return "No gap repair to resume"
    
    logger.info(f"Resuming gap repair from ID {analysis.repair_progress_id}...")
    call_command('repair_ruz_gaps', f'--analysis-id={analysis.id}', '--resume', '--workers=5')
    
    return f"Resumed gap repair from ID {analysis.repair_progress_id}"


@shared_task(base=BaseSyncTask, queue='orsr', rate_limit='15/m')
def sync_company_orsr_data(company_id: int):
    company = Company.objects.get(id=company_id)
    if not is_orsr_eligible_company(company):
        logger.info("ORSR sync skipped for company_id=%s ico=%s", company_id, company.ico)
        return f"ORSR sync skipped for {company.ico}"

    # Capture old executive names for change detection
    old_names: list[str] = []
    try:
        old_profile = company.orsr_profile
    except Exception:
        old_profile = None
    if old_profile:
        from notifications.services import _extract_orsr_person_names
        old_names = _extract_orsr_person_names(old_profile)

    service = RpoSyncService()
    profile = service.sync_company(company)
    logger.info("Company profile sync OK for company_id=%s ico=%s", company_id, company.ico)

    # Detect executive changes after sync
    try:
        from notifications.services import _extract_orsr_person_names, detect_executive_changes
        new_names = _extract_orsr_person_names(profile)
        if old_names or new_names:
            created = detect_executive_changes(
                company_ico=company.ico,
                company_name=company.nazov_UJ,
                old_names=old_names,
                new_names=new_names,
            )
            if created:
                logger.info("Created %d executive change notifications for %s", created, company.ico)
    except Exception as e:
        logger.warning("Failed to detect executive changes for %s: %s", company.ico, e)

    return f"Company profile sync OK for {company.ico}"


@shared_task(queue='orsr')
def schedule_missing_orsr_sync(limit: int = 200):
    """Naplánuje ORSR sync pre firmy, ktoré ešte nemajú ORSR profil."""
    company_ids = list(
        Company.objects.filter(
            orsr_profile__isnull=True,
            pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
            datum_zrusenia__isnull=True,
        )
        .order_by('id')
        .values_list('id', flat=True)[:limit]
    )
    for company_id in company_ids:
        sync_company_orsr_data.delay(company_id)

    logger.info("Scheduled ORSR sync for %s companies", len(company_ids))
    return f"Scheduled ORSR sync for {len(company_ids)} companies"


@shared_task(base=BaseSyncTask, queue='financials', rate_limit='20/m')
def sync_company_financials_from_ruz(company_id: int):
    company = Company.objects.get(id=company_id)
    service = RuzFinancialsSyncService()
    upserts = service.sync_company(company)
    logger.info("RUZ financial sync company_id=%s ico=%s rows=%s", company_id, company.ico, upserts)
    return f"RUZ financial sync finished for {company.ico}, rows={upserts}"


@shared_task(queue='financials')
def schedule_ruz_financials_sync(limit: int = 200, eligible_only: bool = False, missing_only: bool = False):
    """Naplánuje RUZ financial sync pre dávku firiem."""
    qs = Company.objects.order_by('id')

    if eligible_only:
        qs = qs.filter(
            pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
            datum_zrusenia__isnull=True,
        )

    if missing_only:
        qs = qs.filter(financial_results__isnull=True)

    company_ids = list(qs.values_list('id', flat=True)[:limit])
    for company_id in company_ids:
        sync_company_financials_from_ruz.delay(company_id)
    logger.info("Scheduled RUZ financial sync for %s companies", len(company_ids))
    return f"Scheduled RUZ financial sync for {len(company_ids)} companies"


@shared_task(queue='celery')
def orchestrate_full_company_sync(company_id: int):
    """
    Hierarchicky sync jednej firmy:
    1. RUZ základné údaje
    2. Paralelne: RUZ financials + ORSR (ak eligible)
    3. Po dokončení oboch: kontrola dlhov v poisťovniach
    """
    company = Company.objects.get(id=company_id)

    parallel_tasks = [sync_company_financials_from_ruz.si(company.id)]
    if is_orsr_eligible_company(company):
        parallel_tasks.append(sync_company_orsr_data.si(company.id))

    workflow = chain(
        sync_single_company_from_ruz.si(company.ico),
        chord(group(parallel_tasks), update_insurance_debt.si(company.id)),
    )
    workflow.apply_async()
    logger.info("Orchestrated sync for company_id=%s ico=%s", company_id, company.ico)
    return f"Orchestrated sync for {company.ico}"


@shared_task(queue='celery')
def sync_company_now(company_id: int):
    """Backward-compatible wrapper — delegates to orchestrator."""
    orchestrate_full_company_sync.delay(company_id)
    return f"Delegated to orchestrator for company {company_id}"


@shared_task(queue='celery')
def compute_sector_benchmarks(year: int | None = None):
    """Compute sector benchmarks for financial indicators.

    Runs once daily via Celery Beat.
    """
    from companies.services.benchmarking import compute_sector_benchmarks as _compute
    result = _compute(year)
    return f"Sector benchmarks done: {result}"


@shared_task(queue='celery')
def detect_stuck_sync_jobs():
    """Fail sync jobs whose heartbeat has gone stale.

    The reaper itself always worked; nothing ever called it. A job whose worker
    died stayed `running` indefinitely -- job #3 sat that way for 15 days,
    counted as an active import by the admin dashboard, with no manual remedy
    (the API refuses cancel and resume for RUZ jobs by design).

    On the `celery` queue rather than `ruz_full`, so the reaper can never end up
    waiting behind the very backlog it is meant to notice.
    """
    flipped = detect_and_fail_stuck_jobs()
    if flipped:
        logger.warning("Watchdog failed %s stuck sync job(s).", flipped)
    else:
        logger.info("Watchdog found no stuck sync jobs.")
    return flipped
