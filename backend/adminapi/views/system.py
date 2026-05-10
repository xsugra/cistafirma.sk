"""System health + version info."""
import os
import sys

import django
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from adminapi.permissions import IsAdminStaff


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def system_health_view(request):
    health = {"db": "unknown", "redis": "unknown", "celery_workers": 0}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        health["db"] = "ok"
    except Exception as exc:
        health["db"] = f"error: {exc}"

    try:
        from backend.celery import app as celery_app

        inspect = celery_app.control.inspect(timeout=1.5)
        active = inspect.active() if inspect else None
        if active is not None:
            health["celery_workers"] = len(active)
            health["redis"] = "ok"
    except Exception as exc:
        health["redis"] = f"error: {exc}"

    return Response(health)


@api_view(["GET"])
@permission_classes([IsAdminStaff])
def system_info_view(request):
    return Response({
        "django_version": django.get_version(),
        "python_version": sys.version,
        "environment": os.environ.get("DJANGO_ENV", "dev"),
        "deployed_commit": os.environ.get("GIT_COMMIT", "unknown"),
        "settings_module": os.environ.get("DJANGO_SETTINGS_MODULE", ""),
    })
