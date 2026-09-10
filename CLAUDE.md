# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and other AI agents
when working with code in this repository. `AGENTS.md` at the repo root points
here. **Read `docs/DATA_PROTECTION.md` before running any Docker or data
command** — this repo treats a local Docker Postgres as production data.

## Data safety rules (non-negotiable)

The Docker PostgreSQL volume `cistafirma_postgres_data` holds durable,
irreplaceable company data. Running locally in Docker IS the production
environment for this project.

- **Never** run `make docker-reset`, `docker compose down -v`, `docker volume rm`,
  or `docker volume prune`. These destroy the database volume.
- **Never** run `make celery-purge`, a full RUZ resync, or a database restore as
  a routine action. `make celery-purge` requires the explicit
  `CONFIRM_CELERY_PURGE=DELETE_PENDING_MESSAGES` token.
- **Never** restore over the running `cistafirma` database. Restore drills use an
  isolated target container.
- Before any migration, schema, or destructive-looking change: take a fresh
  verified backup (`make db-backup` + `make db-backup-verify BACKUP_FILE=...`).
- Full rules, backup procedure, RPO/RTO, and incident response: see
  `docs/DATA_PROTECTION.md`.
- A project `.claude/settings.json` denies the destructive commands above at the
  permission layer. Machine-local overrides live in `.claude/settings.local.json`
  (gitignored). Do not weaken the deny rules without explicit approval.

## Commands

### Local development (manual, venv)

```bash
make venv-create        # Create virtualenv and install Python deps
make runserver          # Django dev server on localhost:8000
make migrate            # Apply migrations (venv, uses DATABASE_URL or SQLite fallback)
make migrations         # Generate new migrations (makemigrations)
make superuser          # Create Django superuser
```

Note: outside Docker, if `DATABASE_URL` is empty the app silently falls back to
SQLite at `backend/db.sqlite3`. Inside Docker it always uses Postgres.

### Frontend

```bash
cd frontend && npm install
cd frontend && npm run dev    # Vite dev server on localhost:5173
cd frontend && npm run build  # Production build into frontend/dist/
```

Note: the Docker dev container is the canonical dependency installer (Node is
pinned in `frontend/Dockerfile` so the bundled npm 10 writes `package-lock.json`
in a stable format). Running `npm install` with a newer host npm (11.x) rewrites
the lockfile formatting and leaves the working tree dirty — prefer
`docker compose exec frontend npm install` when changing dependencies.

### Docker (preferred for full-stack; this is the production-like environment)

```bash
make docker-up          # Start all services (backend, frontend, postgres, redis, workers)
make docker-down        # Stop services (keeps volumes — do NOT add -v)
make docker-migrate     # Apply migrations via one-shot `migrate` service (NOT auto-run)
make docker-shell       # bash shell into backend container
make docker-logs        # Tail all container logs
```

`docker compose up` no longer auto-runs `migrate`. Run `make docker-migrate`
once after a fresh clone and whenever a branch adds migrations; `celery_beat`
waits until migrations are applied.

`docker-reset` exists but is volume-destructive and now token-gated; treat it as
an emergency-only tool. See Data safety rules.

The backend (`BACKEND_PORT`, default 8080) and the frontend (5173) are published
on **loopback only**, like db and redis. The frontend's Vite dev server proxies
`/api/` to the backend, so both ports have to stay bound for the stack to be
unreachable from the LAN — binding only one leaves the whole API reachable
through the other. `BIND_HOST=0.0.0.0` in `.env` re-exposes them deliberately;
do not set it on a network you do not control. `db` and `redis` ignore
`BIND_HOST` and are always loopback-bound.

Note: **each compose service with a `build:` block gets its own image tag**
(`cistafirma-backend`, `cistafirma-celery_worker_ruz`, …). `docker compose build
backend` rebuilds only the backend image, so the workers keep the old one while
their code arrives through the bind mount — a changed import then crash-loops
every worker. After changing `backend/requirements.txt`, rebuild them all:
`docker compose build backend migrate celery_beat celery_worker_ruz
celery_worker_orsr celery_worker_financials celery_worker_insurance
celery_worker_default`.

### Observability (see docs/OBSERVABILITY.md)

```bash
make metrics                # Fetch /metrics from inside the backend container
make docker-metrics-up      # Opt-in Prometheus + Grafana (monitoring profile)
make docker-metrics-down    # Stop them (volumes kept)
make docker-logs-celery     # Every worker + beat
```

Logs are structured JSON on stdout (`LOG_LEVEL`, `LOG_FORMAT`). `/metrics` is
**never public**: it answers only loopback/private clients, or a bearer
`METRICS_TOKEN` when set, and 404 for everyone else. Prometheus/Grafana only
start under the `monitoring` profile; they bind to loopback.

### Database backup / restore (see docs/DATA_PROTECTION.md)

```bash
make db-backup                                  # Fresh timestamped dump
make db-backup-verify BACKUP_FILE="<abs path>"  # Checksum + archive read check
make db-restore-drill BACKUP_FILE="<abs path>"  # Isolated restore (never live DB)
make db-backup-replicate BACKUP_FILE="<abs path>"  # Uses the recorded off-site dir
make db-offsite-status                          # Read-only off-site readiness gate
make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="<dir>"  # Record it, once
make db-backup-prune                            # Dry-run retention (newest 7 kept)
make db-backup-schedule-install                 # Weekly launchd backup job
make ops-check                                  # Every operational control, one verdict
```

`make ops-check` is the single read-only gate over the whole protection story
(stack, database, queue depths, per-source scrape health, backups, off-site
controls, drill record, and whether the weekly job is still firing). It starts no container and writes
nothing. The weekly job runs the same gate and, on failure, writes
`~/Library/Logs/CistaFirma/LAST_FAILURE`, posts a macOS notification, and exits
non-zero. See `docs/DATA_PROTECTION.md` for the two deliberate asymmetries that
keep that alert trustworthy.

The off-site path is machine-specific and lives outside the repo, in
`~/.config/cistafirma/backup.env` (mode 600), written by `db-offsite-configure`.
Every backup script reads it through `scripts/local/lib/backup_env.sh` — which
is what lets the **launchd job** replicate, since launchd starts agents with
almost no environment. An exported variable of the same name overrides the file,
so `make db-offsite-status CISTAFIRMA_OFFSITE_BACKUP_DIR=/tmp/x` still works.

Each successful `db-restore-drill` appends a record to
`~/Library/Application Support/CistaFirma/restore_drills.log`, and
`db-offsite-status` reads it back — so the documented monthly drill cadence is
checkable rather than assumed. A drill older than `CISTAFIRMA_DRILL_MAX_AGE_DAYS`
(default 30) fails the gate. `db-offsite-status` therefore reports on two things
beyond the backup files: whether a drill happened recently, and whether the
newest dump has an encrypted off-site replica.

### Testing

```bash
make test               # Full Django test suite (venv)
make companies          # Tests for companies app only
make registers          # Tests for registers app only
make users              # Tests for users app only
make analyses           # Tests for analyses app only

# Single test class or method:
venv/bin/python backend/manage.py test registers.tests.SomeTestClass
venv/bin/python backend/manage.py test registers.tests.SomeTestClass.test_method
```

Frontend tests run on **Vitest** (jsdom, `frontend/test/setup.ts`). Run them in
the container, alongside the other two checks CI runs:

```bash
docker compose exec -T frontend npm test         # vitest run
docker compose exec -T frontend npm run typecheck # tsc --noEmit
docker compose exec -T frontend npm run build     # vite build
```

GitLab CI runs exactly these (`frontend_tests`, `frontend_validate`), so a
typecheck break fails the pipeline rather than reaching a running stack.

### Celery (background workers)

```bash
make run-celery-worker           # All queues
make run-celery-worker-sync      # Data sync queues (ruz_full, orsr, financials)
make run-celery-worker-insurance # Insurance + default queue
make run-celery-beat         # Periodic task scheduler
make celery-down             # Kill all Celery processes
make celery-purge            # Flush pending tasks from Redis (token-gated)
```

### Data sync commands

```bash
make fetch-ruz               # Incremental RUZ data fetch
make fetch-ruz-full          # Full RUZ resync from 2000-01-01 (destructive of cursor; careful)
make update-fs               # Update Financna Sprava data
```

## Architecture

CistaFirma is a Slovak company registry intelligence platform. The backend is a
Django monolith exposing a REST API; the frontend is a React SPA that consumes
it. Settings live in `backend/backend/settings.py`; `backend/settings.py` is a
compat shim re-exporting it.

### Backend apps (`backend/`)

| App | Purpose |
|---|---|
| `core` | Shared helpers: constants, formatting, task utilities (`BaseSyncTask`), admin mixins, template tags |
| `users` | Custom User model (email-based auth), SimpleJWT tokens |
| `subscriptions` | Subscription plans and feature gating |
| `companies` | Core `Company` model (ICO/RUZ-keyed), search, profiles, financial results, benchmarks |
| `registers` | External data integrations: RUZ/ORSR/RPO, Financna sprava, insurance debt; sync engine, SyncJob tracking, Focus Mode |
| `connections` | Person graph: `Person`, `PersonCompanyRelation` extraction |
| `analyses` | Placeholder/stub app (no models yet) |
| `api` | Placeholder/stub app (no models yet) |
| `adminapi` | Admin API endpoints (companies, filters, sync, dashboard, audit) + audit middleware |
| `notifications` | User notifications + email (debt/status/executive changes) |
| `lead_scoring` | Lead scoring + AI enrichment (`CompanyScore`, `CompanyEnrichment`) |

### Celery task queues

| Queue | Purpose |
|---|---|
| `ruz_full` | RUZ bulk sync (sequential, holds SyncProgress/SyncJob cursor) |
| `orsr` | ORSR/RPO scraper per-company (rate-limited) |
| `financials` | RUZ financial results per-company |
| `insurance` | VSZP + Social insurance debt checks (rate-limited; one full pass takes ~15 days, so the 12 h beat interval selects what is *due*, it does not bound completion) |
| `celery` (default) | FS updates, orchestration, ad-hoc tasks |

Both a code-defined `CELERY_BEAT_SCHEDULE` and `django-celery-beat`
admin-managed `PeriodicTask`s exist. Focus Mode (see
`backend/registers/services/focus_mode.py`) pauses non-essential periodic
scheduling without destroying queued work.

### External data sources

- **RUZ** – Register účtovných závierok (financial statements)
- **ORSR / RPO** – Obchodný register (company profiles, statutory officers)
- **VSZP / Social insurance** – Insurance debt checks
- **Financna sprava (FS)** – Tax authority data (IČO-matched only)

Scrapers/clients live under `backend/registers/scrapers/`, `scrapers/`,
`integrations/`, and orchestration under `backend/registers/tasks.py` +
`backend/registers/services/sync_engine.py`.

### Frontend (`frontend/`)

React 19 + TypeScript + Vite SPA. There is **no `frontend/src/`** — source files
live directly under `frontend/`:

- `frontend/App.tsx` – routing; `frontend/constants.ts` – routes/plans
- `frontend/pages/` – Home, Monitoring, ApiDocs, Profile, marketing/legal pages
- `frontend/admin/` – staff admin panel: `AdminApp.tsx`, `AdminLayout.tsx`,
  `api.ts`, `pages/` (Dashboard, Data, Users, SyncJobs, ScheduledTasks, AuditLog,
  System, Companies views)
- `frontend/api.ts` + `frontend/lib/apiClient.ts` – API client / JWT handling
- `frontend/types.ts` – types shared with the backend contract
- `frontend/utils/` – format, legal-form profiles, PDF export
- `frontend/components/`, `frontend/context/`, `frontend/hooks/`, `frontend/styles/`
- No browser-side AI calls: risk summaries (`frontend/api.ts` `riskSummary`) are
  deterministic, computed from public-register data (Altman Z-score, debt
  states). A former Gemini integration (`geminiService.ts`, `AiSummary.tsx`) was
  removed.

Frontend calls the backend through Vite's `/api/` proxy to the host configured
in `.env` (`BACKEND_HOST`/`BACKEND_PORT`).

### Infrastructure (`deploy/`)

- `deploy/helm/cistafirma/` – Helm chart (future deploy contract)
- `deploy/k8s/` – Kustomize overlays (current GitLab deploy path; marked DEPRECATED)
- Local "production" today runs via `docker-compose.yml` at the repo root.

### Environment variables

Local: copy `.env.default` to `.env` and fill in secrets. Docker Compose reads
`.env` at repo root. Key vars:
- `DATABASE_URL` – Postgres DSN (empty → SQLite fallback outside Docker)
- `REDIS_URL` – Redis DSN
- `SECRET_KEY` – Django secret key
- `DEBUG` – Enable Django debug mode
- `LOG_LEVEL` / `LOG_FORMAT` – `DEBUG|INFO|WARNING|ERROR|CRITICAL` / `json|text`
- `METRICS_ENABLED` – serve `/metrics` (internal clients only) or not
- `METRICS_TOKEN` – when set, `/metrics` needs `Authorization: Bearer <token>`
  instead of relying on the private-address check
- `BACKEND_WORKERS` / `BACKEND_THREADS` – gunicorn sizing (metrics aggregate
  across workers via `PROMETHEUS_MULTIPROC_DIR`)

### CI/CD (GitLab)

Pipeline stages: **validate** → **test** → **build** → **deploy**. Dev branch
auto-deploys; production deploys on `v*.*.*` tags (manual trigger). See
`docs/DEVOPS_CICD.md` and `docs/DEPLOYMENT_CONTRACT.md`.

## Working conventions

- The live DB and working tree are frequently ahead of `main`; check
  `git status` and current branch before assuming `main` reflects reality.
- Prefer English in new code/comments, but existing Slovak comments are
  accepted; do not mass-rewrite working code for language.
- Run the relevant backend tests before/after changes in sync/scraper logic.
- **Dark mode (Tailwind v4):** a bare `border` / `border-t` / `border-b` with no
  `border-<color>` resolves to `currentColor` (v3 used `gray-200`), and
  `main.css` sets `html.dark body { color: #f8fafc }` with no global dark
  border-color override — so it renders as a **near-white hairline** in dark
  mode. Always pair it: `border border-slate-200 dark:border-slate-700`, or the
  theme tokens `border-light-border dark:border-dark-border`. The same applies
  to light-only `bg-*` / `text-*` / `hover:*` (e.g. `bg-green-100
  text-green-700` → `bg-green-50 dark:bg-green-900/20 text-green-700
  dark:text-green-400`).
- Verify frontend edits with all three CI checks — `npm test`, `npm run
  typecheck`, `npm run build` — run via `docker compose exec -T frontend`. See
  Testing above.
