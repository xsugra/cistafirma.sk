from celery import shared_task
from django.db.models import Q
from django.core.management import call_command
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
import logging

from .scrapers.vszp_debt import check_vszp_debt_get
from .scrapers.soc_poist_debt import check_socpoist_debt
from .scrapers.orsr_scraper import OrsrScraperError
from .integrations.ruz_api import RuzApi
from .services.orsr_sync import OrsrSyncService
from .services.ruz_financials_sync import RuzFinancialsSyncService
from .eligibility import ORSR_ELIGIBLE_LEGAL_FORMS, is_orsr_eligible_company
from companies.models import Company

logger = logging.getLogger(__name__)


@shared_task(queue='ruz_full')
def fetch_ruz_data_task():
    """
    Celery task to fetch company data from the RUZ API.
    Runs on ruz_full/celery queue in its own worker deployment.
    Automatically resumes from last position if sync was interrupted.
    """
    from registers.models import SyncProgress
    
    logger.info("Starting RUZ data fetch...")
    
    # Skontrolujeme či existuje pozastavená synchronizácia
    progress = SyncProgress.objects.filter(
        sync_type='full',
        status__in=['paused', 'failed']
    ).first()
    
    if progress:
        logger.info(f"Found paused sync at RUZ ID {progress.last_processed_ruz_id}, resuming...")
        call_command('fetch_ruz_data', '--resume')
    else:
        call_command('fetch_ruz_data')
    
    logger.info("RUZ data fetch completed.")


# Obmedzenie na 20 requestov za minútu, 3 pokusy s odkladom 1 minúta
# Beží na insurance queue (samostatný worker, rate-limited aby sa vyhlo banu).
@shared_task(queue='insurance', rate_limit='20/m', max_retries=3, default_retry_delay=60)
def update_insurance_debt(company_id: int):
    """
    Stiahne a aktualizuje dlhy pre jednu konkretnu firmu.
    """
    try:
        company = Company.objects.get(id=company_id)
        logger.info(f"Spustam kontrolu dlhov pre {company.nazov_UJ} (ICO: {company.ico})")

        # Ziskanie dat zo scraperov
        # Pridame error handling, ak scraper vrati None
        debt_vszp = check_vszp_debt_get(company.ico)
        debt_soc_poist = check_socpoist_debt(company.ico)

        # Aktualizacia databazy
        update_fields = []
        if debt_vszp is not None:
            company.debt_vszp = debt_vszp
            update_fields.append('debt_vszp')

        if debt_soc_poist is not None:
            company.debt_soc_poist = debt_soc_poist
            update_fields.append('debt_soc_poist')

        company.last_insurance_debt = timezone.now()
        update_fields.append('last_insurance_debt')

        # Ulozime iba zmenene polia pre efektivitu
        if update_fields:
            company.save(update_fields=update_fields)
            logger.info(f"Uspesne aktualizovane dlhy z poistovni pre {company.nazov_UJ}.")


    except Company.DoesNotExist:
        logger.error(f"Firma s ID {company_id} nebola nájdená.")
    except Exception as e:
        logger.error(f"Neočakávaná chyba pri aktualizácii dlhov pre firmu ID {company_id}: {e}")
        # Celery sa pokusi ulohu zopakovat vdaka @shared_task
        raise e

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


@shared_task(queue='celery', max_retries=3, default_retry_delay=30)
def sync_single_company_from_ruz(ico: str):
    """
    Synchronizuje jednu firmu z RUZ API podľa IČO.
    Ak firma neexistuje v DB, vytvorí ju. Ak existuje, aktualizuje ju.
    
    Používa priame vyhľadávanie podľa IČO cez RUZ API parameter.
    """
    logger.info(f"Spúšťam sync z RUZ pre IČO: {ico}")
    
    # Sanitizácia IČO
    ico = ico.strip().zfill(8)
    
    api = RuzApi()
    
    # Skúsime nájsť firmu v DB
    existing_company = Company.objects.filter(ico=ico).first()
    
    if existing_company and existing_company.ruz_id:
        # Máme RUZ ID, môžeme priamo získať detaily
        logger.info(f"Firma {ico} existuje, RUZ ID: {existing_company.ruz_id}")
        details = api.get_company_details(existing_company.ruz_id)
        
        if details:
            company = _update_company_from_ruz_data(details)
            if company:
                if is_orsr_eligible_company(company):
                    sync_company_orsr_data.delay(company.id)
                sync_company_financials_from_ruz.delay(company.id)
            logger.info(f"Firma {ico} úspešne aktualizovaná z RUZ.")
            return f"Aktualizovaná firma {ico}"
        else:
            logger.warning(f"Nepodarilo sa získať detaily pre RUZ ID {existing_company.ruz_id}")
            return f"Nepodarilo sa aktualizovať firmu {ico}"
    
    # Firma neexistuje alebo nemá RUZ ID - vyhľadáme priamo podľa IČO
    logger.info(f"Hľadám firmu {ico} v RUZ API...")
    
    # Použijeme novú metódu pre priame vyhľadávanie podľa IČO
    details = api.get_company_by_ico(ico)
    
    if details:
        company = _update_company_from_ruz_data(details)
        if company:
            if is_orsr_eligible_company(company):
                sync_company_orsr_data.delay(company.id)
            sync_company_financials_from_ruz.delay(company.id)
            logger.info(f"Firma {ico} úspešne importovaná z RUZ (RUZ ID: {company.ruz_id})")
            return f"Importovaná firma {ico}"
    
    logger.warning(f"Firma s IČO {ico} nebola nájdená v RUZ API.")
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


@shared_task(queue='ruz_full')
def start_full_ruz_sync(reset=False):
    """
    Celery task to start a new full RUZ sync.
    
    Args:
        reset: If True, resets progress and starts from beginning.
    """
    logger.info("Starting new full RUZ sync...")
    
    if reset:
        call_command('fetch_ruz_data', '--full-resync', '--reset')
    else:
        call_command('fetch_ruz_data', '--full-resync')
    
    return "Full sync started"


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


@shared_task(queue='ruz_full')
def start_incremental_sync():
    """
    Celery task na spustenie inkrementálnej synchronizácie.
    Stiahne len firmy zmenené od posledného syncu.
    """
    logger.info("Starting incremental RUZ sync...")
    call_command('fetch_ruz_data')
    return "Incremental sync completed"


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


@shared_task(queue='orsr', rate_limit='15/m', max_retries=2, default_retry_delay=60)
def sync_company_orsr_data(company_id: int):
    """Stiahne ORSR profil pre jednu firmu podľa IČO."""
    try:
        company = Company.objects.get(id=company_id)
        if not is_orsr_eligible_company(company):
            logger.info(
                "ORSR sync skipped for company_id=%s ico=%s legal_form=%s",
                company_id,
                company.ico,
                company.pravna_forma,
            )
            return f"ORSR sync skipped for {company.ico}"
        service = OrsrSyncService()
        profile = service.sync_company(company)
        logger.info(
            "ORSR sync OK for company_id=%s ico=%s oddiel=%s vlozka=%s",
            company_id,
            company.ico,
            profile.oddiel,
            profile.vlozka_cislo,
        )
        return f"ORSR sync OK for {company.ico}"
    except Company.DoesNotExist:
        logger.warning("ORSR sync skipped, company does not exist: id=%s", company_id)
        return f"Company {company_id} does not exist"
    except OrsrScraperError as exc:
        logger.warning("ORSR sync failed for company_id=%s: %s", company_id, exc)
        raise


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


@shared_task(queue='financials', rate_limit='20/m', max_retries=2, default_retry_delay=60)
def sync_company_financials_from_ruz(company_id: int):
    """Stiahne a uloží hospodárske výsledky firmy z RUZ API."""
    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        logger.warning("RUZ financial sync skipped, company does not exist: id=%s", company_id)
        return f"Company {company_id} does not exist"

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
def sync_company_now(company_id: int):
    """Spustí kompletný sync jednej firmy: RUZ, ORSR, financials a poisťovne."""
    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        logger.warning("Full company sync skipped, company does not exist: id=%s", company_id)
        return f"Company {company_id} does not exist"

    sync_single_company_from_ruz.delay(company.ico)
    if is_orsr_eligible_company(company):
        sync_company_orsr_data.delay(company.id)
    sync_company_financials_from_ruz.delay(company.id)
    update_insurance_debt.delay(company.id)
    logger.info("Scheduled full sync for company_id=%s ico=%s", company_id, company.ico)
    return f"Scheduled full sync for {company.ico}"


