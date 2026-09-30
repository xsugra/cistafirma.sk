"""Expose the operational health verdicts as Prometheus metrics.

`sync_health`, `source_health` and `beat_health` answer the three questions
`make ops-check` is built from, but they answer them to a shell script on a
schedule. This command serves the same verdicts -- through
`registers.services.ops_health`, the one place the rules live -- in the
Prometheus text format, so a dashboard can show them and an alert can fire on
them without anyone re-implementing a rule and drifting.

Three properties matter more than the metrics themselves.

**Every declared subject is always present, and only a failure is `fail`.**
`cistafirma_ops_subject` carries exactly one series per declared subject -- a
source, a job type, a beat entry -- with `status` one of `ok`, `fail` or
`not_judged`. Emitting only the failures is forbidden: a series that vanishes
reads as healthy, which is the same defect `source_health`'s vocabulary fix
addressed in text. A source with no rows and a job type with no runs are
therefore series that say `not_judged`, never absent series. `not_judged` is
not `ok`: Focus Mode switching a source off, a live full RUZ walk superseding
an incremental window, a switched-off beat entry -- collapsing any of those
into `ok` would make this exporter red on a documented operator action, and
collapsing them into `fail` would make it red for one.

**`cistafirma_ops_unmet{domain}` is the gate's own number.** It is
`Report.unmet` -- the count of `fail` verdicts -- which is exactly the count
`ops_check.sh` adds to its failure total from the summary line, so the metric
and the text gate can never disagree about how many controls are unmet.

**A raising evaluator takes down its own domain and nothing else.** Each domain
is evaluated inside its own guard: a domain that raises contributes no series
and sets `cistafirma_ops_scrape_ok` to 0, and the other two are still served.
A domain that raised is never reported as `ok` -- it is reported as *absent*,
which Prometheus marks stale, plus the scrape-level flag. That is deliberate:
`cistafirma_ops_scrape_ok 0` is the one series that means "this endpoint is
lying to you about something", and the dashboard panels say so.

`evaluate_source_health` is TTL-cached behind `--cache-seconds` (default 60).
It aggregates `CompanySyncStatus` -- one row per company per source, up to
~1.5M rows -- plus a query per source, and running that on every 15 s scrape
would be a database-load change on production rather than a monitoring change.
The other two domains are cheap and run per scrape.
`cistafirma_ops_evaluated_timestamp_seconds` records when each domain was last
*really* evaluated, so a wedged evaluator (or a cache that keeps being served)
shows up as a growing `time() - timestamp` instead of looking fresh.

Read-only: every query it issues is a SELECT, and Focus Mode is read without
creating its singleton row. The server is single-threaded on purpose -- one
thread means one database connection, and `close_old_connections()` before each
scrape keeps it from accumulating Postgres backends.

Run it beside the stack (its own compose service, published on loopback like
every other port here) and scrape `http://<host>:9101/metrics`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django_celery_beat.models import PeriodicTask
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)
from prometheus_client import values as _prom_values

from registers.services import ops_health

# `prometheus_client` chooses its value implementation once, at import, from
# `PROMETHEUS_MULTIPROC_DIR` -- a variable this stack sets for gunicorn, and one
# that reaches this process through the same `.env`. It must not apply here, and
# the reason is not tidiness: this command builds a fresh registry on every
# scrape, so multiprocess values would write a file per series per scrape into
# the directory the *backend's* `/metrics` reads, and the backend would start
# publishing the exporter's series as its own. Forcing the single-process
# implementation is a no-op when the variable is unset -- which is when it is
# already the value that would have been chosen.
_prom_values.ValueClass = _prom_values.MutexValue

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 9101
DEFAULT_CACHE_SECONDS = 60

METRIC_SUBJECT = "cistafirma_ops_subject"
METRIC_UNMET = "cistafirma_ops_unmet"
METRIC_EVALUATED = "cistafirma_ops_evaluated_timestamp_seconds"
METRIC_SCRAPE_OK = "cistafirma_ops_scrape_ok"
METRIC_HEARTBEAT_AGE = "cistafirma_sync_job_heartbeat_age_seconds"
METRIC_BEAT_AGE = "cistafirma_beat_entry_age_seconds"
METRIC_SOURCE_COMPANIES = "cistafirma_source_companies"

DOC_SUBJECT = (
    "Operational health of one declared subject: 1 for the status it is in. "
    "Exactly one series per subject is always present; fail is the only status "
    "that counts towards cistafirma_ops_unmet."
)
DOC_UNMET = (
    "Failed verdicts in this domain -- the same number the matching management "
    "command prints as 'unmet' and exits non-zero for."
)
DOC_EVALUATED = (
    "Unix time of this domain's last real evaluation. A value that stops "
    "advancing means the evaluator or its cache is wedged."
)
DOC_SCRAPE_OK = (
    "1 when every domain evaluated, 0 when any evaluator raised. A domain that "
    "raised serves no series at all and is never reported as ok."
)
DOC_HEARTBEAT_AGE = (
    "Age of the last sign of life of a running sync job, per job type. The "
    "watchdog's own staleness threshold is what makes it a failure."
)
DOC_BEAT_AGE = (
    "Age of the last run of a beat entry whose interval is readable, per entry. "
    "Rows with no readable interval and rows that never ran carry no sample."
)
DOC_SOURCE_COMPANIES = (
    "Companies a source attempted and succeeded on inside the window, per "
    "declared source. Both states are emitted for every source, including the "
    "ones with no rows."
)


@dataclass
class _DomainState:
    """One domain's last evaluation, cached or not."""

    report: "ops_health.Report | None" = None
    subjects: tuple[str, ...] = ()
    evaluated_at: float = 0.0
    error: str = ""


class OpsReportCache:
    """A TTL cache per domain, so a cheap domain is never held back.

    The lock makes "evaluate at most once concurrently" true even if a future
    caller serves this from a threaded server: without it two simultaneous
    scrapes would run the expensive source aggregation twice, which is the
    database-load change the cache exists to avoid.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, _DomainState] = {}

    def get(self, domain: str, *, ttl_seconds: float, loader) -> _DomainState:
        with self._lock:
            now = time.time()
            state = self._states.get(domain)
            fresh = (
                state is not None
                and state.report is not None
                and ttl_seconds > 0
                and (now - state.evaluated_at) < ttl_seconds
            )
            if fresh:
                return state
            try:
                report, subjects = loader()
            except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
                # Reported rather than logged and forgotten: the domain serves
                # no series (so Prometheus marks the old ones stale) and
                # `cistafirma_ops_scrape_ok` goes to 0. A domain that raised
                # must not read as ok.
                state = _DomainState(
                    report=None,
                    subjects=(),
                    evaluated_at=now,
                    error=f"{type(exc).__name__}: {exc}",
                )
            else:
                state = _DomainState(
                    report=report,
                    subjects=tuple(subjects),
                    evaluated_at=time.time(),
                    error="",
                )
            self._states[domain] = state
            return state

    def forget(self) -> None:
        with self._lock:
            self._states.clear()


def _thresholds_from_env() -> dict[str, int]:
    """The same thresholds the three commands default to from the environment.

    Read here rather than passed as flags so that this exporter and the gate it
    mirrors cannot be configured apart: both read the container's environment.
    """
    return {
        "queued_minutes": ops_health.env_int(
            "CISTAFIRMA_QUEUED_JOB_MINUTES", ops_health.DEFAULT_QUEUED_MINUTES
        ),
        "failed_job_hours": ops_health.env_int(
            "CISTAFIRMA_FAILED_JOB_HOURS", ops_health.DEFAULT_FAILED_JOB_HOURS
        ),
        "window_max_age_days": ops_health.env_int(
            "CISTAFIRMA_SYNC_WINDOW_DAYS", ops_health.DEFAULT_WINDOW_MAX_AGE_DAYS
        ),
        "window_hours": ops_health.env_int(
            "CISTAFIRMA_SOURCE_WINDOW_HOURS", ops_health.DEFAULT_WINDOW_HOURS
        ),
        "min_attempts": ops_health.env_int(
            "CISTAFIRMA_SOURCE_MIN_ATTEMPTS", ops_health.DEFAULT_MIN_ATTEMPTS
        ),
        "min_successes": ops_health.env_int(
            "CISTAFIRMA_SOURCE_MIN_SUCCESSES", ops_health.DEFAULT_MIN_SUCCESSES
        ),
        "grace_minutes": ops_health.env_int(
            "CISTAFIRMA_BEAT_GRACE_MINUTES", ops_health.DEFAULT_GRACE_MINUTES
        ),
    }


def _load_sync(thresholds: dict[str, int]):
    return (
        ops_health.evaluate_sync_health(
            queued_minutes=thresholds["queued_minutes"],
            failed_job_hours=thresholds["failed_job_hours"],
            window_max_age_days=thresholds["window_max_age_days"],
        ),
        ops_health.declared_sync_subjects(),
    )


def _load_source(thresholds: dict[str, int]):
    return (
        ops_health.evaluate_source_health(
            window_hours=thresholds["window_hours"],
            min_attempts=thresholds["min_attempts"],
            min_successes=thresholds["min_successes"],
        ),
        ops_health.declared_source_subjects(),
    )


def _load_beat(thresholds: dict[str, int]):
    # No registry_loader: the "the task it names is not registered" sentence
    # decorates a verdict the exporter already has, and reading the registry
    # costs a full task-module import on every refresh.
    report = ops_health.evaluate_beat_health(
        grace_minutes=thresholds["grace_minutes"]
    )
    subjects = list(
        PeriodicTask.objects.order_by("name").values_list("name", flat=True)
    )
    return report, subjects


def _loaders(thresholds: dict[str, int]):
    """The three domains: (domain, loader, cache seconds)."""
    return (
        (ops_health.DOMAIN_SYNC, lambda: _load_sync(thresholds), 0),
        (ops_health.DOMAIN_SOURCE, lambda: _load_source(thresholds), None),
        (ops_health.DOMAIN_BEAT, lambda: _load_beat(thresholds), 0),
    )


_PROCESS_CACHE = OpsReportCache()


def collect_metrics(
    *,
    cache_seconds: float = DEFAULT_CACHE_SECONDS,
    cache: OpsReportCache | None = None,
    thresholds: dict[str, int] | None = None,
) -> tuple[bytes, bool]:
    """The Prometheus text body, and whether every domain evaluated.

    Exposed as a function rather than only as a handler method so the series it
    produces can be asserted on without starting a server -- which is how the
    tests check that a source with no rows still gets a series.
    """
    if cache is None:
        cache = _PROCESS_CACHE
    if thresholds is None:
        thresholds = _thresholds_from_env()

    close_old_connections()

    registry = CollectorRegistry()
    subject = Gauge(METRIC_SUBJECT, DOC_SUBJECT, ["domain", "subject", "status"], registry=registry)
    unmet = Gauge(METRIC_UNMET, DOC_UNMET, ["domain"], registry=registry)
    evaluated = Gauge(METRIC_EVALUATED, DOC_EVALUATED, ["domain"], registry=registry)
    scrape_ok = Gauge(METRIC_SCRAPE_OK, DOC_SCRAPE_OK, registry=registry)
    heartbeat_age = Gauge(METRIC_HEARTBEAT_AGE, DOC_HEARTBEAT_AGE, ["job_type"], registry=registry)
    beat_age = Gauge(METRIC_BEAT_AGE, DOC_BEAT_AGE, ["task"], registry=registry)
    source_companies = Gauge(
        METRIC_SOURCE_COMPANIES, DOC_SOURCE_COMPANIES, ["source", "state"], registry=registry
    )

    every_domain_ok = True

    for domain, loader, ttl in _loaders(thresholds):
        ttl_seconds = cache_seconds if ttl is None else ttl
        state = cache.get(domain, ttl_seconds=ttl_seconds, loader=loader)
        if state.report is None:
            every_domain_ok = False
            continue

        report = state.report
        status_by_subject = report.status_by_subject()

        # The declared vocabulary first, then anything the verdicts add (an
        # incremental window's sync type is not a job type), so no subject the
        # evaluator judged can be missing from the series set.
        subjects = list(state.subjects)
        seen = set(subjects)
        for verdict in report.verdicts:
            if verdict.subject not in seen:
                seen.add(verdict.subject)
                subjects.append(verdict.subject)
        for name in subjects:
            status = status_by_subject.get(name, ops_health.STATUS_NOT_JUDGED)
            subject.labels(domain=domain, subject=name, status=status).set(1)

        unmet.labels(domain=domain).set(report.unmet)
        evaluated.labels(domain=domain).set(state.evaluated_at)

        if domain == ops_health.DOMAIN_SYNC:
            # One sample per job type: several verdicts can share a subject (a
            # stuck run beside a healthy one), and the worst -- the largest age
            # -- is the honest reading of a gauge that is alerted on.
            ages: dict[str, float] = {}
            for verdict in report.verdicts:
                value = verdict.values.get("heartbeat_age_seconds")
                if value is None:
                    continue
                ages[verdict.subject] = max(ages.get(verdict.subject, 0.0), float(value))
            for job_type, value in ages.items():
                heartbeat_age.labels(job_type=job_type).set(value)
        elif domain == ops_health.DOMAIN_BEAT:
            ages = {}
            for verdict in report.verdicts:
                value = verdict.values.get("age_seconds")
                if value is None:
                    continue
                # `task` is the beat entry's name: it is the row's unique key,
                # so two entries can never collapse into one series, and it is
                # the name this stack's operators use for an entry.
                ages[verdict.subject] = max(ages.get(verdict.subject, 0.0), float(value))
            for entry, value in ages.items():
                beat_age.labels(task=entry).set(value)
        elif domain == ops_health.DOMAIN_SOURCE:
            for verdict in report.verdicts:
                values = verdict.values
                source_companies.labels(source=verdict.subject, state="attempted").set(
                    float(values.get("attempted", 0))
                )
                source_companies.labels(source=verdict.subject, state="succeeded").set(
                    float(values.get("succeeded", 0))
                )

    scrape_ok.set(1 if every_domain_ok else 0)
    return generate_latest(registry), every_domain_ok


class _MetricsHandler(BaseHTTPRequestHandler):
    """Serves the scrape; anything but `/metrics` is a 404."""

    server_version = "CistaFirmaOps/1.0"

    def do_GET(self):  # noqa: N802 -- BaseHTTPRequestHandler's own naming
        if self.path.split("?")[0] not in ("/metrics", "/"):
            self.send_error(404, "Not Found")
            return

        try:
            body, _ok = collect_metrics(
                cache_seconds=self.server.cache_seconds,  # type: ignore[attr-defined]
                cache=self.server.cache,  # type: ignore[attr-defined]
            )
        except Exception:  # noqa: BLE001 -- the endpoint must stay up
            # Anything that escapes `collect_metrics` is this process being
            # unable to answer, and the honest body for that is
            # `scrape_ok 0` -- not a 500 that leaves the previous scrape
            # standing as if it were current.
            registry = CollectorRegistry()
            Gauge(METRIC_SCRAPE_OK, DOC_SCRAPE_OK, registry=registry).set(0)
            body = generate_latest(registry)

        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 -- stdlib signature
        # The stack's logs are structured JSON on stdout; a line per scrape here
        # would be noise proportional to the scrape interval.
        pass


class Command(BaseCommand):
    help = (
        "Serve the sync / source / beat health verdicts in Prometheus text "
        "format for as long as the process runs. Read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bind",
            default=DEFAULT_BIND,
            help=(
                "Address to listen on (default: 0.0.0.0). The compose service "
                "is expected to publish the port on loopback only, like every "
                "other port in this stack."
            ),
        )
        parser.add_argument(
            "--port",
            type=int,
            default=DEFAULT_PORT,
            help="Port to listen on (default: 9101).",
        )
        parser.add_argument(
            "--cache-seconds",
            type=int,
            default=DEFAULT_CACHE_SECONDS,
            help=(
                "How long a source_health evaluation may be reused "
                "(default: 60). It aggregates one row per company per source, "
                "so evaluating it on every 15s scrape is a database-load "
                "change rather than a monitoring change. 0 evaluates always."
            ),
        )

    def handle(self, *args, **options):
        bind = options["bind"]
        port = options["port"]
        cache_seconds = options["cache_seconds"]

        server = HTTPServer((bind, port), _MetricsHandler)
        server.cache = OpsReportCache()
        server.cache_seconds = cache_seconds

        self.stdout.write(
            f"ops exporter listening on http://{bind}:{port}/metrics "
            f"(source_health cached {cache_seconds}s)"
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            self.stdout.write("ops exporter stopped")
