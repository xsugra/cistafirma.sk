"""Central sync orchestrator.

This module replaces ad-hoc per-task progress tracking with a unified API:

- `enqueue_job(...)`: create a SyncJob row and dispatch the underlying Celery task.
- `update_company_status(...)`: record the outcome of a per-company sync attempt.

Design principles:
- Single source of truth: anything visible in the admin reads from these models.
- Idempotent: retrying the same task does not double-count items.
- Resilient: a worker crash leaves the job in a recoverable state (heartbeat
  watchdog flips it to `failed` after staleness, but data isn't corrupted).

There was a third entry point here, `tracked_sync_task(...)`, a decorator meant
to wrap a per-company Celery task and write `SyncJobItem` rows plus a
`CompanySyncStatus` row for each attempt. It is gone, along with `record_item`
and the `SyncJobItem` model: it was applied to **no task**, so its only writer
never ran and the table it fed never held a row. The per-company tasks record
their outcome directly (`ruz_financials_sync.sync_company_and_record` for
financials, `record_orsr_outcome` for ORSR), which is both simpler and the thing
that actually happens. Reinstating per-company item tracking is new work, not a
repair: see `docs/OBSERVABILITY.md`.
"""

from __future__ import annotations

import logging
import os
import random
import time
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Iterable

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from companies.models import Company
from registers.models import (
    AuditLog,
    CompanySyncStatus,
    SyncJob,
)
from registers.scrapers.orsr_scraper import OrsrNoRecordError, OrsrScraperError

logger = logging.getLogger(__name__)

RUZ_JOB_TYPES = frozenset(
    {"ruz_full", "ruz_full_firmy", "ruz_full_szco", "ruz_incremental", "ruz_repair"}
)
RUZ_CONCURRENCY_KEY = "ruz:global"


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

MAX_BACKOFF_SECONDS = 24 * 60 * 60  # cap at 24h
BASE_BACKOFF_SECONDS = 30

# A company the registry answered about is not due again for a year. This is
# not a retry delay -- the retry delay is `compute_next_retry`'s exponential
# backoff, and it applies to failures. This is what "we asked, and the answer
# is not going to change this week" costs: without it a successful attempt
# leaves `next_retry_at = NULL`, which the due-query reads as "due now", so the
# whole freshly-synced batch would refill the next batch and starve every
# company that has never been attempted.
#
# It lives here rather than beside either source because it is a fact about
# `update_company_status`'s `retry_after` contract and about `sync_due_q`
# below, and every rotating source needs the same value for the same reason.
ANSWERED_RETRY_AFTER = timedelta(days=365)

# A register that answered "I hold no such entity" is not going to change its
# mind tomorrow, so backoff is the wrong shape for it -- but a year is more
# certainty than the reading deserves. ORSR's public search is refreshed on its
# own schedule, so a company registered last month can be missing from it today
# and present next month; re-asking a few hundred companies once a month costs
# about eight requests a day and keeps that from being a year-long mistake.
#
# This is what an absence costs, measured: 249 companies were coming round every
# day at three requests each -- roughly 750 requests a day against a public
# register, none of which could ever succeed (2026-09-15).
NO_RECORD_RETRY_AFTER = timedelta(days=30)

# The `CompanySyncStatus.ERROR_TYPE_CHOICES` value for "the register holds
# nothing". Named from the register's side rather than ours -- `no_record` alone
# would read as a note about our own bookkeeping rather than as a fact about the
# company.
ERROR_TYPE_NO_RECORD = "not_in_register"


def compute_next_retry(consecutive_failures: int) -> timezone.datetime:
    """Exponential backoff with full jitter.

    1 failure  -> ~30s
    2 failures -> ~60s
    3 failures -> ~120s
    ...
    capped at 24h.
    """
    if consecutive_failures <= 0:
        return timezone.now()
    base = min(
        BASE_BACKOFF_SECONDS * (2 ** (consecutive_failures - 1)),
        MAX_BACKOFF_SECONDS,
    )
    jitter = random.uniform(0, base * 0.2)
    return timezone.now() + timedelta(seconds=base + jitter)


def should_retry(status: CompanySyncStatus) -> bool:
    """Decide whether a company-source pair is eligible for sync now."""
    if status.is_blocked:
        return False
    if status.next_retry_at and timezone.now() < status.next_retry_at:
        return False
    return True


# ---------------------------------------------------------------------------
# Per-company status updates
# ---------------------------------------------------------------------------


def update_company_status(
    *,
    company_id: int,
    source: str,
    success: bool,
    error: str = "",
    error_type: str = "",
    retry_after: timedelta | None = None,
    failure_retry_after: timedelta | None = None,
    detail: str | None = None,
    parser_revision: int | None = None,
) -> CompanySyncStatus:
    """Upsert the per-company, per-source status after a sync attempt.

    `retry_after` sets how long a **successful** attempt stays out of the due
    queue. It defaults to `None`, which stores `next_retry_at = NULL` -- and the
    due-query reads `NULL` as "due now", so a source whose successes are common
    needs to say something here or its rotation cannot advance. See
    `ANSWERED_RETRY_AFTER` above.

    A failure ignores it: how long to wait after a failure is
    `compute_next_retry`'s decision, and it is backoff, not a fixed delay.

    `failure_retry_after` is that decision, for the failures that are not
    backoff-shaped. The two mean different things and are separate arguments
    precisely so they cannot be confused: backoff answers "the source is having
    trouble, wait and it may pass", while a caller passing this is saying "the
    source *answered*, and the answer will still be this one in a month". ORSR
    learning that the register holds no such IČO is the case that needed it --
    `NO_RECORD_RETRY_AFTER` above -- and a daily retry there is not patience,
    it is 249 companies asking a question whose answer is already known. On a
    failure it replaces `compute_next_retry` outright.

    `detail` is the attempt's own sentence, and is written on success too --
    which `error` never is, because a successful attempt blanks it. The three
    values mean three different things and the column is only honest if the
    caller picks the right one:

    - a sentence: what this attempt had to say about itself;
    - `None`: this caller has nothing to say, so whatever is there stays. Three
      sources pass nothing (VZP, Sociálna poisťovňa, RUZ dates) and they are
      different `source` rows, so nothing of theirs is overwritten;
    - `""`: nothing is there *because this attempt has no sentence*, and a
      leftover from an earlier writer must not be read as one. Only ORSR passes
      this, and it has to: its row is written by more than one writer --
      `record_orsr_not_monitored` puts a reason on it, and migration 0018 seeded
      147 of them with a note about the migration. Left alone, that note sat
      under a `not_in_register` verdict from a later attempt and read, in the
      admin's reason cell, as the reason for *that* attempt. Measured
      2026-09-15: 125 rows were in exactly that state.

    `parser_revision` records which revision of the reading produced the rows
    this attempt wrote, and only `financials` passes it. `None` leaves the
    column alone rather than clearing it -- for the five sources that have no
    parser, and for a financials attempt that failed at the transport, where
    nothing was read and the stored rows keep the revision that wrote them.
    """
    now = timezone.now()
    with transaction.atomic():
        status, _ = CompanySyncStatus.objects.select_for_update().get_or_create(
            company_id=company_id,
            source=source,
        )
        status.last_attempted_at = now
        if success:
            status.last_succeeded_at = now
            status.consecutive_failures = 0
            status.last_error = ""
            status.last_error_type = ""
            status.next_retry_at = now + retry_after if retry_after else None
        else:
            status.consecutive_failures += 1
            status.last_error = (error or "")[:4000]
            status.last_error_type = error_type or "unknown"
            if failure_retry_after is not None:
                status.next_retry_at = now + failure_retry_after
            else:
                status.next_retry_at = compute_next_retry(status.consecutive_failures)
        if detail is not None:
            status.last_detail = detail[:4000]
        if parser_revision is not None:
            status.parser_revision = parser_revision
        status.save()
    return status


def record_ruz_date_outcome(
    *, company_id: int, refused: Iterable[tuple[str, Any]]
) -> CompanySyncStatus:
    """Record one RUZ attempt for a company: a success, or a refusal.

    This is what makes `ruz_api.apply_ruz_dates` refusing to write a control
    rather than a log line: `source_health` counts these against the source and
    fails it when they stop looking like an upstream typo and start looking
    like a format change, which is what lets `make ops-check` reach a verdict
    instead of a human having to grep a JSON stream.

    It writes a row for **every** attempt, not only for a refusal, and that is
    the change: `ruz` used to write a row only when a date went unread and never
    a success, so `consecutive_failures` stayed 0 and the refusal was invisible
    to every reader that keys on it -- `adminapi`'s `failures_24h`, its
    per-source card, `company_filters`' `sync_state=failing`, and
    `lead_scoring`'s average all read that column. The gate could say *how many*
    records carried an unreadable date and no screen could say *which*.

    That bypass existed for a real reason, and the reason is now gone: with no
    success path, a written failure could never be cleared, so incrementing the
    count would have armed a trap for the first reader to trust it. A success
    row is what makes writing the failure honest. The cost is one row per
    company per RUZ run -- what every other source already pays -- paid on the
    incremental run (thousands) far more often than on a full resync, which is
    already a manual, backup-gated, hours-long operation.

    Both RUZ writers call this, so the two cannot drift: a refusal recorded by
    the six-hourly beat is cleared by an on-demand sync of the same company, and
    the other way round.
    """
    refused = list(refused)
    if not refused:
        return update_company_status(
            company_id=company_id, source=CompanySyncStatus.SOURCE_RUZ, success=True
        )
    return update_company_status(
        company_id=company_id,
        source=CompanySyncStatus.SOURCE_RUZ,
        success=False,
        error="; ".join(f"Unreadable {field}={raw!r}" for field, raw in refused),
        error_type="parse_error",
    )


def record_orsr_outcome(
    company: Company,
    *,
    fetch_ok: bool,
    error: str = "",
    error_type: str = "",
    failure_retry_after: timedelta | None = None,
) -> CompanySyncStatus:
    """Record one ORSR attempt for a company: the source's only writer.

    ORSR wrote `OrsrCompanyProfile` and nothing else, so `CompanySyncStatus`
    held **no** `orsr` row at all -- measured 2026-09-11, zero rows, and no code
    path able to create one. Everything that reads that table was therefore
    blind to the source rather than reporting it as quiet: `source_health` could
    not name it, the per-source dashboard card, `company_filters`'
    `sync_state=failing` and `lead_scoring`'s average each covered a population
    that silently excluded it.

    It also gave ORSR no **backoff**, and the two ways an attempt can fail both
    ended in a dead end. `OrsrScraperError` is raised *after*
    `OrsrSyncService` has written `fetch_ok=False` onto the profile, so the
    company leaves the `orsr_profile__isnull=True` population and
    `schedule_missing_orsr_sync` never selects it again. Any other exception --
    a transport failure inside `RpoClient` -- writes nothing at all, so the
    company stays in that population and is re-dispatched at the head of an
    `order_by('id')` queue on every run, and `BaseSyncTask`'s three retries
    over a few minutes are the only ones it will ever get.

    A success is pushed `ANSWERED_RETRY_AFTER` out for the same reason
    financials is: `next_retry_at = NULL` reads as "due now", so a success that
    wrote nothing would sit permanently at the head of the retry lane and starve
    every company that genuinely needs another attempt.

    `detail` is passed as `""` rather than left at `None`, and that is a claim
    rather than a default: ORSR has no sentence of its own to add, and this
    attempt is now the newest thing that happened to the row, so anything an
    earlier writer left on it has stopped being the reason. Two such writers
    exist -- `record_orsr_not_monitored`, which puts a reason on the row when it
    takes a company out of the lane, and migration 0018, which seeded 147 rows
    with a note about itself. Leaving them alone made that note sit under a
    later `not_in_register` verdict and read, in the admin's reason cell, as the
    reason for the *newest* attempt. Measured 2026-09-15: 125 rows were in
    exactly that state, and the note also doubled as the reverse migration's
    delete key.
    """
    return update_company_status(
        company_id=company.id,
        source=CompanySyncStatus.SOURCE_ORSR,
        success=fetch_ok,
        error="" if fetch_ok else error,
        error_type="" if fetch_ok else error_type,
        retry_after=ANSWERED_RETRY_AFTER if fetch_ok else None,
        failure_retry_after=None if fetch_ok else failure_retry_after,
        detail="",
    )


def record_orsr_failure(company: Company, exc: BaseException) -> CompanySyncStatus:
    """Record a failed ORSR attempt from the exception that ended it.

    One function where there were three copies of the same claim. Each call site
    -- the beat rotation and the two management commands -- caught
    `OrsrScraperError` and filed it as `"network"`, which is a statement about
    the transport, made about every way an attempt can end. It was true often
    enough to look right: the scraper raises that class when a request failed,
    and it also raised it when the register had answered with something that was
    not a company výpis. The second reading is not a network error, and filing
    it as one put 249 companies into a 24-hour backoff loop that could never
    end, because the answer was never going to change.

    So the classification lives here, next to the delays, rather than being
    spelled out at each caller: `OrsrNoRecordError` keeps its own label and gets
    `NO_RECORD_RETRY_AFTER` instead of backoff, every other `OrsrScraperError`
    stays `"network"` exactly as before, and anything else falls through to
    `_classify_error`, which is what the commands were already doing for their
    catch-all clause.
    """
    if isinstance(exc, OrsrNoRecordError):
        return record_orsr_outcome(
            company,
            fetch_ok=False,
            error=f"{type(exc).__name__}: {exc}",
            error_type=ERROR_TYPE_NO_RECORD,
            failure_retry_after=NO_RECORD_RETRY_AFTER,
        )
    if isinstance(exc, OrsrScraperError):
        return record_orsr_outcome(
            company,
            fetch_ok=False,
            error=f"{type(exc).__name__}: {exc}",
            error_type="network",
        )
    return record_orsr_outcome(
        company,
        fetch_ok=False,
        error=f"{type(exc).__name__}: {exc}",
        error_type=_classify_error(exc),
    )


def record_orsr_not_monitored(company: Company, reason: str) -> CompanySyncStatus | None:
    """Take a due ORSR row out of the lane for a company ORSR will not ask about.

    `sync_company_orsr_data` refuses a company that is dissolved, or whose legal
    form is not one ORSR carries, and returns before any request. It also
    returned before any write -- so a retry row that came due for such a company
    was drawn by every batch and written back by none, due for ever and
    occupying one of the `RETRY_SHARE` slots the lane has for real retries.
    Cheap per attempt (nothing is requested) and invisible to every reader,
    which is the shape this codebase treats as the defect.

    Measured 2026-09-15: 19 such rows exist, every one of them for a company
    dissolved after its last successful read, and every one of them due
    `2027-09` -- a year on from that read, because a success is what
    `ANSWERED_RETRY_AFTER` pushes out. Nothing leaks today; the leak is what
    happens on that date, and it then grows with each dissolution.

    A year is the same delay a successful attempt gets, and for the same
    reason: ORSR holds current records, so there is nothing to monitor about a
    dissolved company, and a correction to `datum_zrusenia` in our own data is
    something the annual pass will pick up. That the two constants agree is not
    a coincidence but it is also not a coupling -- this is the cadence for
    "the answer we already have stays good", which is what both are.

    **No row is created if there is none.** A company ORSR refuses never had an
    attempt recorded, and inventing one would put it into the retry lane for
    ever -- the thing `RpoSyncService.refresh_person_history` refuses to do for
    exactly this reason. This only ever edits a row that exists, which is to say
    one an actual attempt already wrote.

    Nothing about the attempt is claimed: `last_attempted_at`,
    `last_succeeded_at`, `consecutive_failures` and `last_error` are all left as
    they were, because nothing was attempted. `last_detail` carries the reason,
    which is where a reader looking at the row will find it.
    """
    status = CompanySyncStatus.objects.filter(
        company_id=company.id, source=CompanySyncStatus.SOURCE_ORSR
    ).first()
    if status is None:
        return None
    status.next_retry_at = timezone.now() + ANSWERED_RETRY_AFTER
    status.last_detail = reason[:4000]
    status.save(update_fields=["next_retry_at", "last_detail", "updated_at"])
    return status


def block_company(*, company_id: int, source: str, reason: str = "") -> CompanySyncStatus:
    status, _ = CompanySyncStatus.objects.update_or_create(
        company_id=company_id,
        source=source,
        defaults={"is_blocked": True, "blocked_reason": reason},
    )
    return status


def unblock_company(*, company_id: int, source: str) -> CompanySyncStatus:
    status, _ = CompanySyncStatus.objects.update_or_create(
        company_id=company_id,
        source=source,
        defaults={"is_blocked": False, "blocked_reason": ""},
    )
    return status


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------


def enqueue_job(
    *,
    job_type: str,
    parameters: dict | None = None,
    triggered_by_id: int | None = None,
    triggered_via: str = "system",
    notes: str = "",
) -> SyncJob:
    """Create a queued SyncJob. Caller is responsible for dispatching the task."""
    job = SyncJob.objects.create(
        job_type=job_type,
        status="queued",
        triggered_by_id=triggered_by_id,
        triggered_via=triggered_via,
        parameters=parameters or {},
        notes=notes,
    )
    AuditLog.objects.create(
        actor_id=triggered_by_id,
        action="sync.enqueue",
        target_type="syncjob",
        target_id=str(job.pk),
        payload={"job_type": job_type, "parameters": parameters or {}, "via": triggered_via},
    )
    return job


def enqueue_ruz_job(
    *,
    job_type: str,
    parameters: dict | None = None,
    triggered_by_id: int | None = None,
    triggered_via: str = "system",
    notes: str = "",
) -> tuple[SyncJob, bool]:
    """Create one globally exclusive RUZ job, or return the active one."""
    if job_type not in RUZ_JOB_TYPES:
        raise ValueError(f"{job_type} is not a RUZ job type")

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(
                job_type=job_type,
                status="queued",
                triggered_by_id=triggered_by_id,
                triggered_via=triggered_via,
                parameters=parameters or {},
                notes=notes,
                concurrency_key=RUZ_CONCURRENCY_KEY,
            )
            AuditLog.objects.create(
                actor_id=triggered_by_id,
                action="sync.enqueue",
                target_type="syncjob",
                target_id=str(job.pk),
                payload={"job_type": job_type, "parameters": parameters or {}, "via": triggered_via},
            )
            return job, True
    except IntegrityError:
        job = (
            SyncJob.objects.filter(
                concurrency_key=RUZ_CONCURRENCY_KEY,
                status__in=["queued", "running"],
            )
            .order_by("-queued_at")
            .first()
        )
        if job is None:
            raise
        return job, False


def claim_ruz_job(job_id: int, *, celery_task_id: str = "") -> SyncJob | None:
    """Atomically claim a queued RUZ job; duplicate deliveries are ignored."""
    now = timezone.now()
    claimed = SyncJob.objects.filter(
        pk=job_id,
        job_type__in=RUZ_JOB_TYPES,
        concurrency_key=RUZ_CONCURRENCY_KEY,
        status="queued",
    ).update(
        status="running",
        started_at=now,
        last_heartbeat=now,
        celery_task_id=celery_task_id,
    )
    if not claimed:
        return None
    return SyncJob.objects.get(pk=job_id)


def start_job(job: SyncJob, *, total_items: int | None = None, celery_task_id: str = "") -> None:
    # One `now` for both columns: two calls put a few microseconds between a
    # job's start and its first heartbeat, which reads as a real interval in
    # the admin and makes "did it ever beat?" needlessly harder to answer.
    now = timezone.now()
    SyncJob.objects.filter(pk=job.pk).update(
        status="running",
        started_at=now,
        last_heartbeat=now,
        total_items=total_items if total_items is not None else job.total_items,
        celery_task_id=celery_task_id or job.celery_task_id,
    )


def complete_job(job: SyncJob, *, notes: str = "") -> None:
    update = {
        "status": "completed",
        "completed_at": timezone.now(),
        "last_heartbeat": timezone.now(),
    }
    if notes:
        update["notes"] = notes
    SyncJob.objects.filter(pk=job.pk).update(**update)


def fail_job(job: SyncJob, *, error: str) -> None:
    SyncJob.objects.filter(pk=job.pk).update(
        status="failed",
        completed_at=timezone.now(),
        last_error=(error or "")[:4000],
    )


def cancel_job(job: SyncJob, *, reason: str = "") -> None:
    SyncJob.objects.filter(pk=job.pk).update(
        status="cancelled",
        completed_at=timezone.now(),
        notes=(job.notes + f"\nCancelled: {reason}").strip(),
    )


def pause_job(job: SyncJob, *, reason: str = "") -> None:
    # Only append when there is something to say. An unconditional f-string
    # left job #3 with three bare "Paused: " lines -- a note that records
    # nothing while looking like it does.
    update: dict = {"status": "paused"}
    if reason:
        update["notes"] = (job.notes + f"\nPaused: {reason}").strip()
    SyncJob.objects.filter(pk=job.pk).update(**update)


def set_job_outcome(
    job_id: int,
    *,
    processed: int,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
) -> None:
    """Record what a run actually achieved, without touching its status.

    A completed job showing zero processed items cannot be told apart from one
    that did nothing. That is not hypothetical: the 12:22 RUZ run created 17
    companies and was stored as `processed_items=0`, because the command
    reports to `SyncProgress` -- whose counters accumulate across runs -- and
    never to the job at all.

    Only the counters are written. `status` stays the lifecycle owner's
    (`complete_job` / `fail_job`), so there is never a second writer of it.
    """
    SyncJob.objects.filter(pk=job_id).update(
        processed_items=processed,
        succeeded_items=succeeded,
        failed_items=failed,
        skipped_items=skipped,
    )


def _classify_error(exc: Exception) -> str:
    """Map an exception to a CompanySyncStatus.ERROR_TYPE_CHOICES value."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return "timeout"
    if "429" in msg or "rate" in msg:
        return "http_429"
    if "404" in msg or "not found" in msg:
        return "http_404"
    if "5" in msg and ("500" in msg or "502" in msg or "503" in msg or "504" in msg):
        return "http_5xx"
    if "parse" in msg or "decode" in msg or "html" in msg:
        return "parse_error"
    if "connection" in msg or "network" in msg or "dns" in msg:
        return "network"
    if "validation" in name:
        return "validation"
    return "unknown"


# ---------------------------------------------------------------------------
# Watchdog: detect stuck jobs
# ---------------------------------------------------------------------------


DEFAULT_STUCK_HEARTBEAT_MINUTES = 30
STUCK_HEARTBEAT_ENV = "CISTAFIRMA_STUCK_HEARTBEAT_MINUTES"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def stuck_heartbeat_threshold() -> timedelta:
    """How stale a heartbeat may get before its job counts as dead.

    Read from the environment rather than fixed in code, because the right
    value is set by the slowest *legitimate* step and that is not knowable
    here. It was 10 minutes while nothing called this at all; the first real
    caller is the RUZ import, where one page is a thousand companies behind a
    0.1s-per-company sleep and a retry session that may stall for minutes. A
    threshold tighter than that does not protect anything -- it kills healthy
    imports, which is worse than the stale row it was meant to reap.
    """
    return timedelta(
        minutes=_env_int(STUCK_HEARTBEAT_ENV, DEFAULT_STUCK_HEARTBEAT_MINUTES)
    )


def stuck_cutoff():
    """The instant before which a heartbeat means the job is dead.

    Single owner of what "stuck" means: the watchdog below and the read-only
    `sync_health` command both need the same verdict, so neither re-derives
    it. Same principle as `offsite_status.sh` owning the off-site verdict.
    """
    return timezone.now() - stuck_heartbeat_threshold()


def is_stuck(job: SyncJob, *, cutoff=None) -> bool:
    """Whether the watchdog would reap this job.

    The single owner of the rule. `detect_and_fail_stuck_jobs` below and the
    read-only `sync_health` command both need it, and the gate is only useful
    if it agrees with the reaper -- so it asks rather than re-deriving the
    condition and drifting. A job that never beat at all is judged on
    `started_at`, because "never wrote a heartbeat" is not the same as "wrote
    one long ago" and only the second means a worker once existed.
    """
    if job.status != "running":
        return False
    if cutoff is None:
        cutoff = stuck_cutoff()
    if job.last_heartbeat is None:
        return job.started_at is not None and job.started_at < cutoff
    return job.last_heartbeat < cutoff


def detect_and_fail_stuck_jobs() -> int:
    """Mark running jobs as failed if their heartbeat is stale.

    Called from a periodic Celery beat task.
    Returns the number of jobs flipped.
    """
    cutoff = stuck_cutoff()
    count = 0
    # Filtered in Python through `is_stuck` rather than in the queryset: the
    # rule is the part that must not exist twice, and the running set is a
    # handful of rows that the watchdog walks every ten minutes.
    for job in SyncJob.objects.filter(status="running"):
        if not is_stuck(job, cutoff=cutoff):
            continue
        fail_job(job, error="Stuck job auto-failed by watchdog (no heartbeat).")
        AuditLog.objects.create(
            action="sync.watchdog.failed",
            target_type="syncjob",
            target_id=str(job.pk),
            payload={"reason": "heartbeat_stale", "last_heartbeat": str(job.last_heartbeat)},
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Iteration helpers
# ---------------------------------------------------------------------------


@contextmanager
def heartbeat_loop(job: SyncJob, interval_seconds: int = 30):
    """Context manager that keeps the job's last_heartbeat fresh while iterating.

    Use this around long-running loops that pass long enough between natural
    checkpoints for the watchdog's staleness threshold to be reached.
    """
    last = [time.time()]

    def beat():
        if time.time() - last[0] >= interval_seconds:
            job.heartbeat()
            last[0] = time.time()

    try:
        yield beat
    finally:
        job.heartbeat()


def sync_due_q(next_retry_field: str, now):
    """The one definition of "this source may be attempted now".

    `next_retry_field` is the full lookup path to a `next_retry_at` column, e.g.
    `"next_retry_at"` on `CompanySyncStatus` or
    `"sync_statuses__next_retry_at"` on `Company`.

    Kept in a single place because two different populations are asked about it
    in two different shapes -- rows that exist and carry a `next_retry_at`, and
    companies that have never been attempted and have no row at all -- and they
    must agree on what "due" means, or a rotation double-counts one and starves
    the other. `NULL` means "due now", which is why a successful attempt that
    wants to stay out of the queue has to write a real timestamp rather than
    clearing the field.
    """
    return Q(**{f"{next_retry_field}__lte": now}) | Q(
        **{f"{next_retry_field}__isnull": True}
    )


def companies_due_for_sync(
    source: str, *, limit: int = 200, stale_revision: int | None = None
) -> Iterable[CompanySyncStatus]:
    """Return CompanySyncStatus rows that are eligible for a fresh attempt.

    Eligible = not blocked AND (next_retry_at is null OR next_retry_at <= now).
    Ordered by oldest last_attempted_at first so we revisit the stalest rows,
    with `id` as a tiebreak: every row written by one batch shares a
    `last_attempted_at` to the microsecond, so without it the order within a
    batch is the database's to choose and two consecutive calls can return the
    same rows.

    `stale_revision` widens eligible with the rows a **successful** attempt
    stamped with an older parser revision, whatever `next_retry_at` says. It
    exists because a success pushes the next attempt a year out
    (`ANSWERED_RETRY_AFTER`), so without it a parser fix reaches only the
    companies the rotation happens to revisit -- the rows already stored keep
    the reading of a parser that no longer exists, and nothing marks them.

    The `last_succeeded_at is not null` guard is what keeps this from becoming a
    trap. Widening on `parser_revision` alone would pull in every row that has
    *ever failed* -- a row that failed carries no revision, so it would read as
    stale -- and those rows would then be drawn every batch, bypassing the
    exponential backoff that `compute_next_retry` exists to apply. The stale
    rule is about re-reading what we read; repetition of a failure stays
    `next_retry_at`'s decision.
    """
    now = timezone.now()
    due = sync_due_q("next_retry_at", now)

    if stale_revision is not None:
        stale = Q(last_succeeded_at__isnull=False) & (
            Q(parser_revision__isnull=True) | Q(parser_revision__lt=stale_revision)
        )
        due = due | stale

    qs = (
        CompanySyncStatus.objects.filter(source=source, is_blocked=False)
        .filter(due)
        .order_by("last_attempted_at", "id")
        .select_related("company")[:limit]
    )
    return qs


# ---------------------------------------------------------------------------
# Batch rotation
# ---------------------------------------------------------------------------

# How much of a batch may be spent on retries. A failing minority must not be
# able to hold the whole rotation -- but it must also not be starved, because a
# company that asked to be tried again is the one case where the work is known
# to be needed.
RETRY_SHARE = 4


def rotating_batch(
    *,
    source: str,
    candidates,
    limit: int,
    restrict_retries_to_candidates: bool = False,
    stale_revision: int | None = None,
) -> list[int]:
    """Choose one batch of company ids for a per-company source.

    Two populations, in this order:

    1. **Retries** -- `CompanySyncStatus(source=...)` rows whose `next_retry_at`
       has arrived: the companies that were tried and asked to be tried again.
       Capped at `1 / RETRY_SHARE` of the batch.
    2. **New ground** -- rows of `candidates` with no status row for this source
       at all, ordered by `id`. An attempt always writes a status row, so the
       head of this queue moves after every batch: resumable and deterministic
       without storing a cursor of its own.

    `candidates` is the queryset of companies this source is allowed to touch,
    and the two populations are kept disjoint on purpose -- new ground excludes
    both the companies that have an attempt recorded *and* the ids already taken
    as retries. The second exclusion is redundant when "has an attempt" and "is
    a candidate" line up, and it is what keeps the guarantee true when they do
    not: ORSR's new ground is "no profile", which a company can lack while
    having a due attempt recorded, and the same company would otherwise be
    handed out twice in one batch.

    `restrict_retries_to_candidates` re-checks the due rows against
    `candidates`. It exists because a caller can narrow the population for one
    run (`missing_only`) and the due list knows nothing about that: without the
    re-check the batch would dispatch companies the caller excluded. It costs a
    query over the due ids, so it is off by default.

    `stale_revision` is passed straight to `companies_due_for_sync`, which is
    where the argument is explained. What matters here is *where the stale rows
    enter*: as retries, not as a third population, so they inherit the
    `1 / RETRY_SHARE` cap and a parser bump re-reads the corpus at the
    rotation's normal cadence instead of flooding a queue. That cap is the whole
    reason this is a parameter rather than a separate pass.

    **This is the fix for a scheduled job that looks alive and never advances.**
    The previous shape was `Company.objects.order_by('id')[:limit]` with a beat
    argument of 500: no cursor, so every run chose the same 500 companies.
    Measured 2026-09-11, 297 of the 309 companies holding any financial result
    sat inside ids 202-701 after 32 runs of the 12-hour beat. Nothing failed and
    nothing logged; coverage simply stopped at 309 of 251 598 and stayed there.
    """
    retry_budget = limit // RETRY_SHARE

    retry_ids: list[int] = []
    if retry_budget > 0:
        due = companies_due_for_sync(
            source, limit=retry_budget, stale_revision=stale_revision
        )
        if restrict_retries_to_candidates:
            retry_ids = list(
                candidates.filter(id__in=[status.company_id for status in due])
                .order_by("id")
                .values_list("id", flat=True)
            )
        else:
            retry_ids = [status.company_id for status in due]

    remaining = max(limit - len(retry_ids), 0)
    if remaining == 0:
        return retry_ids

    attempted = CompanySyncStatus.objects.filter(
        company_id=OuterRef("pk"), source=source
    )
    new_ids = list(
        candidates.exclude(Exists(attempted))
        .exclude(id__in=retry_ids)
        .order_by("id")
        .values_list("id", flat=True)[:remaining]
    )
    return retry_ids + new_ids
