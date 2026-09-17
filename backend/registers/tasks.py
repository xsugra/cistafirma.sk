from celery import shared_task, chain, chord, group
from django.db.models import Count, Exists, F, OuterRef, Q
from django.db import transaction
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
import logging

from .scrapers.vszp_debt import check_vszp_debt_get
from .scrapers.soc_poist_debt import check_socpoist_debt
from .scrapers.debt_result import DebtCheckState
from .scrapers.orsr_scraper import OrsrScraperError
from .integrations.ruz_api import RuzApi, apply_ruz_dates
from .services.rpo_sync import RpoSyncService, pending_person_history
from .services.ruz_financials_sync import PARSER_REVISION, sync_company_and_record
from .eligibility import (
    ORSR_ELIGIBLE_LEGAL_FORMS,
    is_orsr_eligible_company,
    orsr_ineligibility_reason,
)
from companies.models import Company, Watchlist, normalize_legal_form_code
from core.task_utils import BaseSyncTask
from .models import CompanySyncStatus, OrsrCompanyProfile
from .services.sync_engine import (
    _env_int,
    claim_ruz_job,
    complete_job,
    detect_and_fail_stuck_jobs,
    enqueue_ruz_job,
    fail_job,
    record_orsr_failure,
    record_orsr_not_monitored,
    record_orsr_outcome,
    record_ruz_date_outcome,
    rotating_batch,
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

    # A source somebody blocked is not asked, and the answer already stored for
    # it stays as it was. Per source, not per company: blocking `vszp` says
    # nothing about `debt_soc_poist`, which is a different question with a
    # different answer, and freezing both would make the block a bigger hammer
    # than the one the admin picked up.
    #
    # Read before the requests, because this decides whether to make them.
    blocked = set(
        CompanySyncStatus.objects.filter(
            company_id=company_id, source__in=INSURANCE_SOURCES, is_blocked=True
        ).values_list("source", flat=True)
    )
    if blocked == set(INSURANCE_SOURCES):
        logger.info(
            "Kontrola dlhov pre %s (ICO: %s) preskočená -- oba zdroje sú "
            "manuálne zablokované.",
            company.nazov_UJ,
            company.ico,
        )
        return

    vszp_result = (
        None
        if CompanySyncStatus.SOURCE_VSZP in blocked
        else check_vszp_debt_get(company.ico)
    )
    social_result = (
        None
        if CompanySyncStatus.SOURCE_SOCIAL in blocked
        else check_socpoist_debt(company.ico)
    )

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
            if result is None:
                # Blocked: not attempted, so there is nothing to record about
                # this attempt and nothing to write over the stored answer.
                continue
            update_company_status(
                company_id=company.id,
                source=source,
                success=result.is_authoritative,
                error=result.error,
                error_type=result.error_type,
                # `None` where the attempt has nothing to say, which is every
                # state but `LISTED_NO_AMOUNT` -- the argument's own contract
                # is that `None` leaves a previous writer's sentence alone,
                # and neither of these two sources has another writer.
                detail=result.detail or None,
            )
            if result.is_authoritative:
                # For `LISTED_NO_AMOUNT` this writes `None`: the register
                # stopped publishing a sum for this company, so the one we
                # stored is no longer what it says. The listing itself is
                # recorded in the column below, not here.
                setattr(company, field_name, result.amount)
                update_fields.append(field_name)

        # The SP registry lists two kinds of entry and only one of them is
        # money. `debt_soc_poist` is NULL for both "owes nothing" and "listed
        # without a sum", so the second needs its own column or the company
        # page cannot tell them apart -- and it currently shows the second as
        # the first. Guarded on `is_authoritative` so that a network error
        # cannot clear a flag a previous attempt set from a page it did read.
        if social_result is not None and social_result.is_authoritative:
            listed = social_result.state is DebtCheckState.LISTED_NO_AMOUNT
            if company.social_listed_without_amount != listed:
                company.social_listed_without_amount = listed
                update_fields.append("social_listed_without_amount")

        # Advanced only when both sources were asked *and* both answered. A
        # blocked source was never asked, so it did not answer -- and this
        # timestamp is shown to readers as the date the debts were checked, so
        # it may not claim a check that did not happen. The cost is that a
        # company with one blocked source stays in the due set; the scheduler
        # above is what keeps it from being picked for ever.
        answered = [
            result for result in (vszp_result, social_result) if result is not None
        ]
        if len(answered) == len(INSURANCE_SOURCES) and all(
            result.is_authoritative for result in answered
        ):
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
        vszp_result.state if vszp_result is not None else "blocked",
        social_result.state if social_result is not None else "blocked",
    )

# `update_insurance_debt` drains at `rate_limit='20/m'`, so one 12-hour tick can
# absorb 20 * 60 * 12 = 14 400 tasks. The scheduler below enqueues no more.
#
# It previously enqueued the entire due population -- 439 817 companies on
# 2026-09-12 -- which the queue could never absorb. Measured that day: 5 108 434
# pending messages holding ~5 GB of Redis, the largest single consumer in the
# stack.
#
# The backlog was the least of it. **The scheduler ran on the same queue it
# floods**, so it waited behind its own backlog and then fired over and over:
# beat dispatched it at 07:50 and a worker first ran it after 11:00, after which
# it executed at 03:11, 04:17, 11:14, 11:49, 12:04, 13:55, 14:15, 14:19, 14:34,
# 14:39 and 14:53 -- roughly 8.4 million messages enqueued in one day against
# 14 400 drained. Each of those runs builds ~440 000 `delay()` calls, so with
# `--concurrency=2` the worker spent its time scheduling rather than checking:
# its last recorded attempt was 14:15 while it ran past 15:20.
#
# A scheduler must not share a queue with the work it schedules. This one no
# longer does -- but note **which layer decides that**. The admin-managed
# `PeriodicTask` row `schedule-insurance-debt-checks-every-12-hours` carries
# `queue = 'insurance'` explicitly, and with `DatabaseScheduler` that row is what
# runs: the `CELERY_TASK_ROUTES` entry below and the `options.queue` in
# `CELERY_BEAT_SCHEDULE` are both inert for this task while the row exists. All
# three are set to `celery` so they cannot disagree again, but the row is the one
# that has to be changed on a live system.
INSURANCE_RATE_PER_MINUTE = 20
INSURANCE_TICK_HOURS = 12
INSURANCE_BATCH_PER_TICK = INSURANCE_RATE_PER_MINUTE * 60 * INSURANCE_TICK_HOURS

# The two sources one insurance-debt check answers for, and the only two whose
# `CompanySyncStatus` rows this module reads or writes. Named here because
# three places need the same pair -- the selector, the block check and the
# "did both answer?" test -- and a tuple that drifts between them would be a
# silent hole rather than a mistake anyone notices.
INSURANCE_SOURCES = (
    CompanySyncStatus.SOURCE_VSZP,
    CompanySyncStatus.SOURCE_SOCIAL,
)


@shared_task(queue='celery')
def schedule_insurance_debt_checks(limit: int = INSURANCE_BATCH_PER_TICK):
    """Queue a bounded batch of insurance-debt checks for the companies that are due.

    Due means `last_insurance_debt` older than 12 hours, or never checked, *and*
    at least one of the two sources still open to us -- see the block below.
    The rotation that implies is unchanged: an attempt that both sources answer
    advances the timestamp, so the head of the queue moves on and a later tick
    cannot hand out the same companies again.

    What is new is `limit`. The batch is capped at what `update_insurance_debt`
    can drain before the next tick, so the queue stays bounded instead of
    growing without limit. It is a task argument rather than a constant so it
    can be retuned from the admin-managed `PeriodicTask` row without a deploy,
    the way `schedule_ruz_financials_sync` already carries `args: [2000]`.

    Ordering is `nulls_first`: never-checked companies come before the oldest
    checked ones. Postgres sorts NULLs *last* under a plain ascending order, so
    without it the 25 398 companies whose timestamp is merely stale would be
    re-chosen every tick while the 414 419 never-checked ones waited behind them
    for ever.

    **Watched companies are drawn first**, because the rotation is what makes
    "sledovať firmu" mean anything. The batch absorbs 14 400 of ~414 000
    never-checked companies per tick, so an unwatched company waits roughly a
    week for its first check -- and a watched one waited exactly as long, which
    made the watchlist a promise the rotation did not keep: `NotificationEvent`
    is only ever written for a company that has been checked twice, so the
    "Udalosti vo firme" section could not fill for any company a reader had
    actually asked about. Measured 2026-09-13: 6 companies watched, 0 of them
    ever checked, 0 events.

    They are capped at half the batch, and that cap is load-bearing. Watched
    companies are the *front* of the order, so without it a watchlist larger
    than `limit` would take every slot and the 414 419 never-checked companies
    the rotation exists to reach would stop advancing -- the same "looks alive
    and never progresses" defect this repository keeps finding, reintroduced
    through priority. Half is a judgement: enough that watching a company
    visibly works within a tick or two, bounded enough that the general
    population keeps moving. `max(1, ...)` keeps the guarantee true for a small
    `limit`, where `limit // 2` is 0 and watched companies would otherwise be
    excluded entirely.

    The cap is a *ceiling on the watched half*, not a reservation. If there is
    not enough other work to fill the batch, the remainder goes back to watched
    companies rather than dispatching a short batch -- a half-empty batch wastes
    drain capacity that `rate_limit` will not give back. That is not a corner
    case to shrug at: a caught-up rotation is the goal, and in that state the
    unwatched due set really can run dry.

    **`next_retry_at` is deliberately not read here**, although
    `update_company_status` writes it for these two sources. The backoff cannot
    fire on this path: `compute_next_retry` caps it at `MAX_BACKOFF_SECONDS`
    (24 h) while the rotation revisits a company about every 15 days -- 400 831
    never-checked companies at 14 400 per 12 h tick -- so by the time a row is
    looked at again its backoff has always expired. Measured on the live
    database 2026-09-15: of 54 486 `social` and 54 486 `vszp` rows, **0** had
    `next_retry_at` in the future, while `orsr` (8 055) and `financials`
    (10 340) did -- those rotations do come back within the day. Adding the
    filter would therefore exclude nothing, ever: the "control that looks
    configured and decides nothing" this repository keeps finding, built
    deliberately. What bounds this path is `rate_limit='20/m'` for the load it
    puts on the registers and the rotation for how often a company is asked.

    **`is_blocked` is read**, and it is the one thing here that was genuinely
    missing. Every other source is asked for work through
    `companies_due_for_sync`, which filters `is_blocked=False`; this batch
    selected on `Company.last_insurance_debt` alone, so a company an admin had
    blocked was still checked -- and because a blocked source is never
    attempted, its timestamp never advanced and it kept its slot, tick after
    tick, for ever. The rule is "an unblocked source, or no row at all": a
    company with no insurance row has simply never been checked and is due; a
    company whose every insurance row is blocked is not.
    """
    time_threshold = timezone.now() - timedelta(hours=12)

    # Which companies have *every* insurance source blocked, read as an indexed
    # query of its own rather than as a correlated `EXISTS` beside the scan.
    #
    # The two answer identically and do not cost identically. Measured on the
    # live database 2026-09-15, warm, with the real ordering and limit:
    #
    #     two correlated `EXISTS`   select 582-695 ms   due.count() 408-419 ms
    #     this list, then exclude   select 187-207 ms   due.count()  100-105 ms
    #     nothing at all            select 190-215 ms   due.count()  100-109 ms
    #
    # The filter is *free* this way -- the plan is the same `Parallel Seq Scan`
    # it is with no filter, because excluding an empty list costs nothing --
    # while the correlated form makes the planner estimate 4 001 250 where it
    # estimated 41 250 and drop parallel query altogether, on the one statement
    # the whole rotation runs. It is the estimate rather than the milliseconds
    # that decides it: 600 ms twice a day is nothing, but a 100x misestimate on
    # a table that only grows is a timeout waiting for enough companies.
    #
    # The rule is "every source is blocked", not "no source is unblocked". They
    # differ for a company that a `block_company` call gave a blocked `vszp` row
    # without ever giving it a `social` one -- the admin API writes a row per
    # source on demand, so that state is reachable, and the test suite pins it.
    # Under the second phrasing the missing `social` row would read as "nothing
    # to do there" and the company would never be asked about its
    # social-insurance debt at all; under this one it stays due, which is what
    # "never checked" means everywhere else in this module.
    #
    # `is_blocked` is indexed and only an admin API call blocks anything -- one
    # company, one source, per request (`adminapi/views/sync.py`) -- so this
    # returns a handful of ids, and 0 today. `exclude(pk__in=[])` is therefore
    # the ordinary case, not a corner: Django drops the clause and keeps every
    # row, which a test states outright, because an empty batch is the failure
    # that would matter. `order_by()` clears any ordering a future `Meta` might
    # add, so the `GROUP BY` stays `company_id` alone.
    fully_blocked_ids = list(
        CompanySyncStatus.objects.filter(
            source__in=INSURANCE_SOURCES, is_blocked=True
        )
        .values("company_id")
        .annotate(_sources=Count("source", distinct=True))
        .filter(_sources=len(INSURANCE_SOURCES))
        .order_by()
        .values_list("company_id", flat=True)
    )

    due = Company.objects.filter(
        Q(last_insurance_debt__lte=time_threshold)
        | Q(last_insurance_debt__isnull=True)
    ).exclude(pk__in=fully_blocked_ids)

    # One `EXISTS` subquery rather than a join through `watchers`: a company can
    # be on several watchlists, and a join would hand the same company to
    # `values_list` more than once. The annotation is also what lets the
    # unwatched half be one query instead of a `NOT IN` over every watched id.
    is_watched = Exists(Watchlist.objects.filter(company_id=OuterRef("pk")))
    order = (F("last_insurance_debt").asc(nulls_first=True), "id")

    watched_due = (
        due.annotate(_watched=is_watched).filter(_watched=True).order_by(*order)
    )
    watched_cap = max(1, limit // 2)
    watched_ids = list(
        watched_due.values_list("id", flat=True)[:watched_cap]
    )

    # Ids only, and only `limit` of them. Iterating the queryset itself would
    # materialise every due company as a full model instance -- 439 817 of them
    # at the time this was measured.
    unwatched_ids = list(
        due.annotate(_watched=is_watched)
        .filter(_watched=False)
        .order_by(*order)
        .values_list("id", flat=True)[: max(limit - len(watched_ids), 0)]
    )

    company_ids = watched_ids + unwatched_ids

    shortfall = limit - len(company_ids)
    if shortfall > 0:
        company_ids += list(
            watched_due.values_list("id", flat=True)[
                len(watched_ids) : len(watched_ids) + shortfall
            ]
        )

    logger.info(
        "Plánujem kontrolu dlhov pre %s z %s firiem, ktoré sú na rade "
        "(z toho %s sledovaných).",
        len(company_ids),
        due.count(),
        len(watched_ids),
    )

    for company_id in company_ids:
        update_insurance_debt.delay(company_id)

    logger.info("Naplánovaných %s kontrol dlhov v poisťovniach.", len(company_ids))
    return f"Scheduled {len(company_ids)} insurance debt checks"


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
    # Two forms, and they are not interchangeable. What the register wants as a
    # *query parameter* is zero-padded, and `get_company_id_by_ico` applies that
    # itself. What we store is the stripped value the register sent -- so
    # matching the local row with the padded form is what made a 6-digit IČO
    # unfindable even when we already held it, and sent the lookup to the
    # register to import a row we had. Padding outbound, strip locally.
    ico = ico.strip()
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
    # `.strip()` only, and the upsert keyed on `ruz_id` -- see
    # `fetch_ruz_data.update_or_create_company` for why both: `ico` is not the
    # register's identity (three entities answer to `00177474`), and keying on it
    # re-stamps another entity's row whenever the incoming `ruz_id` is not taken.
    ruz_id = data.get('id')
    ico = str(data.get('ico') or '').strip()
    if not ico:
        logger.warning(f"Preskakujem záznam s RUZ ID {ruz_id} - chýba IČO.")
        return None

    defaults = {
        'ruz_id': ruz_id,
        'ico': ico,
        'dic': data.get('dic'),
        'sid': data.get('sid'),
        'nazov_UJ': data.get('nazovUJ', ''),
        'mesto': data.get('mesto'),
        'ulica': data.get('ulica'),
        'psc': data.get('psc'),
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
    }

    # The three date fields go in together, and a field whose value we cannot
    # read is left out entirely -- `update_or_create` then keeps what is
    # stored instead of overwriting it with `None`. See `apply_ruz_dates`.
    refused_dates = apply_ruz_dates(defaults, data)

    # `update_or_create` discards the row it matched, so once the write lands
    # there is no way to tell whether the company was already dissolved. Read
    # the previous value first -- and only when the incoming record HAS a
    # dissolution date, which keeps this extra query off the common path.
    #
    # `.get`, not `[...]`: an unreadable `datumZrusenia` is left out of the
    # defaults, and nothing about the company's status is changing then --
    # which is exactly what a `None` here means to `detect_status_change`.
    new_zrusenie = defaults.get('datum_zrusenia')
    previous_zrusenie = None
    if new_zrusenie is not None:
        previous_zrusenie = (
            Company.objects.filter(ruz_id=ruz_id)
            .values_list('datum_zrusenia', flat=True)
            .first()
        )

    company, created = Company.objects.update_or_create(
        ruz_id=ruz_id,
        defaults=defaults
    )
    
    action = "Vytvorená" if created else "Aktualizovaná"
    logger.info(f"{action} firma: {company.nazov_UJ} (IČO: {company.ico})")
    
    # Only an existing company can have *become* dissolved -- one created here
    # already dissolved was never known to us as active.
    if not created:
        try:
            from notifications.services import detect_status_change
            detect_status_change(
                company_ico=company.ico,
                company_name=company.nazov_UJ,
                old_datum_zrusenia=previous_zrusenie,
                # `new_zrusenie`, not `company.datum_zrusenia`: the latter
                # reads the row back, so when `apply_ruz_dates` has just
                # declined to write an unreadable value it would hand
                # `detect_status_change` the *stored* date as though it were
                # new -- and the untouched date would be announced as a
                # dissolution.
                new_datum_zrusenia=new_zrusenie,
            )
        except Exception:
            logger.error("Failed to detect status change for %s", company.ico, exc_info=True)

    # One row per on-demand sync, carrying either the success or the refusal --
    # the same call the six-hourly command makes, so a refusal recorded by one
    # is cleared by the other. See `record_ruz_date_outcome`.
    record_ruz_date_outcome(company_id=company.id, refused=refused_dates)

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
        # The refusal has to be written down, not just returned. A due retry row
        # is drawn by `rotating_batch` on `next_retry_at` alone, so a company
        # this refuses and does not write back is due in every batch from here
        # on -- one of the `RETRY_SHARE` slots spent, every batch, for ever, on
        # a question that was answered before it was asked. See
        # `sync_engine.record_orsr_not_monitored`, which is where the delay and
        # the measured population are explained.
        reason = orsr_ineligibility_reason(company)
        record_orsr_not_monitored(company, f"ORSR monitoring preskočený: {reason}")
        logger.info(
            "ORSR sync skipped for company_id=%s ico=%s (%s)", company_id, company.ico, reason
        )
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
    try:
        profile = service.sync_company(company)
    except OrsrScraperError as exc:
        # Classified by `record_orsr_failure` rather than filed as `"network"`
        # here, which is what it used to do. The scraper raises this class both
        # when a request failed and when the register answered that it holds no
        # such IČO, and calling the second a network error is what kept 249
        # companies retrying daily against an answer that was never going to
        # change. It also carries the IČO inside a URL, so `_classify_error`'s
        # substring matching would file an IČO containing "500" as a server
        # error -- another reason the verdict is decided from the exception's
        # type rather than from its text.
        record_orsr_failure(company, exc)
        raise
    except Exception as exc:
        # A transport failure inside `RpoClient`, or a bug in the reading code.
        # Recorded and re-raised: whatever it was, the company would otherwise
        # leave no trace of having been attempted.
        record_orsr_failure(company, exc)
        raise

    record_orsr_outcome(
        company, fetch_ok=profile.fetch_ok, error=profile.last_error
    )
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
    except Exception:
        # `logger.warning` with the exception interpolated into the message is
        # the shape cce632f fixed one path over: no traceback, and a severity
        # that does not reach the error rate. A notification that was never
        # created is a silent loss, not a warning.
        logger.error(
            "Failed to detect executive changes for %s", company.ico, exc_info=True
        )

    return f"Company profile sync OK for {company.ico}"


def _orsr_candidates():
    """The population an ORSR rotation may draw from: eligible, not dissolved."""
    return Company.objects.filter(
        pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
        datum_zrusenia__isnull=True,
    )


def orsr_sync_batch(limit: int) -> list[int]:
    """Choose the company ids for one ORSR batch: retries, then new ground.

    Retries come from `CompanySyncStatus(source='orsr')` -- which exists only
    because the previous commit gave the source a writer. Before it, an ORSR
    failure was recorded on the profile and nowhere else, so this population was
    empty by construction and there was nothing to retry *with*.

    **New ground is "no `CompanySyncStatus` row for this source", which is what
    `rotating_batch` documents for every source and what this one used to
    disagree with.** It asked for `orsr_profile__isnull=True` instead, on the
    reading that a company already carrying a profile needs no first read. The
    reading is right about the read and wrong about the reach: the retry lane is
    a `CompanySyncStatus` row too, so a profile that has none was in neither
    half of the rotation -- not for a period, but permanently, since neither
    half was ever going to change its mind.

    That population is not hypothetical. Measured 2026-09-15: **19 591 profiles
    read successfully, not one of them with an ORSR status row**, and 19 517 of
    them on companies this rotation is allowed to touch (the other 74 are
    dissolved). They were written before commit 6603901 gave the source a
    writer, when an attempt recorded itself on the profile and nowhere else.
    Every writer records one now -- the Celery task and both management commands
    -- so the population is frozen rather than growing: nothing adds to it and
    nothing was ever going to take anything out of it.

    So the one filter comes off. Re-reading those 19 517 once is what gives each
    of them the row that makes it visible to `source_health`, enters it in the
    annual rotation, and records when it was last actually read. Their
    `last_synced_at` cannot say when that was, and that is a second reason the
    date had stopped meaning anything: `RpoSyncService.refresh_person_history`
    saves the profile with `update_fields=["raw_payload", "last_synced_at"]`, so
    the person-history rotation moves it -- 15 201 of the 19 591 carry a date
    from that rotation, and the other 4 390 the date of an ORSR write.

    The cost is one request per company, once. It is not spread evenly, and the
    ordering is worth stating because it is not what the shape suggests: the
    stranded profiles carry the *low* ids (median `id` 19 815, against 293 774
    for the candidates that have no profile at all), so the new-ground lane
    drains them first instead of interleaving. Measured 2026-09-15 against the
    live database: the first batch of 500 returned 40 retries and 460 new-ground
    ids, and **every one of the 460 was stranded**. At that rate and the
    four-hour beat it is ~42 ticks, about a week, and then the lane moves on to
    the rest.

    That week is not a detour around the other ground, it is the front of it:
    the 19 517 have to be read either way, and reading them first costs the
    227 104 that wait behind them nothing but the wait. The whole new-ground
    backlog is 246 621 companies (the 254 697 candidates less the 8 076 that
    already carry an answered row), so the order changes when each one is
    reached, not whether.

    It also makes the invariant self-healing. A future writer that forgets to
    record an attempt creates a profile with no row, and that is now new ground:
    the company is re-read once, records itself, and joins the rotation. No
    separate alarm is needed for it and none is added -- a check for a state
    this cannot reach again would be the "control that looks configured and
    decides nothing" this repository keeps finding.

    The retry lane is unchanged and remains the only way back to a company whose
    attempt failed into a profile: `OrsrScraperError` leaves a row behind with
    `fetch_ok=False`, and it is that row which puts it in the lane. It is no
    longer also what takes the company out of new ground.

    Split out from the task so the selection can be tested without dispatching
    Celery work -- the same shape as `financials_sync_batch`.
    """
    return rotating_batch(
        source=CompanySyncStatus.SOURCE_ORSR,
        candidates=_orsr_candidates(),
        limit=limit,
    )


def person_history_batch(limit: int) -> list[int]:
    """Companies whose person history has never been read from the register.

    The selection itself lives in `pending_person_history`, next to the key it
    selects on, because two callers need it -- this rotation and
    `refresh_person_history --dry-run` -- and a `--dry-run` that counts a
    different population than the run dispatches is worse than no dry run.
    """
    return list(
        pending_person_history().values_list("company_id", flat=True)[:limit]
    )


@shared_task(base=BaseSyncTask, queue='orsr', rate_limit='15/m')
def read_person_history(company_id: int) -> str:
    """Read one company's person history from the register and write it down.

    A separate task from `sync_company_orsr_data` rather than a flag on it,
    because the two ask different questions and the eligibility rule answers
    only one of them. That task is the ORSR **monitoring** entry point, and
    `is_orsr_eligible_company` belongs there: ORSR keeps current records, so
    monitoring a dissolved company spends somebody else's server on an answer
    that cannot change. Whether RPO holds a person history is a different
    question with a different answer -- it holds all of it, ended functions
    included -- and applying the monitoring rule to it was stranding 92 of the
    24 227 profiles waiting for a first read (measured 2026-09-13; three
    sampled, 16/62/30 person entries each). The population could never reach
    zero, so the one-off repair could never be retired.

    `queue='orsr'` and the same 15/min, though this calls RPO's API and not
    ORSR's: it is the same rotation over the same companies, and a second rate
    on one rotation would only make the drain arithmetic harder to state.
    """
    company = Company.objects.get(id=company_id)
    profile = OrsrCompanyProfile.objects.filter(company=company).first()
    if profile is None:
        # Not reachable through `person_history_batch`, which selects profile
        # ids -- but reachable by hand, and answering it beats an AttributeError.
        return f"No ORSR profile for {company.ico}"

    result = RpoSyncService().refresh_person_history(profile)
    logger.info("Person history for %s: %s", company.ico, result)
    return f"{company.ico}: {result}"


# `read_person_history` and `sync_company_orsr_data` share the `orsr` queue and
# its two concurrency slots, and each is capped at 15/m. When the register
# answers, that ceiling is reached and the queue drains at ~900/h; when it does
# not, one entity costs `timeout=30` five times over plus 22.5s of backoff, and
# two slots then pass ~42 entities an hour. Measured 2026-09-13: a single
# degraded window (18:00-20:00 UTC, one hour with 128 receives and 0
# completions, 474 read timeouts) left ~1 400 messages in `orsr` for a healthy
# window to clear.
#
# A fixed batch cannot see that. The dispatcher added 2 000 every four hours
# whatever the queue already held, so a batch that could not drain sat in front
# of the next one and the backlog was a random walk whose drift nobody measured.
# Hence the bound below: the dispatcher checks the backlog first and shrinks its
# batch to fit.
#
# It is a safety valve, not a throttle. The batch is 2 000 and the ORSR rotation
# adds 500, so a healthy queue never passes ~2 500 and the bound below changes
# nothing on the happy path -- `min()` only bites once a backlog that size has
# accumulated. And it cannot stall for ever: draining is always positive, so the
# backlog must fall back under the bound and dispatch resumes by itself.
PERSON_HISTORY_MAX_BACKLOG_ENV = "CISTAFIRMA_PERSON_HISTORY_MAX_BACKLOG"
DEFAULT_PERSON_HISTORY_MAX_BACKLOG = 6000


def _person_history_max_backlog() -> int:
    return _env_int(PERSON_HISTORY_MAX_BACKLOG_ENV, DEFAULT_PERSON_HISTORY_MAX_BACKLOG)


def _orsr_backlog() -> int | None:
    """Pending messages on the `orsr` queue, or None when the broker cannot say.

    None is the fail-open answer on purpose. A broker hiccup must not stop the
    backfill, and dispatching the full batch when the depth is unknown is what
    this did before the check existed -- so the worst case of a broker outage is
    the old behaviour, not a stalled population. The failure is still said out
    loud: an exception message from a broker connection carries the connection
    URL, and REDIS_URL may embed a password, so the detail stays in the log.
    """
    from backend.celery import app as celery_app

    try:
        with celery_app.connection_or_acquire() as conn:
            _, count, _ = conn.default_channel.queue_declare(
                queue='orsr', passive=True
            )
            return count
    except Exception:
        logger.warning(
            "Could not read the orsr backlog; dispatching the full batch unthrottled",
            exc_info=True,
        )
        return None


@shared_task(queue='celery')
def schedule_person_history_resync(limit: int = 2000):
    """Re-read the person history for companies the old reader left blank.

    Why this exists rather than a one-off command: the graph held 64 128
    relations all asserting they were current, and the register's own record
    says otherwise for at least the dissolved companies. Re-reading one company
    at 15 requests a minute is 27 hours of background work, and work that long
    has to survive a restart and finish without anyone watching it.

    It stops on its own. The key it selects on is the key the new reader
    writes, so when the last profile has been read this dispatches nothing and
    the beat entry becomes a no-op -- there is no "completed" state to forget to
    set. What it dispatches is `read_person_history`, not the ORSR monitoring
    task, so that every company this selects can actually be marked: a profile
    the worker refuses outright would be re-selected for ever and the
    population would never empty.

    `queue='celery'`, not `orsr`: this task queues the work rather than doing
    it, and a dispatcher on the queue it floods waits behind its own 2 000 tasks
    -- the failure the insurance entry's comment describes. The beat row says
    `celery` too, but a row is DB state that a direct `.delay()` bypasses, so
    the queue is declared here as well and routed in `CELERY_TASK_ROUTES`. All
    three layers say the same thing on purpose.

    The batch is sized against the backlog, because a dispatcher that cannot see
    the queue it feeds is the one control here that never judged its own
    outcome. See the bound's comment above for the measurements.
    """
    bound = _person_history_max_backlog()
    backlog = _orsr_backlog()

    if backlog is not None:
        headroom = max(0, bound - backlog)
        if headroom < limit:
            logger.info(
                "Person-history resync throttled: orsr holds %s, so %s of %s "
                "fits under the %s bound",
                backlog, headroom, limit, bound,
            )
        limit = min(limit, headroom)

    if limit <= 0:
        return f"Held back: orsr backlog {backlog} is at or above the {bound} bound"

    company_ids = person_history_batch(limit)
    for company_id in company_ids:
        read_person_history.delay(company_id)

    logger.info("Scheduled person-history resync for %s companies", len(company_ids))
    return f"Scheduled person-history resync for {len(company_ids)} companies"


@shared_task(queue='orsr')
def schedule_missing_orsr_sync(limit: int = 200):
    """Naplánuje ORSR sync: najprv opakovania, potom firmy bez profilu.

    The task name and signature stay put -- it is in
    `registers.services.focus_mode.FOCUS_KEEP_TASKS`, called by the admin
    `orsr_batch` action and by the legacy dashboard, and dispatched from the
    beat by name. Only the selection changes.

    It used to be `orsr_profile__isnull=True ... order_by('id')[:limit]`, which
    advanced only because an attempt usually creates a profile row. Two kinds of
    attempt do not, and each pinned a company to the head of the queue for ever,
    re-dispatched every four hours and blocking the rotation behind it:

    - a `RpoClient` transport failure, which writes nothing at all; and
    - before the previous commit, every failure, since nothing recorded an
      attempt. `OrsrScraperError` writes `fetch_ok=False` onto the profile, so
      that company left this population entirely and was never selected again.

    The rotation is now the shared `sync_engine.rotating_batch`: retries first,
    drawn from `CompanySyncStatus(source='orsr')` -- which is what the previous
    commit's writer made possible -- and new ground from the companies that have
    no status row for this source, which is every company until an attempt
    records one, profile or no profile. Because an attempt always writes a
    status row now, the head advances even when the attempt fails for good.
    """
    company_ids = orsr_sync_batch(limit)
    for company_id in company_ids:
        sync_company_orsr_data.delay(company_id)

    logger.info("Scheduled ORSR sync for %s companies", len(company_ids))
    return f"Scheduled ORSR sync for {len(company_ids)} companies"


@shared_task(base=BaseSyncTask, queue='financials', rate_limit='20/m')
def sync_company_financials_from_ruz(company_id: int):
    company = Company.objects.get(id=company_id)
    result = sync_company_and_record(company)
    # `detail` is logged because the scheduled path is where it would otherwise
    # be lost: `sync_company_and_record` keeps it only for failures, so a run
    # that reached the registry, found statements and recorded none of them
    # leaves `CompanySyncStatus.last_error` empty. That is the shape of the
    # question this log line answers -- "why did 79 companies store nothing?"
    # -- and the service now answers it in words. Logged here rather than in
    # the service so the manual CLI and the admin do not print it twice.
    logger.info(
        "RUZ financial sync company_id=%s ico=%s outcome=%s rows=%s detail=%s",
        company_id, company.ico, result.outcome.value, result.rows, result.detail,
    )
    return (
        f"RUZ financial sync for {company.ico}: "
        f"{result.outcome.value}, rows={result.rows}"
        + (f" ({result.detail})" if result.detail else "")
    )


def _financials_candidates(*, eligible_only: bool, missing_only: bool):
    """The population a financials batch may draw from, before ordering."""
    qs = Company.objects.all()
    if eligible_only:
        qs = qs.filter(
            pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
            datum_zrusenia__isnull=True,
        )
    if missing_only:
        qs = qs.filter(financial_results__isnull=True)
    return qs


def financials_sync_batch(
    limit: int, *, eligible_only: bool = True, missing_only: bool = False
) -> list[int]:
    """Choose the company ids for one financials batch: retries, then new ground.

    The shape of the rotation itself is `sync_engine.rotating_batch`, which is
    shared with `schedule_missing_orsr_sync` so the two cannot drift. What is
    specific to this source is the population, and the measured history that
    made the rotation necessary:

    The previous selection was `Company.objects.order_by('id')[:limit]` with a
    beat argument of 500, and it has no cursor, so **every run chose the same
    500 companies**. Measured 2026-09-11: 297 of the 309 companies holding any
    financial result at all sit inside ids 202-701, after 32 runs of the 12-hour
    beat. Nothing failed and nothing logged; coverage simply stopped at 309 of
    251 598 companies and stayed there. A scheduled job that looks alive and
    never advances is this repository's recurring defect, and this is its
    clearest instance.

    `eligible_only` (ORSR-eligible legal forms, not dissolved) is now the
    default. It is the same population `schedule_missing_orsr_sync` uses, and
    the beat calls this task with only `limit` -- whether to import statements
    for every company rather than the eligible subset is a separate decision
    from making the rotation advance, and it is not being made by default here.

    `stale_revision` is what makes a parser fix self-heal rather than wait for a
    company to come round again. Rows an older `PARSER_REVISION` wrote are drawn
    as retries -- bounded by `1 / RETRY_SHARE` of the batch -- so bumping the
    constant re-reads the stored corpus over days at the rotation's normal
    cadence. Without it the three parser fixes already committed would reach
    only companies the rotation had not yet read, because a successful read sets
    `next_retry_at` a year out.
    """
    return rotating_batch(
        source=CompanySyncStatus.SOURCE_FINANCIALS,
        candidates=_financials_candidates(
            eligible_only=eligible_only, missing_only=missing_only
        ),
        limit=limit,
        restrict_retries_to_candidates=missing_only,
        stale_revision=PARSER_REVISION,
    )


@shared_task(queue='financials')
def schedule_ruz_financials_sync(
    limit: int = 200, eligible_only: bool = True, missing_only: bool = False
):
    """Naplánuje RUZ financial sync pre dávku firiem, ktorá naozaj postupuje.

    The task name is load-bearing and deliberately unchanged: the admin-managed
    `PeriodicTask` row, `FOCUS_KEEP_TASKS`, `CELERY_BEAT_SCHEDULE`, the manual
    dispatcher and two tests all key on it. Only the selection changed, so
    there is no data migration to make and no row to edit -- and a rollback is
    a code revert rather than a scheduler change.
    """
    company_ids = financials_sync_batch(
        limit, eligible_only=eligible_only, missing_only=missing_only
    )
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

    Runs once daily via Celery Beat. Called with no argument -- as the beat
    entry does -- it recomputes **every** year that clears the threshold, not
    only the newest one. See `companies.services.benchmarking`: storing a single
    year was a `break` in a loop that wanted to be a filter, and it left 1 703
    of 15 467 companies without a benchmark, because both readers look the row
    up by the company's own latest filed year.
    """
    from companies.services.benchmarking import compute_sector_benchmarks as _compute
    per_year = _compute(year)
    if not per_year:
        return "Sector benchmarks done: no year cleared the threshold"
    # Summarised rather than repr'd: thirteen years of nineteen sections is a
    # few kilobytes of task result nobody reads.
    return "Sector benchmarks done: " + ', '.join(
        f"{y} ({len(sections)} sections, {sum(sections.values())} companies)"
        for y, sections in sorted(per_year.items(), reverse=True)
    )


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


@shared_task(queue='celery')
def match_company_seats():
    """Re-place every company's seat from the address the row carries now.

    `seat_*` is derived from `Company.{psc,mesto,ulica}`, and until #148 nothing
    recomputed it: `match_seat_addresses` had only ever been run by hand and was
    in no schedule, so a company that moved kept a pin on its old address for
    good. `Company.save()` now clears the derived columns when the address
    changes; this task is the other half -- the pass that computes them again.

    Six-hourly, matching `fetch-ruz-data-every-6-hours`, because that sync is
    what moves the addresses. Between the two the coupling is the point: the
    invalidation is immediate but the replacement is not, so the interval is how
    long a moved company is allowed to be blank instead of wrong -- and a pass
    every 6 h never has more than one sync's worth of debt to clear.

    On the `celery` queue, and it belongs on none of the others. `ruz_full`
    holds the sync cursor, so a minutes-long full-table sweep in that lane would
    delay a data import behind something that is not an import; `orsr` and
    `insurance` are rate-limited against somebody else's server, while this
    command reads only our own database.

    No lock, and the margin is the reason rather than an oversight: a full pass
    over 449 764 companies is minutes (the command's own docstring measures the
    chunks), so two runs overlap only if one takes far longer than a six-hour
    interval -- and even then both compute their placements from the same
    `AddressPoint` rows, so they would write the same values.
    """
    logger.info("Triggering match_seat_addresses command...")
    call_command('match_seat_addresses')
    logger.info("match_seat_addresses command finished.")
