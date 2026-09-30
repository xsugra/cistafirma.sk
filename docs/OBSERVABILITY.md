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
past a per-queue bound: `CISTAFIRMA_QUEUE_WARN_DEPTH` (default 50000) for the
queues that drain to zero, and `CISTAFIRMA_QUEUE_WARN_DEPTH_INSURANCE` (default
144000, ten ticks of drain capacity) for the insurance queue, whose depth is
conserved by design rather than drained. Nothing else in the stack exposes this,
and a queue that has silently stopped draining is otherwise indistinguishable
from one that is merely busy. See `docs/DATA_PROTECTION.md` for the gate as a
whole, and for why the insurance bound is the one that differs.

### Beat schedule

Queue depth and job rows all read what a *run* left behind, so none of them can
see a schedule entry that has stopped firing — and a task that never runs writes
nothing anywhere. `compute-sector-benchmarks-daily` sat like that for 32 h with
an entry, a row and an admin listing, and the gate stayed green.

`python manage.py beat_health`
(`backend/registers/management/commands/`) is chained by the gate for exactly
that: it judges each `PeriodicTask` row's own `last_run_at` against that row's
own interval, printing `Beat schedule: N unmet` and exiting 1 when an enabled
entry is past its interval plus `CISTAFIRMA_BEAT_GRACE_MINUTES` (default 15).
It is the one control that judges the *absence* of a run. What it deliberately
does not judge, and why, is in `docs/DATA_PROTECTION.md`.

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

- `detect-stuck-sync-jobs-every-10-min` in `CELERY_BEAT_SCHEDULE` runs
  `registers.tasks.detect_stuck_sync_jobs` on the
  `celery` queue every 600 s, expires 550 s — on `celery` rather than `ruz_full`
  so the reaper can never wait behind the backlog it is meant to notice. It
  flips a `running` job to `failed` once its heartbeat is past the staleness
  threshold.
- `python manage.py sync_health`
  (`backend/registers/management/commands/`) is a read-only report the gate
  chains: a table of active and recent jobs, then `Sync jobs: N unmet`, exiting
  1 when anything is unmet. See `docs/DATA_PROTECTION.md`.

`sync_health` judges **four** conditions: a `running` job whose heartbeat is
past the staleness threshold, a `queued` job older than `--queued-minutes`
(`CISTAFIRMA_QUEUED_JOB_MINUTES`, default 720) that was never claimed, the
newest run of a `triggered_via='beat_schedule'` job type that ended `failed`
within `CISTAFIRMA_FAILED_JOB_HOURS` (default 24), and an incremental sync
window that has stopped moving — `SyncProgress.zmenene_od` older than
`--window-max-age-days` (`CISTAFIRMA_SYNC_WINDOW_DAYS`, default 3), which is a
*state* rather than a volume and so is exactly what a volume threshold cannot
see. (This paragraph said "exactly three" for some time after the fourth was
added; the module docstring, which begins "Four conditions fail a job", was
right and this was not.) The third covers a failure
with no operator in front of it: a run that dies in the beat, so before this the
table showed the failed row while the verdict still read `0 unmet`. (The other
such failure — an entry that never fires at all, which leaves no failed row
either — is Beat schedule above.) It is judged on the *newest* attempt, so a later
successful run clears it rather than leaving the gate red for a transient
failure. The fourth is not judged at all while Focus Mode has the run switched
off or a full walk holds the window — those two states make the age meaningless
rather than stale, and both print `--` instead of a verdict. Counters
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

#### Per-item progress inside a job: what it would take

The deleted `SyncJobItem` was an attempt at this and is worth recording so the
next attempt starts from the diagnosis rather than from the same idea. It held
**zero** rows for its whole life, and the reason was structural, not a bug in
the model: its only writer was a decorator applied to no task, and no task ever
had a *reason* to report into a job — nothing passed a `SyncJob` id down to a
per-company Celery task.

Reinstating it is new work with three parts, and all three are needed:

1. **The parent job has to exist.** A fan-out scheduler (`schedule_missing_orsr_sync`,
   `schedule_ruz_financials_sync`, `orchestrate_full_company_sync`) must create
   one `SyncJob` for the batch — the `ruz_full` path already does this via
   `enqueue_ruz_job`; the others create none, which is why the 12:22 RUZ run
   reporting to `SyncProgress` was stored as `processed_items=0`.
2. **The id has to be carried to every child.** Each per-company task takes
   `job_id` as an argument and records its own row against it. This is the part
   that costs: it changes a task signature that the beat, the admin dispatcher
   and `companies/admin.py` all call.
3. **Something has to read it.** `SyncJobs.tsx` shows counts, not items; the
   `items` endpoint the deleted serializer fed was never called by the frontend.
   A per-item table nobody opens is the same defect one layer up.

Until all three exist, per-company attempts are recorded where they already are
and where the gate actually reads them: `CompanySyncStatus`, one row per company
per source, written by `record_ruz_date_outcome`, `record_orsr_outcome` and
`sync_company_and_record`.

### Known limitations

- Counter values are per *container*. With `BACKEND_WORKERS` > 1 they are
  correctly aggregated across gunicorn workers; they are not aggregated across
  replicated backend containers, because Prometheus scrapes one address.
- Celery workers export no metrics (no HTTP endpoint), and this is still true.
  The `ops_exporter` in the Optional monitoring stack below exports the *health
  gates' verdicts* about those workers, which is not the same thing: it says
  whether a job is stuck, not how many tasks ran. Task-level metrics would need
  an exporter inside the workers themselves.
- The `process_*`/`python_*` collectors are only exported when the multiprocess
  directory is unset (tests, `runserver`, management commands); under gunicorn
  they would be one worker's view, so they are excluded.
- **Nothing here detects an API outage on its own.** `/metrics` describes what
  the backend did with the requests it received; it cannot report requests that
  never arrived because nginx could not reach the backend — during the
  2026-09-17 outage the scrape target itself stayed up and reported normally.
  The outside-in check in `make ops-check` exists to cover exactly that, and it
  is a weekly-and-by-hand gate, not an alert. The alerting added to the Optional
  monitoring stack does not change this: every one of those rules reads
  Prometheus, which read this endpoint normally throughout the outage. See "The
  gap that is still open" there.

## Optional monitoring stack

Prometheus + Grafana run under the `monitoring` compose profile, which means a
plain `docker compose up` never starts them.

```bash
make docker-metrics-up      # start the whole stack
make docker-metrics-down    # stop it (volumes are kept)
```

| Service | URL | Notes |
|---|---|---|
| Prometheus | http://127.0.0.1:9090 | 15 s scrape, 15 d retention |
| Grafana | http://127.0.0.1:3000 | `admin` / `cistafirma`, unless `GRAFANA_ADMIN_PASSWORD` is set |

Both ports are published on **loopback only** — the UIs are never exposed to the
LAN. The exporters publish no port at all: Prometheus reaches them by Docker DNS
name over the compose network, which is deliberate, because none of them has an
auth layer.

Six scrape targets, in `deploy/monitoring/prometheus/prometheus.yml`:

| Job | What it is |
|---|---|
| `prometheus` | self-scrape |
| `cistafirma-backend` | the app's own `/metrics` — HTTP counters and the duration histogram |
| `node` | node_exporter on **both** hosts (`dell` and `sam-lenovo`), by tailnet IP |
| `postgres` | `postgres_exporter`, using the same interpolated credentials the app uses |
| `redis` | `redis_exporter`, with `--check-keys` so the Celery queues' list lengths appear |
| `cistafirma-ops` | the operational verdicts — see below |

### The operational verdicts (`cistafirma-ops`)

Whether a sync job is stuck, whether a source stopped advancing, whether a beat
entry is overdue: those are **judgements**, not measurements, and they cannot be
expressed as a PromQL rule over the counters the backend exports. So they are not
re-implemented here. `backend/registers/services/ops_health.py` holds them, the
three management commands render that module's `Report` for a human, and
`manage.py run_ops_exporter` serves it as metrics from the `ops_exporter`
service (the backend image, port 9101, no published port).

That shared module is the point: **the alert and `make ops-check` cannot
disagree, because they read the same verdict twice.** The `Sync jobs: N unmet` /
`Source health: N unmet` / `Beat schedule: N unmet` summary lines and the
`not_judged` (`--`) states are a contract `scripts/local/ops_check.sh` parses by
regex, so they survive the refactor unchanged.

Two properties are worth knowing before you trust a panel:

- `cistafirma_ops_subject` carries **exactly one series per declared subject**,
  with a `status` label. Subjects come from the models' choice lists, never from
  the rows that happen to exist, so a source with no data is a series saying
  `not_judged` rather than a series that is absent. A series that vanishes reads
  as healthy, which is the failure this whole file is about.
- The source domain aggregates `CompanySyncStatus` (a row per company per
  source, up to ~1.5M) and is therefore **cached inside the exporter**. Prometheus
  scrapes it every 30 s, but the number may be up to a cache interval old;
  `cistafirma_ops_evaluated_timestamp_seconds` says how fresh it actually is.

  Measured on dell 2026-10-01, so the cache is *not* read as a scrape-timeout
  guard: the three commands take 2.13 / 2.39 / 2.15 s wall clock from the host
  (`sync_health` / `source_health` / `beat_health`), but running `manage.py check`
  — Django's start-up, touching no table — takes **1.94 s** of that. Inside the
  exporter the interpreter is already up, so a scrape that re-evaluates all three
  domains costs roughly **0.3 s** against Prometheus's 10 s scrape timeout. The
  60 s cache on the source domain buys database load, nothing else; if it is ever
  removed, latency is not what will break.

### Alerting

Ten rules live in `deploy/monitoring/grafana/provisioning/alerting/` and are
evaluated by **Grafana's unified alerting**, not by Prometheus — so
`prometheus.yml` stays a pure scrape configuration and needs no `rule_files`.
Delivery is Telegram, through the `telegram` contact point and the single root
notification policy in that directory. `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` come from the root `.env`; create the bot with @BotFather,
send it a message, then read the chat id from
`https://api.telegram.org/bot<token>/getUpdates`.

Three things about these files are not obvious:

- **The `folder:` name is matched by name and created if absent.** Alert rule
  provisioning takes no `folderUid`, so Grafana creates a missing `CistaFirma`
  folder itself and gives it a generated UID. That is why the rules provision
  on a fresh volume — and why you must *not* try to pin that folder's UID
  elsewhere. Alerting is provisioned **before** dashboards, so a dashboard
  provider that pinned a folder UID with the same name would collide on the
  unique-name constraint and take the whole provisioning service down (Grafana
  exits 1 and restart-loops). `provisioning/dashboards/dashboards.yml` sets
  `folder: ""` on purpose, so the dashboards land in **General** and no UID is
  pinned anywhere. The rules sitting in `CistaFirma` while the dashboard sits in
  `General` is the intended, harmless consequence of that.
- **Grafana reads alerting provisioning files at start-up**, not on a timer
  (dashboards, by contrast, are re-read every 30 s by their provider). After
  editing anything under `provisioning/alerting/`, restart Grafana:
  `docker compose restart grafana` — `restart`, never `--force-recreate`, which
  is what keeps `db` and `redis` untouched.
- **Nothing verifies that alerts are delivered, and nothing can.** Grafana
  interpolates `$VAR` in provisioning files and substitutes the **empty string**
  for an unset variable rather than failing, so a missing token provisions a
  contact point that looks perfectly healthy and sends nothing. The only test is
  to send a message: press **Test** on the contact point in Grafana and watch the
  chat. `make ops-check` does not check this and does not pretend to. Do that
  once after setting the token, and again if the token is ever rotated.

The rules cover: any scrape target down; the exporter's verdicts going stale; an
evaluator inside the exporter raising; sync jobs unmet; the beat schedule
overdue; source health unmet; both Celery queue shapes (the queues that drain to
zero, and `insurance`, which is conserved by design and needs its own bound);
an elevated 5xx ratio; and a host filesystem below 15% — on `dell` that last one
is the disk holding the only copy of the production database.

### The gap that is still open

The 2026-09-17 outage — 3 h 43 min of 502s — is why this stack grew alerting.
It is worth being precise about what now covers it and what does not.

What covers it: the operational layer above, which would have reported the
backend's own health and the queue and schedule behaviour within minutes.

What does not: **an outside-in API outage is still not alerted on.** Every rule
above reads Prometheus, and Prometheus reads the backend's `/metrics` — which
stayed up and reported normally throughout that outage, because it describes
what the backend did with requests it received, not requests that never arrived.
Availability is asserted instead by `scripts/local/ops_check.sh`, whose **API
availability** section GETs `/api/stats/landing/` through the frontend's
*published* port from the host and requires a 200 — a path that includes nginx,
the exact component whose stale upstream address caused the outage, and one that
a running, healthy frontend does not make pass on its own (`/healthz` answered
200 for the whole of it). What it proves is deliberately bounded: that the API
answers, not that its answers are right — correctness is the sync-jobs and
source-health sections' verdict. It is a weekly and by-hand gate, not an alert.
Closing that properly needs a blackbox probe Prometheus can scrape, which is not
in this stack today.

Do **not** use `docker compose down` to stop this stack: that verb is on this
repository's never-run list and would also stop the database. Use `stop`.

## Not implemented: error tracking

External error tracking (Sentry and similar) is deliberately not wired up. The
existing `sentry_sdk` hook in `companies/models.py` stays inert because shipping
stack traces that contain company data to a third party conflicts with this
repository's data-protection posture. Any future error tracking should be either
self-hosted (e.g. GlitchTip, Sentry-compatible API) or explicitly approved, and
disabled by default.
