"""Sync management endpoints: jobs, per-company status, focus mode, queues."""
import logging

from django.shortcuts import get_object_or_404
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
        "ruz_repair": (tasks.start_repair_sync, {
            "start_id": params.get("start_id", 0),
            "workers": params.get("workers", 3),
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
