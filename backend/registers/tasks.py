from celery import shared_task
from django.db.models import Q
from django.core.management import call_command
from django.utils import timezone
import logging

from .scrapers.vszp_debt import check_vszp_debt_get
from .scrapers.soc_poist_debt import check_socpoist_debt
from companies.models import Company

logger = logging.getLogger(__name__)

@shared_task
def fetch_ruz_data_task():
    """
    Celery task to fetch company data from the RUZ API.
    """
    call_command('fetch_ruz_data')

 # Obmedzenie na 1 request/s, 3 pokusy s odkladom 1 minúta
@shared_task(rate_limit='20/m', max_retries=3, default_retry_delay=60)
def update_insurance_debt(company_id: int):
    """
    Stiahne a aktualizuje dlhy pre jednu konkretnu firmu.
    """
    try:
        company = Company.objects.get(id=company_id)
        logger.info(f"Spustam kontrolu dlhov pre {company.nazovUJ} (ICO: {company.ico})")

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
            logger.info(f"Uspesne aktualizovane dlhy z poistovni pre {company.nazovUJ}.")


    except Company.DoesNotExist:
        logger.error(f"Firma s ID {company_id} nebola nájdená.")
    except Exception as e:
        logger.error(f"Neočakávaná chyba pri aktualizácii dlhov pre firmu ID {company_id}: {e}")
        # Celery sa pokusi ulohu zopakovat vdaka @shared_task
        raise e

@shared_task
def schedule_insurance_debt_checks():
    """
    Naplanuje kontrolu dlhov pre vsetky firmy, ktore neboli skontrolovane za poslednych 12 hodin.
    """

    # Vypocitame casovy limit 12hod dozadu
    time_threshold = timezone.now() - timezone.timedelta(hours=12)

    # Ziskanie firiem, ktore mali kontrolu naposledy pred limitom, alebo neboli kontrolovane nikdy (null)
    companies_to_check = Company.objects.filter(
        Q(last_insurance_debt__lte=time_threshold) | Q(last_insurance_debt__isnull=True)
    )

    # Pre kazdu firmu naplanujeme samostatnu robotnicku ulohu cez celery
    for company in companies_to_check:
        update_insurance_debt.delay(company.id)

    logger.info("Vsetky ulohy na kontrolu dlhov v poistovniach boli uspesne naplanovane.")


@shared_task
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

@shared_task
def update_fs_data_task():
    """
    Celery task to trigger the update_fs_data management command.
    """
    logger.info("Triggering update_fs_data command...")
    call_command('update_fs_data')
    logger.info("update_fs_data command finished.")