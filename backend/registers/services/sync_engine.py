"""Central sync orchestrator.

This module replaces ad-hoc per-task progress tracking with a unified API:

- `enqueue_job(...)`: create a SyncJob row and dispatch the underlying Celery task.
- `update_company_status(...)`: record the outcome of a per-company sync attempt.
- `tracked_sync_task(...)`: decorator that wraps a Celery task to auto-update
  SyncJob/SyncJobItem rows and CompanySyncStatus.

Design principles:
- Single source of truth: anything visible in the admin reads from these models.
- Idempotent: retrying the same task does not double-count items.
- Resilient: a worker crash leaves the job in a recoverable state (heartbeat
  watchdog flips it to `failed` after staleness, but data isn't corrupted).
"""

from __future__ import annotations

import functools
import logging
import os
import random
import time
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterable

from django.db import IntegrityError, transaction
from django.utils import timezone

from registers.models import (
    AuditLog,
    CompanySyncStatus,
    SyncJob,
    SyncJobItem,
)

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
) -> CompanySyncStatus:
    """Upsert the per-company, per-source status after a sync attempt."""
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
            status.next_retry_at = None
        else:
            status.consecutive_failures += 1
            status.last_error = (error or "")[:4000]
            status.last_error_type = error_type or "unknown"
            status.next_retry_at = compute_next_retry(status.consecutive_failures)
        status.save()
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


def record_item(
    *,
    job: SyncJob,
    item_key: str,
    company_id: int | None = None,
    status: str = "success",
    error_message: str = "",
    error_type: str = "",
    duration_ms: int | None = None,
) -> SyncJobItem:
    """Append a SyncJobItem and bump the parent job's counters atomically."""
    item = SyncJobItem.objects.create(
        job=job,
        item_key=item_key,
        company_id=company_id,
        status=status,
        attempts=1,
        error_message=(error_message or "")[:4000],
        error_type=error_type or "",
        duration_ms=duration_ms,
        completed_at=timezone.now() if status in ("success", "failed", "skipped") else None,
    )
    update_kwargs: dict = {"last_heartbeat": timezone.now(), "processed_items": SyncJob._meta.get_field("processed_items").default}
    # Bump counters via F() to avoid races.
    from django.db.models import F

    counter_updates: dict = {"processed_items": F("processed_items") + 1, "last_heartbeat": timezone.now()}
    if status == "success":
        counter_updates["succeeded_items"] = F("succeeded_items") + 1
    elif status == "failed":
        counter_updates["failed_items"] = F("failed_items") + 1
    elif status == "skipped":
        counter_updates["skipped_items"] = F("skipped_items") + 1
    SyncJob.objects.filter(pk=job.pk).update(**counter_updates)
    return item


# ---------------------------------------------------------------------------
# Decorator for Celery tasks
# ---------------------------------------------------------------------------


def tracked_sync_task(*, source: str, item_key_arg: str = "company_id"):
    """Decorator that wraps a per-company Celery task to auto-update sync state.

    Usage:

        @app.task(bind=True, queue="orsr")
        @tracked_sync_task(source="orsr", item_key_arg="company_id")
        def sync_company_orsr_data(self, company_id):
            ...

    The wrapped function still does its work; this decorator handles the
    bookkeeping (CompanySyncStatus + SyncJobItem rows).

    The wrapped function may raise to signal failure; the decorator will
    record the error and re-raise (so Celery retry semantics still work).
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve company_id from kwargs first, then positional after `self`.
            company_id = kwargs.get(item_key_arg)
            if company_id is None and len(args) >= 2:
                company_id = args[1]

            # Optional job_id passed via kwargs lets us link this attempt to a parent job.
            job_id = kwargs.pop("_sync_job_id", None)
            job = SyncJob.objects.filter(pk=job_id).first() if job_id else None

            started = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — re-raised below
                duration_ms = int((time.time() - started) * 1000)
                error_type = _classify_error(exc)
                error_message = f"{type(exc).__name__}: {exc}"
                if company_id:
                    update_company_status(
                        company_id=company_id,
                        source=source,
                        success=False,
                        error=error_message,
                        error_type=error_type,
                    )
                if job:
                    record_item(
                        job=job,
                        item_key=str(company_id) if company_id else "?",
                        company_id=company_id,
                        status="failed",
                        error_message=error_message,
                        error_type=error_type,
                        duration_ms=duration_ms,
                    )
                logger.exception("tracked_sync_task[%s] failed for %s", source, company_id)
                raise
            else:
                duration_ms = int((time.time() - started) * 1000)
                if company_id:
                    update_company_status(
                        company_id=company_id,
                        source=source,
                        success=True,
                    )
                if job:
                    record_item(
                        job=job,
                        item_key=str(company_id) if company_id else "?",
                        company_id=company_id,
                        status="success",
                        duration_ms=duration_ms,
                    )
                return result

        return wrapper

    return decorator


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

    Use this around long-running loops where individual record_item() calls
    might be too slow to count as a heartbeat.
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


def companies_due_for_sync(source: str, *, limit: int = 200) -> Iterable[CompanySyncStatus]:
    """Return CompanySyncStatus rows that are eligible for a fresh attempt.

    Eligible = not blocked AND (next_retry_at is null OR next_retry_at <= now).
    Ordered by oldest last_attempted_at first so we revisit the staleset rows.
    """
    now = timezone.now()
    qs = (
        CompanySyncStatus.objects.filter(source=source, is_blocked=False)
        .filter(
            models_q_lte("next_retry_at", now) | models_q_isnull("next_retry_at")
        )
        .order_by("last_attempted_at")
        .select_related("company")[:limit]
    )
    return qs


# tiny Q helpers to avoid importing django.db.models.Q at top level
def models_q_lte(field, value):
    from django.db.models import Q

    return Q(**{f"{field}__lte": value})


def models_q_isnull(field, value=True):
    from django.db.models import Q

    return Q(**{f"{field}__isnull": value})
