"""Dashboard metrics endpoints — aggregate KPIs across the platform."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from adminapi.permissions import IsAdminStaff
from companies.models import Company, CompanyFinancialResult
from registers.models import (
    AuditLog,
    CompanySyncStatus,
    OrsrCompanyProfile,
    SyncJob,
)

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def dashboard_overview(request):
    """High-level KPI cards for the main admin landing page."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(datum_zrusenia__isnull=True).count()
    with_orsr = OrsrCompanyProfile.objects.count()
    with_financials = CompanyFinancialResult.objects.values("company_id").distinct().count()

    active_jobs = SyncJob.objects.filter(status__in=["queued", "running"]).count()
    failed_jobs_24h = SyncJob.objects.filter(status="failed", completed_at__gte=last_24h).count()
    completed_jobs_24h = SyncJob.objects.filter(status="completed", completed_at__gte=last_24h).count()

    failures_24h = CompanySyncStatus.objects.filter(
        last_attempted_at__gte=last_24h, consecutive_failures__gt=0
    ).count()
    blocked = CompanySyncStatus.objects.filter(is_blocked=True).count()

    total_users = User.objects.count()
    active_users_7d = User.objects.filter(last_login__gte=last_7d).count()

    # Best-effort revenue — sum of plan price * users per plan.
    try:
        from subscriptions.models import SubscriptionPlan

        mrr = float(
            User.objects.exclude(subscription_plan__isnull=True)
            .values("subscription_plan")
            .annotate(n=Count("id"))
            .aggregate(total=Sum("subscription_plan__price_eur"))["total"]
            or 0
        )
    except Exception:
        mrr = 0.0

    return Response({
        "generated_at": now,
        "companies": {
            "total": total_companies,
            "active": active_companies,
            "with_orsr": with_orsr,
            "with_financials": with_financials,
            "orsr_coverage_pct": round((with_orsr / total_companies * 100) if total_companies else 0, 1),
            "financials_coverage_pct": round((with_financials / total_companies * 100) if total_companies else 0, 1),
        },
        "sync": {
            "active_jobs": active_jobs,
            "completed_jobs_24h": completed_jobs_24h,
            "failed_jobs_24h": failed_jobs_24h,
            "company_failures_24h": failures_24h,
            "blocked_companies": blocked,
        },
        "users": {
            "total": total_users,
            "active_7d": active_users_7d,
            "mrr_eur": mrr,
        },
    })


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def dashboard_sync(request):
    """Per-source coverage and throughput trends."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    total = Company.objects.count() or 1

    sources = []
    for code, label in CompanySyncStatus.SOURCE_CHOICES:
        synced = CompanySyncStatus.objects.filter(
            source=code, last_succeeded_at__isnull=False
        ).count()
        failing = CompanySyncStatus.objects.filter(
            source=code, consecutive_failures__gt=0
        ).count()
        avg_failures = CompanySyncStatus.objects.filter(source=code).aggregate(
            avg=Avg("consecutive_failures")
        )["avg"] or 0
        sources.append({
            "source": code,
            "label": label,
            "synced_count": synced,
            "coverage_pct": round(synced / total * 100, 1),
            "failing_count": failing,
            "avg_consecutive_failures": round(float(avg_failures), 2),
        })

    # Hourly throughput buckets for the last 24h (bucketed by hour of completed_at).
    completed_jobs = SyncJob.objects.filter(
        completed_at__gte=last_24h, status="completed"
    ).values("completed_at", "succeeded_items", "failed_items")

    buckets = [0] * 24
    fails_buckets = [0] * 24
    for job in completed_jobs:
        idx = 23 - int((now - job["completed_at"]).total_seconds() // 3600)
        if 0 <= idx < 24:
            buckets[idx] += job["succeeded_items"] or 0
            fails_buckets[idx] += job["failed_items"] or 0

    return Response({
        "sources": sources,
        "throughput_24h": {
            "succeeded_per_hour": buckets,
            "failed_per_hour": fails_buckets,
        },
    })


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def dashboard_business(request):
    """Business KPIs: users, plans, watchlist activity."""
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    plans_breakdown = list(
        User.objects.values("subscription_plan__slug", "subscription_plan__name")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    new_users_30d = User.objects.filter(created_at__gte=last_30d).count()
    active_30d = User.objects.filter(last_login__gte=last_30d).count()

    # Watchlist size if app is installed.
    try:
        from companies.models import Watchlist  # type: ignore

        watchlist_count = Watchlist.objects.count()
    except Exception:
        watchlist_count = None

    return Response({
        "users": {
            "total": User.objects.count(),
            "new_30d": new_users_30d,
            "active_30d": active_30d,
        },
        "plans_breakdown": plans_breakdown,
        "watchlist_count": watchlist_count,
    })


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def dashboard_system(request):
    """System health: DB, Redis, Celery worker count, queue depths, recent audit volume."""
    from django.db import connection

    health = {"db": "unknown", "redis": "unknown", "celery_workers": 0, "queues": {}}

    # DB ping
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        health["db"] = "ok"
    except Exception as exc:
        health["db"] = f"error: {exc}"

    # Redis + Celery
    try:
        from backend.celery import app as celery_app

        inspect = celery_app.control.inspect(timeout=1.5)
        active = inspect.active() if inspect else None
        if active is not None:
            health["celery_workers"] = len(active)
            health["redis"] = "ok"
    except Exception as exc:
        health["redis"] = f"error: {exc}"

    # Queue depths via Kombu.
    try:
        from registers.services.focus_mode import ALL_KNOWN_QUEUES
        from backend.celery import app as celery_app

        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            for q in sorted(ALL_KNOWN_QUEUES):
                try:
                    _, count, _ = channel.queue_declare(queue=q, passive=True)
                    health["queues"][q] = count
                except Exception:
                    health["queues"][q] = None
    except Exception:
        pass

    # Audit volume in last hour.
    last_hour = timezone.now() - timedelta(hours=1)
    audit_volume = AuditLog.objects.filter(created_at__gte=last_hour).count()

    return Response({
        "health": health,
        "audit_events_last_hour": audit_volume,
    })
