"""Request access-log middleware (structured, to stdout, never to DB).

Placed FIRST in MIDDLEWARE: measures the whole chain including Django's own
exception handling, and request.user is available (resolved by inner layers)
when the response returns.

Health, scrape and static traffic is skipped entirely (_SKIP_EXACT /
_SKIP_PREFIXES): the Docker HEALTHCHECK hits /healthz and Prometheus hits
/metrics every 15s, and monitoring must not dominate the telemetry it feeds —
neither the request log nor the counters, which are fed from this same single
observation point.
"""

from __future__ import annotations

import logging
import time

from core import metrics

logger = logging.getLogger("cistafirma.request")

_SKIP_EXACT = {"/healthz", "/healthz/", "/metrics", "/metrics/"}
_SKIP_PREFIXES = ("/static/",)


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if path in _SKIP_EXACT or path.startswith(_SKIP_PREFIXES):
            return self.get_response(request)

        method = request.method or ""
        started = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            # Only exceptions from inner middleware reach here; view exceptions
            # are already converted to 500 responses by Django's BaseHandler.
            self._log(
                method, path, 500,
                (time.perf_counter() - started) * 1000, request,
            )
            raise
        self._log(
            method, path,
            getattr(response, "status_code", 0),
            (time.perf_counter() - started) * 1000,
            request,
        )
        return response

    def _log(self, method: str, path: str, status: int,
             duration_ms: float, request) -> None:
        if status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        # Best-effort user id; guarded so a lazy user lookup failure never
        # breaks the request.
        user_id = None
        try:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                user_id = getattr(user, "pk", None)
        except Exception:
            user_id = None

        logger.log(
            level,
            f"{method} {path} -> {status} ({duration_ms:.1f} ms)",
            extra={
                "event": "request",
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "user_id": user_id,
            },
        )

        # Prometheus counters are labelled with the *normalized* path (the log
        # line above keeps the raw one); record_request never raises.
        metrics.record_request(method, path, status, duration_ms / 1000.0)
