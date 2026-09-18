"""Sync management endpoints: jobs, per-company status, focus mode, queues."""
import logging
from datetime import datetime

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from adminapi.permissions import IsAdminStaff, IsSuperUser
from adminapi.serializers import (
    CompanySyncStatusSerializer,
    SyncJobSerializer,
    SyncJobTriggerSerializer,
)
from companies.models import Company
from registers.models import CompanySyncStatus, SyncJob
from registers.services import sync_engine
from registers.services.focus_mode import (
    ALL_KNOWN_QUEUES,
    enter_focus_mode,
    exit_focus_mode,
    focus_mode_status,
)

logger = logging.getLogger(__name__)


class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    """List + retrieve SyncJob rows. Mutations happen via the action endpoints."""

    queryset = SyncJob.objects.all().select_related("triggered_by")
    serializer_class = SyncJobSerializer
    permission_classes = [IsAdminStaff]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if status_filter := params.get("status"):
            qs = qs.filter(status=status_filter)
        if job_type := params.get("job_type"):
            qs = qs.filter(job_type=job_type)
        return qs.order_by("-queued_at")

    def create(self, request, *args, **kwargs):
        """POST /api/admin/sync/jobs/ → create + dispatch a new job."""
        ser = SyncJobTriggerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        job_type = ser.validated_data["job_type"]
        params = ser.validated_data.get("parameters", {}) or {}
        notes = ser.validated_data.get("notes", "")

        if job_type in sync_engine.RUZ_JOB_TYPES:
            job, created = sync_engine.enqueue_ruz_job(
                job_type=job_type,
                parameters=params,
                triggered_by_id=request.user.id,
                triggered_via="admin_ui",
                notes=notes,
            )
            if not created:
                return Response(SyncJobSerializer(job).data, status=status.HTTP_200_OK)
        else:
            job = sync_engine.enqueue_job(
                job_type=job_type,
                parameters=params,
                triggered_by_id=request.user.id,
                triggered_via="admin_ui",
                notes=notes,
            )
        # Dispatch the underlying Celery task. Many job types map onto existing tasks;
        # we stay defensive — if a dispatcher isn't wired yet, the job stays queued
        # and the operator sees it in the UI.
        try:
            _dispatch_job(job)
        except Exception as exc:
            sync_engine.fail_job(job, error=f"Dispatch failed: {exc}")
        return Response(SyncJobSerializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        job = self.get_object()
        sync_engine.pause_job(job, reason=request.data.get("reason", ""))
        return Response(SyncJobSerializer(SyncJob.objects.get(pk=job.pk)).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        job = self.get_object()
        if job.job_type in sync_engine.RUZ_JOB_TYPES:
            return Response(
                {"detail": "RUZ jobs cannot be resumed by redispatch. Start a new tracked run after reviewing its saved cursor."},
                status=status.HTTP_409_CONFLICT,
            )
        SyncJob.objects.filter(pk=job.pk).update(status="running")
        try:
            _dispatch_job(SyncJob.objects.get(pk=job.pk))
        except Exception as exc:
            sync_engine.fail_job(job, error=f"Resume dispatch failed: {exc}")
        return Response(SyncJobSerializer(SyncJob.objects.get(pk=job.pk)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.job_type in sync_engine.RUZ_JOB_TYPES:
            return Response(
                {"detail": "RUZ jobs cannot be terminated because that can interrupt persisted imports."},
                status=status.HTTP_409_CONFLICT,
            )
        sync_engine.cancel_job(job, reason=request.data.get("reason", ""))
        if job.celery_task_id:
            try:
                from backend.celery import app as celery_app

                celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
            except Exception:
                pass
        return Response(SyncJobSerializer(SyncJob.objects.get(pk=job.pk)).data)

    @action(detail=True, methods=["post"], url_path="retry-failed")
    def retry_failed(self, request, pk=None):
        """Re-run this job's type.

        It used to read the failed `SyncJobItem` rows of this job and pass their
        keys to the new job as `retry_keys`. Both halves were fiction: no task
        ever wrote an item (its only writer was a decorator applied to nothing),
        so the list was always empty, and **nothing has ever read `retry_keys`
        anyway** -- the parameter was written into `parameters` and ignored by
        every consumer. The endpoint therefore did exactly one real thing, and
        it is the thing it still does: enqueue another job of the same type,
        carrying this job's parameters.

        The per-company failure record does exist, but it is keyed by source
        rather than by job: `CompanySyncStatus.consecutive_failures`. Retrying
        *those* is a real feature and a different one -- for `insurance_batch`
        it would mean re-running tens of thousands of companies that the source
        has already refused -- so it is not being introduced here by a rename.
        """
        job = self.get_object()
        new_job = sync_engine.enqueue_job(
            job_type=job.job_type,
            parameters={**(job.parameters or {})},
            triggered_by_id=request.user.id,
            triggered_via="admin_ui",
            notes=f"Re-run of job #{job.pk} ({job.job_type})",
        )
        try:
            _dispatch_job(new_job)
        except Exception as exc:
            sync_engine.fail_job(new_job, error=f"Dispatch failed: {exc}")
        return Response(SyncJobSerializer(new_job).data, status=status.HTTP_201_CREATED)


class _SyncStatusPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class CompanySyncStatusViewSet(viewsets.ReadOnlyModelViewSet):
    # One row per company per source, so this table is as large as the book is:
    # 111 071 rows when the admin screen was finally wired up, split across
    # `vszp` and `social` (54 007 each), `orsr` and `financials`. Unpaginated,
    # the endpoint answered with all of them at once -- a response the browser
    # cannot render and, at `-consecutive_failures`, one whose first page was
    # 49 430 rate-limited insurance rows with the interesting ones at the end.
    queryset = CompanySyncStatus.objects.all().select_related("company")
    serializer_class = CompanySyncStatusSerializer
    permission_classes = [IsAdminStaff]
    pagination_class = _SyncStatusPagination

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if source := params.get("source"):
            qs = qs.filter(source=source)
        if params.get("has_errors") in ("1", "true", "True"):
            qs = qs.filter(consecutive_failures__gt=0)
        if params.get("blocked") in ("1", "true", "True"):
            qs = qs.filter(is_blocked=True)
        if params.get("has_detail") in ("1", "true", "True"):
            # The default ordering sorts by `-consecutive_failures`, which puts
            # exactly the companies that *have* something to say at the bottom:
            # a company whose statements were read and none recorded is an
            # answered attempt, so its failure count is 0. Without this filter
            # the field is reachable only by paging to the end.
            qs = qs.exclude(last_detail="")
        return qs.order_by("-consecutive_failures", "-last_attempted_at")

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        obj = self.get_object()
        sync_engine.block_company(
            company_id=obj.company_id,
            source=obj.source,
            reason=request.data.get("reason", ""),
        )
        return Response(CompanySyncStatusSerializer(CompanySyncStatus.objects.get(pk=obj.pk)).data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        obj = self.get_object()
        sync_engine.unblock_company(company_id=obj.company_id, source=obj.source)
        return Response(CompanySyncStatusSerializer(CompanySyncStatus.objects.get(pk=obj.pk)).data)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """Reset retry counter and dispatch a single-company sync."""
        obj = self.get_object()
        CompanySyncStatus.objects.filter(pk=obj.pk).update(
            consecutive_failures=0, next_retry_at=None
        )
        try:
            _dispatch_single_company(obj.source, obj.company_id)
        except Exception as exc:
            return Response({"detail": f"Dispatch failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"detail": "queued"})


# ---------------------------------------------------------------------------
# Focus mode
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def focus_mode_state(request):
    return Response(focus_mode_status())


@api_view(["POST"])
@permission_classes([IsAdminStaff])
def enter_focus_mode_view(request):
    state = enter_focus_mode(user=request.user)
    return Response({"active": state.active, "snapshot_size": len(state.snapshot or [])})


@api_view(["POST"])
@permission_classes([IsAdminStaff])
def exit_focus_mode_view(request):
    state = exit_focus_mode(user=request.user)
    return Response({"active": state.active})


# ---------------------------------------------------------------------------
# Queue depths
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def queue_depths_view(request):
    """Return current pending message count per known queue (Redis LLEN equivalent)."""
    from backend.celery import app as celery_app

    depths: dict[str, int | None] = {}
    try:
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            for q in sorted(ALL_KNOWN_QUEUES):
                try:
                    _, count, _ = channel.queue_declare(queue=q, passive=True)
                    depths[q] = count
                except Exception:
                    depths[q] = None
    except Exception:
        # A broker connection failure carries the connection URL in its own
        # message, and REDIS_URL may embed a password -- so the detail goes to
        # the log. The client is told which dependency is down, not its DSN.
        logger.exception("queue_depths_view: could not reach the broker")
        return Response(
            {"error": "Nepodarilo sa spojiť s brokerom frontu.", "queues": depths},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response({"queues": depths})


# ---------------------------------------------------------------------------
# Periodic / scheduled tasks
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def scheduled_tasks_view(request):
    from django_celery_beat.models import PeriodicTask

    rows = []
    for pt in PeriodicTask.objects.all().select_related("interval", "crontab"):
        rows.append({
            "id": pt.id,
            "name": pt.name,
            "task": pt.task,
            "enabled": pt.enabled,
            "interval": str(pt.interval) if pt.interval_id else None,
            "crontab": str(pt.crontab) if pt.crontab_id else None,
            "queue": pt.queue,
            "last_run_at": pt.last_run_at,
            "total_run_count": pt.total_run_count,
            "args": pt.args,
            "kwargs": pt.kwargs,
        })
    return Response({"results": rows})


@api_view(["POST"])
@permission_classes([IsAdminStaff])
def toggle_scheduled_task_view(request, pk: int):
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    pt = get_object_or_404(PeriodicTask, pk=pk)
    pt.enabled = not pt.enabled
    pt.save(update_fields=["enabled"])
    PeriodicTasks.update_changed()
    return Response({"id": pt.id, "enabled": pt.enabled})


# ---------------------------------------------------------------------------
# Internal: map job_type -> Celery dispatch
# ---------------------------------------------------------------------------


def _dispatch_job(job: SyncJob) -> None:
    """Translate a SyncJob into a Celery task call, capturing the task id."""
    job_type = job.job_type
    params = job.parameters or {}

    # Lazy import to avoid circulars at module load.
    from registers import tasks

    task_map = {
        "ruz_full": (tasks.start_full_ruz_sync, {"reset": params.get("reset", False), "sync_job_id": job.pk}),
        "ruz_full_firmy": (tasks.fetch_ruz_data_firmy_only, {"sync_job_id": job.pk}),
        "ruz_full_szco": (tasks.fetch_ruz_data_szco_only, {"sync_job_id": job.pk}),
        "ruz_incremental": (tasks.start_incremental_sync, {"sync_job_id": job.pk}),
        # `sync_job_id` is not optional here. Every other RUZ entry point passes
        # it, and this one did not: the job row this view had just created was
        # handed to a task that called the command directly and never claimed
        # it. A `queued` row is exactly what `reg_s_one_active_ruz_job` holds,
        # so the row stayed `queued` for ever and every later RUZ run met the
        # constraint, got this job back and returned without dispatching --
        # including the keeper's own resume. `_run_ruz_command` claims what it
        # is given; the id is how it gets there.
        # No default for `start_id`. It used to default to `0`, which is not a
        # sentinel the command can tell from a real start point: `0 is not None`,
        # so `--start-id=0` was appended and the command's own resume branch --
        # the one that reads the stored cursor -- became unreachable from here.
        # The trigger panel sends no parameters at all, so every admin-started
        # repair re-walked the register from RUZ id 0. `None` is what reaches the
        # command now, and `None` is what it already understood.
        "ruz_repair": (tasks.start_repair_sync, {
            "start_id": params.get("start_id"),
            "workers": params.get("workers", 3),
            "sync_job_id": job.pk,
        }),
        "orsr_batch": (tasks.schedule_missing_orsr_sync, {"limit": params.get("limit", 200)}),
        "financials_batch": (tasks.schedule_ruz_financials_sync, {
            "limit": params.get("limit", 200),
            "eligible_only": params.get("eligible_only", True),
            "missing_only": params.get("missing_only", True),
        }),
        "insurance_batch": (tasks.schedule_insurance_debt_checks, {}),
        "fs_update": (tasks.update_fs_data_task, {}),
    }
    if job_type not in task_map:
        raise ValueError(f"Unknown job_type: {job_type}")

    func, kwargs = task_map[job_type]
    async_result = func.apply_async(kwargs=kwargs)
    if job_type in sync_engine.RUZ_JOB_TYPES:
        SyncJob.objects.filter(pk=job.pk, status="queued").update(celery_task_id=async_result.id or "")
    else:
        sync_engine.start_job(job, total_items=params.get("total_items"), celery_task_id=async_result.id or "")


def _dispatch_single_company(source: str, company_id: int) -> None:
    from registers import tasks

    if source == "orsr":
        tasks.sync_company_orsr_data.apply_async(kwargs={"company_id": company_id})
    elif source == "financials":
        tasks.sync_company_financials_from_ruz.apply_async(kwargs={"company_id": company_id})
    elif source in ("vszp", "social"):
        tasks.update_insurance_debt.apply_async(args=[company_id])
    elif source == "ruz":
        # Refetch base RUZ — use the manual sync task that orchestrates everything.
        tasks.sync_company_now.apply_async(args=[company_id])
    else:
        raise ValueError(f"No dispatcher for source: {source}")


# ---------------------------------------------------------------------------
# One company, every source -- the "refresh this company" control
# ---------------------------------------------------------------------------

# How long one company's refresh keeps the next one out.
#
# The pass is orchestrated and long: RUZ base data, then financials and ORSR
# together, then the two insurance checks. The window has to outlast it, because
# the second click is not a second question -- the status rows the admin is
# looking at are written *by* the first pass, so a refresh that lands while it
# is still running spends the same five requests to race its own result.
COMPANY_REFRESH_COOLDOWN_SECONDS = 900


def company_refresh_plan(company: Company) -> dict:
    """What a full refresh of `company` will ask, and what it will not.

    Read from the same predicates the tasks themselves read, so the answer
    cannot drift from the work: `orchestrate_full_company_sync` asks ORSR only
    for an eligible company, and `update_insurance_debt` does not make the
    request for a source an admin has blocked. Both refusals are *reported*
    rather than quietly dropped -- a refresh that skips a source in silence is
    the control that looks configured and decides nothing, which is the failure
    this repository keeps finding.
    """
    from registers.eligibility import is_orsr_eligible_company
    from registers.tasks import INSURANCE_SOURCES

    blocked = set(
        CompanySyncStatus.objects.filter(
            company_id=company.pk, source__in=INSURANCE_SOURCES, is_blocked=True
        ).values_list("source", flat=True)
    )

    dispatched = [CompanySyncStatus.SOURCE_RUZ, CompanySyncStatus.SOURCE_FINANCIALS]
    skipped: list[dict] = []

    if is_orsr_eligible_company(company):
        dispatched.append(CompanySyncStatus.SOURCE_ORSR)
    else:
        skipped.append({"source": CompanySyncStatus.SOURCE_ORSR, "reason": "not_eligible"})

    # Declared order, not sorted: the tuple is written as "VšZP, Sociálna
    # poisťovňa" and the response is read as a list of sources, so keeping the
    # order keeps the two readings of it the same.
    for source in INSURANCE_SOURCES:
        if source in blocked:
            skipped.append({"source": source, "reason": "blocked"})
        else:
            dispatched.append(source)

    # The block is honoured unevenly and the response says so, rather than
    # letting an admin infer otherwise from a list that looks complete. It is
    # read in three places -- `sync_due_q` keeps a blocked row out of the
    # *rotation*, `sync_due_q`'s sibling keeps it out of the insurance batch,
    # and `update_insurance_debt` refuses to make the request at all -- but
    # neither `orchestrate_full_company_sync` nor `sync_company_orsr_data`
    # consults the flag. So a blocked RUZ, financials or ORSR row is asked
    # anyway, and the admin who blocked it should be told that here.
    asked_while_blocked = list(
        CompanySyncStatus.objects.filter(
            company_id=company.pk, is_blocked=True, source__in=dispatched
        )
        .order_by("source")
        .values_list("source", flat=True)
    )

    return {
        "dispatched": dispatched,
        "skipped": skipped,
        "blocked_but_asked": asked_while_blocked,
    }


def _refresh_cooldown_remaining(lock_key: str, now) -> int:
    """Seconds left on a live claim, or the whole window if it cannot be read.

    The stored value is the moment of dispatch, so the wait can be *stated*
    instead of rounded up to the full window: "skús to o 15 minút" for a pass
    that started 14 minutes ago is the kind of number that teaches an admin to
    stop reading the number.
    """
    try:
        stored = cache.get(lock_key)
        elapsed = (now - datetime.fromisoformat(stored)).total_seconds()
    except Exception:
        # Either the read failed or the stored value is not something this view
        # wrote. Both take the same answer for the same reason: what is being
        # produced is a wait for an admin to plan around, and the full window is
        # the only value that cannot be wrong in the direction of promising a
        # refresh that will not run. It is not a decision about whether to run
        # one -- `cache.add` returned False microseconds ago, so the refresh is
        # already in flight.
        return COMPANY_REFRESH_COOLDOWN_SECONDS
    return max(1, int(COMPANY_REFRESH_COOLDOWN_SECONDS - elapsed))


@api_view(["POST"])
@permission_classes([IsAdminStaff])
def company_refresh_view(request, company_id: int):
    """POST /api/admin/companies/<id>/refresh/ -- re-read one company, every source.

    Staff-only, and enforced *here* rather than only in the UI that hides the
    button. The company page is public -- `CompanyViewSet` is `AllowAny` and
    `/firma/:ico` sits outside `ProtectedRoute` -- so a control placed on it is
    reachable by anonymous traffic, and this is the one endpoint that would let
    a visitor name a company and spend the scrapers' budget on it. Those sources
    are rate-limited under "riziko banu" (see the queue comments in
    `settings.py`), and the `orsr` queue this joins is shared with the RPO
    person-history backfill behind a two-slot worker. No other endpoint in the
    project dispatches Celery work to a non-staff caller, and this is not the
    one to start with.

    Deliberately *not* a `SyncJob`. The orchestrated task never claims one, so a
    row created here would sit `queued` for ever and `make ops-check` would fail
    it as a job whose worker never came -- an alarm about a row nothing was ever
    going to move. The visible result of a refresh is the per-source
    `CompanySyncStatus` rows the pass rewrites, which is what the admin was
    looking at when they clicked.
    """
    company = get_object_or_404(Company, pk=company_id)
    lock_key = f"company-refresh:{company_id}"
    started = timezone.now()

    # Read before the claim, not after: it is two small queries and nothing
    # depends on winning the claim, while a failure *after* claiming would hold
    # the window open on a refresh that never started.
    plan = company_refresh_plan(company)

    try:
        claimed = cache.add(lock_key, started.isoformat(), COMPANY_REFRESH_COOLDOWN_SECONDS)
    except Exception as exc:
        # Reported, not swallowed. Without the cache there is no de-duplication,
        # and a silent fallback would turn one click into as many passes as it
        # was clicked -- so the refresh does not run. The queue needs the same
        # Redis, so this is not a state in which dispatching would have worked.
        return Response(
            {"detail": f"Cache nedostupná, obnovenie sa nespustilo: {exc}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not claimed:
        return Response(
            {
                "detail": "already_running",
                "retry_after_seconds": _refresh_cooldown_remaining(lock_key, started),
            },
            status=status.HTTP_409_CONFLICT,
        )

    plan = company_refresh_plan(company)

    from registers import tasks

    try:
        tasks.orchestrate_full_company_sync.apply_async(args=[company_id])
    except Exception as exc:
        # The claim is released rather than kept: it exists to stop a second
        # pass, and a dispatch that never happened is not one. Held, it would
        # make a broker outage look like a company that had just been refreshed.
        cache.delete(lock_key)
        return Response(
            {"detail": f"Dispatch failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY
        )

    logger.info(
        "Admin %s started a full refresh of company_id=%s ico=%s (asked: %s; skipped: %s)",
        request.user.id,
        company_id,
        company.ico,
        ",".join(plan["dispatched"]),
        ",".join(item["source"] for item in plan["skipped"]) or "-",
    )
    return Response(
        {
            "company_id": company_id,
            "ico": company.ico,
            **plan,
            "cooldown_seconds": COMPANY_REFRESH_COOLDOWN_SECONDS,
        }
    )
