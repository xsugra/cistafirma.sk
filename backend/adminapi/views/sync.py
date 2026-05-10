"""Sync management endpoints: jobs, per-company status, focus mode, queues."""
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from adminapi.permissions import IsAdminStaff, IsSuperUser
from adminapi.serializers import (
    CompanySyncStatusSerializer,
    SyncJobItemSerializer,
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

    @action(detail=True, methods=["get"])
    def items(self, request, pk=None):
        job = self.get_object()
        items_qs = job.items.all().order_by("-id")
        if item_status := request.query_params.get("status"):
            items_qs = items_qs.filter(status=item_status)
        page = self.paginate_queryset(items_qs)
        ser = SyncJobItemSerializer(page or items_qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    def create(self, request, *args, **kwargs):
        """POST /api/admin/sync/jobs/ → create + dispatch a new job."""
        ser = SyncJobTriggerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        job_type = ser.validated_data["job_type"]
        params = ser.validated_data.get("parameters", {}) or {}
        notes = ser.validated_data.get("notes", "")

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
        SyncJob.objects.filter(pk=job.pk).update(status="running")
        try:
            _dispatch_job(SyncJob.objects.get(pk=job.pk))
        except Exception as exc:
            sync_engine.fail_job(job, error=f"Resume dispatch failed: {exc}")
        return Response(SyncJobSerializer(SyncJob.objects.get(pk=job.pk)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
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
        """Spawn a new job from the failed items of this one."""
        job = self.get_object()
        failed_keys = list(job.items.filter(status="failed").values_list("item_key", flat=True))
        new_job = sync_engine.enqueue_job(
            job_type=job.job_type,
            parameters={**(job.parameters or {}), "retry_keys": failed_keys},
            triggered_by_id=request.user.id,
            triggered_via="admin_ui",
            notes=f"Retry of failed items from job #{job.pk}",
        )
        try:
            _dispatch_job(new_job)
        except Exception as exc:
            sync_engine.fail_job(new_job, error=f"Dispatch failed: {exc}")
        return Response(SyncJobSerializer(new_job).data, status=status.HTTP_201_CREATED)


class CompanySyncStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CompanySyncStatus.objects.all().select_related("company")
    serializer_class = CompanySyncStatusSerializer
    permission_classes = [IsAdminStaff]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if source := params.get("source"):
            qs = qs.filter(source=source)
        if params.get("has_errors") in ("1", "true", "True"):
            qs = qs.filter(consecutive_failures__gt=0)
        if params.get("blocked") in ("1", "true", "True"):
            qs = qs.filter(is_blocked=True)
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
    except Exception as exc:
        return Response({"error": str(exc), "queues": depths}, status=status.HTTP_502_BAD_GATEWAY)
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
        "ruz_full": (tasks.start_full_ruz_sync, {"reset": params.get("reset", False)}),
        "ruz_incremental": (tasks.start_incremental_sync, {}),
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
    sync_engine.start_job(job, total_items=params.get("total_items"))
    async_result = func.apply_async(kwargs=kwargs)
    SyncJob.objects.filter(pk=job.pk).update(celery_task_id=async_result.id or "")


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
