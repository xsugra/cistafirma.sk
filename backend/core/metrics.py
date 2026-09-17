"""Prometheus metrics for the backend, plus the internal-only /metrics endpoint.

Metrics are registered in the default ``prometheus_client`` registry so that
counters defined elsewhere in the codebase
(``companies.models.UNKNOWN_LEGAL_FORM_CODE_COUNT``) and the standard
process/python collectors are all exported by a single scrape.

The endpoint is deliberately NOT public. The backend port is published to the
host, so ``/metrics`` is limited to loopback/private clients -- or to a caller
presenting ``METRICS_TOKEN`` as a bearer token -- and answers 404 (never 403) to
everyone else so it does not advertise its own existence. ``X-Forwarded-For``
is intentionally NOT trusted: honouring a client-supplied header would defeat
the guard entirely.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import re
import threading

from django.conf import settings
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger("cistafirma.metrics")

# The whole prometheus_client API is imported defensively. This module is
# reachable from ROOT_URLCONF, and Celery workers run a Django system check at
# startup, so a hard import here would kill every worker over an exporter they
# never use — and the container image is a separate build step from the
# bind-mounted code, so code/image drift is a real failure mode in this repo.
# A missing library therefore degrades to a 503 on /metrics: loud at the scrape
# (Prometheus reports the target as down) without taking the app with it.
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )

    METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover - only on a broken/unbuilt image
    METRICS_AVAILABLE = False
    logger.warning(
        "prometheus_client is not installed; /metrics will report 503 and no "
        "request metrics will be recorded."
    )

if METRICS_AVAILABLE:
    # --- Exposition registry -------------------------------------------------
    # Under gunicorn every worker is a separate process. With
    # PROMETHEUS_MULTIPROC_DIR set (see docker-compose.yml + gunicorn.conf.py)
    # the counter values live in memory-mapped files shared by all workers, and
    # only MultiProcessCollector can aggregate them; exposing the default
    # REGISTRY would return a single worker's view. Without the variable (tests,
    # runserver, management commands) the default registry is correct and
    # additionally carries the process/python collectors.
    #
    # Read-only here on purpose. `prometheus_client` chose its value class when
    # it was first imported, which happens before this module is reached (the
    # first metric in any Django process is built at import time by
    # `companies.models`), so by now the choice is frozen and nothing in this
    # file could change it. The variable is settled once, from `settings.py`,
    # through `core/prometheus_env.py` -- including the empty-value case, where
    # the library's presence test and this truthiness test would otherwise
    # disagree. This line only asks which mode is in force.
    _MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

    if _MULTIPROC_DIR:
        from prometheus_client.multiprocess import MultiProcessCollector

        _EXPOSITION_REGISTRY: CollectorRegistry = CollectorRegistry()
        MultiProcessCollector(_EXPOSITION_REGISTRY)
    else:
        _EXPOSITION_REGISTRY = REGISTRY

    HTTP_REQUESTS_TOTAL = Counter(
        "cistafirma_http_requests_total",
        "HTTP requests handled, by method, normalized path and status code.",
        ["method", "path", "status"],
    )

    HTTP_REQUEST_DURATION = Histogram(
        "cistafirma_http_request_duration_seconds",
        "HTTP request latency in seconds, by method and normalized path.",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
else:
    _EXPOSITION_REGISTRY = None
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION = None

# --- Path normalization ------------------------------------------------------
# Raw request paths carry identifiers (/api/companies/12345678/), which would
# create one time series per company and eventually exhaust memory. Any
# identifier-shaped segment collapses to a fixed placeholder.
_NUMERIC = re.compile(r"^\d+$")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_HEX = re.compile(r"^[0-9a-fA-F]{16,}$")

_ID = ":id"
_OTHER = ":other"

# Hard cap on distinct normalized paths. Normalization already bounds the
# realistic route set; this bounds it against a scanner probing random URLs,
# which would otherwise grow the label space without limit.
_MAX_TRACKED_PATHS = 200
_tracked_paths: set[str] = set()
_tracked_lock = threading.Lock()

API_NOT_FOUND = {"detail": "Not Found"}


def normalize_path(path: str) -> str:
    """Collapse identifier-shaped segments so label cardinality stays bounded."""
    if not path:
        return "/"

    segments = []
    for segment in path.split("/"):
        if not segment:
            segments.append(segment)
        elif _NUMERIC.match(segment) or _UUID.match(segment) or _LONG_HEX.match(segment):
            segments.append(_ID)
        elif len(segment) > 64:
            segments.append(_OTHER)
        else:
            segments.append(segment)

    normalized = "/".join(segments)
    return normalized if normalized.startswith("/") else "/" + normalized


def _bounded_path(normalized: str) -> str:
    """Return the path to label with, collapsing anything past the cap."""
    with _tracked_lock:
        if normalized in _tracked_paths:
            return normalized
        if len(_tracked_paths) >= _MAX_TRACKED_PATHS:
            return _OTHER
        _tracked_paths.add(normalized)
    return normalized


def metrics_enabled() -> bool:
    return bool(getattr(settings, "METRICS_ENABLED", True))


def record_request(method: str, path: str, status: int,
                   duration_seconds: float) -> None:
    """Record one served request.

    Instrumentation must never break a request, so every failure here is
    swallowed (and logged at DEBUG only).
    """
    if not (METRICS_AVAILABLE and metrics_enabled()):
        return
    try:
        label_path = _bounded_path(normalize_path(path))
        label_method = (method or "UNKNOWN").upper()
        HTTP_REQUESTS_TOTAL.labels(
            method=label_method, path=label_path, status=str(status)
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=label_method, path=label_path
        ).observe(duration_seconds)
    except Exception:
        logger.debug("Failed to record request metrics", exc_info=True)


# --- Endpoint access control -------------------------------------------------
def is_internal_client(remote_addr: str | None) -> bool:
    """Whether a request came from loopback, a private or a link-local address.

    Public because it is the repo's answer to "may this caller be told what
    broke" -- `/metrics` uses it to decide whether to exist, and `/healthz`
    uses it to decide whether the body may name the exception behind a
    degraded dependency. One place decides that, so the two cannot drift.
    """
    if not remote_addr:
        return False
    try:
        address = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def _is_authorized(request) -> bool:
    """A bearer token, when configured; otherwise private/loopback clients only."""
    token = os.getenv("METRICS_TOKEN", "").strip()
    if token:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):].strip(), token)
    return is_internal_client(request.META.get("REMOTE_ADDR"))


def metrics_view(request):
    """Export metrics, or 404 for anyone not entitled to know this exists."""
    if request.method != "GET" or not metrics_enabled() or not _is_authorized(request):
        return JsonResponse(API_NOT_FOUND, status=404)

    if not METRICS_AVAILABLE:
        # 503, not 404: the target is supposed to exist, so let Prometheus mark
        # it down rather than quietly scrape nothing.
        return HttpResponse(
            "# prometheus_client is not installed in this image\n",
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    return HttpResponse(
        generate_latest(_EXPOSITION_REGISTRY), content_type=CONTENT_TYPE_LATEST
    )
