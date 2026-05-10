"""AuditLogMiddleware: records every non-GET admin API request to AuditLog.

Mounted in MIDDLEWARE *after* AuthenticationMiddleware so request.user is set.
Only paths starting with `/api/admin/` are logged.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

LOGGED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PATH_PREFIX = "/api/admin/"
MAX_PAYLOAD_BYTES = 8000  # truncate huge bodies


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _safe_body_snapshot(request) -> dict:
    """Read a parsed JSON body if available, else fall back to raw string."""
    try:
        body = request.body[:MAX_PAYLOAD_BYTES]
        if not body:
            return {}
        try:
            data = json.loads(body)
        except Exception:
            data = {"_raw": body.decode("utf-8", errors="replace")}
        # Strip obvious secrets.
        if isinstance(data, dict):
            for key in list(data.keys()):
                if any(s in key.lower() for s in ("password", "token", "secret", "authorization")):
                    data[key] = "***"
        return data
    except Exception:
        return {}


def _action_for(request) -> str:
    """Best-effort action name from method + path tail."""
    parts = [p for p in request.path.replace(PATH_PREFIX, "", 1).strip("/").split("/") if p]
    method = request.method.lower()
    if not parts:
        return f"admin.{method}"
    head = parts[0]
    tail = parts[-1] if len(parts) > 1 else ""
    if tail and not tail.isdigit():
        return f"{head}.{tail}"
    return f"{head}.{method}"


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Snapshot inputs BEFORE the view runs so we can record even on 4xx/5xx.
        is_admin = request.path.startswith(PATH_PREFIX)
        method = request.method
        if is_admin and method in LOGGED_METHODS:
            payload = _safe_body_snapshot(request)
            ip = _client_ip(request)
            ua = request.META.get("HTTP_USER_AGENT", "")[:1000]
            action = _action_for(request)
        else:
            payload = None

        response = self.get_response(request)

        if payload is not None:
            try:
                from registers.models import AuditLog

                user = getattr(request, "user", None)
                AuditLog.objects.create(
                    actor=user if (user and user.is_authenticated) else None,
                    action=action,
                    method=method,
                    path=request.path[:255],
                    status_code=getattr(response, "status_code", None),
                    payload=payload,
                    ip_address=ip,
                    user_agent=ua,
                )
            except Exception:
                logger.exception("AuditLogMiddleware: failed to persist audit row")
        return response
