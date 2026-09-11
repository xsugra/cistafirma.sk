# Observability

How to see what the stack is doing: structured logs, the Prometheus metrics
endpoint, and the optional local dashboards. Nothing here changes data — every
control in this document is read-only.

## Logging

All backend/worker output is one JSON object per line on stdout
(`LOG_FORMAT=json`, default). Set `LOG_FORMAT=text` for classic human-readable
lines, and `LOG_LEVEL` to `DEBUG|INFO|WARNING|ERROR|CRITICAL` (default `INFO`).
Both are validated at startup: an invalid value aborts the process rather than
silently falling back.

```bash
make docker-logs            # everything
make docker-logs-backend    # gunicorn
make docker-logs-celery     # every worker + beat
```

### Request log

`core.middleware.RequestLogMiddleware` is first in `MIDDLEWARE`, so it times the
whole chain and logs one line per request through the `cistafirma.request`
logger: `method`, `path`, `status`, `duration_ms`, `user_id`. Level follows the
status (`>=500` ERROR, `>=400` WARNING, else INFO). `/healthz`, `/metrics` and
`/static/` are skipped: the Docker HEALTHCHECK and the Prometheus scrape are
constant background probes and must not dominate the log or the counters.

`django.server` is pinned to WARNING and `django.request` to ERROR, so 4xx/5xx
have exactly one source and 5xx still carries its traceback (as `exc_info`).

### Task correlation

Celery 5 only adds `task_id`/`task_name` through its own formatter, so
`core.logging.CeleryTaskFilter` (attached to the console handler) pulls them from
`celery._state` and every record logged while a task runs — including from the
app loggers the task calls — carries them. A record's own
`extra={'task_id': ...}` always wins. Non-task threads are left untouched.

### Retention

Every long-running service uses the `x-logging` anchor (`json-file`,
`max-size: 20m`, `max-file: 5`), so container logs are capped at ~100 MB each
instead of growing without bound.

## Metrics

### Endpoint and access control

`GET /metrics` on the backend exposes the Prometheus text format. It is **not
public** and must not be made public. The backend port is bound to loopback by
default, but `BIND_HOST=0.0.0.0` deliberately re-exposes it, so the endpoint
keeps its own guard rather than relying on the binding:

- Default: only loopback and private/RFC1918 clients receive metrics. Note this
  admits **any** private address — on a shared LAN, `BIND_HOST=0.0.0.0` makes
  `/metrics` readable by every neighbour, which is one of the reasons the
  default binding is loopback. Set `METRICS_TOKEN` if the port is ever exposed.
- With `METRICS_TOKEN` set, a bearer token is required instead:
  `Authorization: Bearer <token>` (compared in constant time).
- Everyone else gets **404**, never 403 — an unauthorised caller learns nothing
  about whether the endpoint exists.
- `X-Forwarded-For` is deliberately **not** trusted; honouring a client-supplied
  header would defeat the guard.
- `METRICS_ENABLED=false` disables the endpoint (still a 404).
- If `prometheus_client` is missing from the image, `/metrics` returns **503**
  with an explanatory body. This is intentional: the app keeps running (Celery
  workers run a Django system check at startup and must not die over an
  exporter), but the scrape target reports as down instead of silently
  exporting nothing.

```bash
make metrics | head -20
```

### What is exported

| Metric | Type | Labels |
|---|---|---|
| `cistafirma_http_requests_total` | counter | `method`, `path`, `status` |
| `cistafirma_http_request_duration_seconds` | histogram | `method`, `path` |
| `unknown_legal_form_codes_total` | counter | `code`, `source` |

The `path` label is normalized before use: numeric, UUID and long hex segments
collapse to `:id`, segments over 64 characters to `:other`, and the number of
distinct paths is capped (200), after which new paths label as `:other`. Without
this, `/api/companies/<ico>/` would create one time series per company. The
request *log* keeps the raw path — only the metric label is normalized.

`unknown_legal_form_codes_total` is defined in `companies/models.py`; its series
appears the first time an unrecognised legal-form code is actually seen.

### gunicorn multiprocess mode

The backend runs more than one gunicorn worker, and each worker is a separate
process. Without `PROMETHEUS_MULTIPROC_DIR` every worker exports its own
counters, so consecutive scrapes alternate between workers (3, 3, 5, 3 …) and
Prometheus reads the drops as counter resets — making `rate()` meaningless.
The variable is therefore set **on the backend service only**, and:

- `core/metrics.py` aggregates with `MultiProcessCollector` when it is set.
- `backend/gunicorn.conf.py` wipes the directory in `on_starting`, i.e. in the
  master before any worker forks, so a previous run's files (named by worker
  pid) cannot keep contributing frozen values.
- Files of workers that exit mid-run are deliberately kept: that is what keeps
  the exported totals monotonic.

Celery containers do not set it — they have no scrape target and must not share
the directory.

### Broker-side queue depth

`/metrics` cannot see the broker, so queue backlog is reported by
`make ops-check` instead — it prints the depth of every Celery queue and warns
past `CISTAFIRMA_QUEUE_WARN_DEPTH`. Nothing else in the stack exposes this, and
a queue that has silently stopped draining is otherwise indistinguishable from
one that is merely busy. See `docs/DATA_PROTECTION.md` for the gate as a whole.

### Sync jobs

Depth measures load, and for the same reason it cannot answer whether an
*import* is still moving. A job whose worker died keeps its `running` row and a
frozen `last_heartbeat` for ever: the queue behind it can look healthy while
nothing in it will ever be processed. That is not hypothetical — SyncJob #3
(`ruz_full_firmy`) sat `running` from 2026-08-25 22:30:52 with its heartbeat
frozen at that same instant and `processed_items=0`, and
`adminapi/views/dashboard.py:35` counted it as an active job for **15 days**.

The reaper for exactly this, `detect_and_fail_stuck_jobs()` in
`registers/services/sync_engine.py`, had been referenced only at its own
definition across the whole repository — never scheduled, no management command,
no tests — while the module docstring already claimed "heartbeat watchdog flips
it to `failed` after staleness". Two things now close that gap:

- `detect-stuck-sync-jobs-every-10-min` in `CELERY_BEAT_SCHEDULE` (the schedule
  now has 7 entries) runs `registers.tasks.detect_stuck_sync_jobs` on the
  `celery` queue every 600 s, expires 550 s — on `celery` rather than `ruz_full`
  so the reaper can never wait behind the backlog it is meant to notice. It
  flips a `running` job to `failed` once its heartbeat is past the staleness
  threshold.
- `python manage.py sync_health`
  (`backend/registers/management/commands/`) is a read-only report the gate
  chains: a table of active and recent jobs, then `Sync jobs: N unmet`, exiting
  1 when anything is unmet. See `docs/DATA_PROTECTION.md`.

`sync_health` judges exactly three conditions: a `running` job whose heartbeat is
past the staleness threshold, a `queued` job older than `--queued-minutes`
(`CISTAFIRMA_QUEUED_JOB_MINUTES`, default 720) that was never claimed, and the
newest run of a `triggered_via='beat_schedule'` job type that ended `failed`
within `CISTAFIRMA_FAILED_JOB_HOURS` (default 24). The third covers the one
failure nobody is watching: a run that dies in the beat has no operator in
front of it, so before this the table showed the failed row while the verdict
still read `0 unmet`. It is judged on the *newest* attempt, so a later
successful run clears it rather than leaving the gate red for a transient
failure. Counters
are printed but never judged — how many items a job *should* process depends on
the run, not on its type, so no threshold would be honest. The report and the
reaper both ask `is_stuck()` in `registers/services/sync_engine.py` for the
verdict instead of re-deriving it, so the gate cannot disagree with the watchdog.

`CISTAFIRMA_STUCK_HEARTBEAT_MINUTES` (default **30**) sets that threshold. It
had been a hard-coded 10-minute constant that nothing called, and it could not
simply be switched on: `last_heartbeat` was written only by `record_item`, which
only the per-company `tracked_sync_task` tasks (orsr / financials / insurance)
called — and that decorator was applied to **no task at all**, so the field was
in practice never written by anything, and a healthy multi-hour resync was
indistinguishable from a dead one. Both the decorator and `record_item` have
since been deleted; the RUZ management command now beats explicitly, which is
what the watchdog rests on. `RuzApi` bounds the other side of
that risk — explicit request timeouts (30 s for the changed-IDs page) plus a
retry session with 4 attempts (`backend/registers/integrations/ruz_api.py:18-19`)
— so a stalled run ends within minutes rather than hanging for ever.

### Known limitations

- Counter values are per *container*. With `BACKEND_WORKERS` > 1 they are
  correctly aggregated across gunicorn workers; they are not aggregated across
  replicated backend containers, because Prometheus scrapes one address.
- Celery workers export no metrics (no HTTP endpoint). Task-level metrics would
  need a separate exporter.
- The `process_*`/`python_*` collectors are only exported when the multiprocess
  directory is unset (tests, `runserver`, management commands); under gunicorn
  they would be one worker's view, so they are excluded.

## Optional monitoring stack

Prometheus + Grafana run under the `monitoring` compose profile, which means a
plain `docker compose up` never starts them.

```bash
make docker-metrics-up      # start both
make docker-metrics-down    # stop both (volumes are kept)
```

| Service | URL | Notes |
|---|---|---|
| Prometheus | http://127.0.0.1:9090 | scrapes `backend:8000/metrics` every 15s, 15d retention |
| Grafana | http://127.0.0.1:3000 | `admin` / `cistafirma`, unless `GRAFANA_ADMIN_PASSWORD` is set |

Both ports are published on **loopback only** — the UIs are never exposed to the
LAN. Grafana provisions its Prometheus datasource and a `CistaFirma Overview`
dashboard (request rate by status, p95 latency, 5xx ratio, top paths, unknown
legal-form codes) from `deploy/monitoring/`. No alerting rules are provisioned.

Do **not** use `docker compose down` to stop this stack: that verb is on this
repository's never-run list and would also stop the database. Use `stop`.

## Not implemented: error tracking

External error tracking (Sentry and similar) is deliberately not wired up. The
existing `sentry_sdk` hook in `companies/models.py` stays inert because shipping
stack traces that contain company data to a third party conflicts with this
repository's data-protection posture. Any future error tracking should be either
self-hosted (e.g. GlitchTip, Sentry-compatible API) or explicitly approved, and
disabled by default.
