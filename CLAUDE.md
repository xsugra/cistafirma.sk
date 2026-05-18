# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local development (manual)

```bash
make venv-create        # Create virtualenv and install Python deps
make runserver          # Django dev server on localhost:8000
make migrate            # Apply migrations
make migrations         # Generate new migrations (makemigrations)
make superuser          # Create Django superuser
```

### Frontend

```bash
cd frontend && npm install
cd frontend && npm run dev    # Vite dev server on localhost:5173
cd frontend && npm run build  # Production build into frontend/dist/
```

### Docker (preferred for full-stack)

```bash
make docker-up          # Start all services (backend, frontend, postgres, redis, workers)
make docker-migrate     # Run migrations in container
make docker-shell       # bash shell into backend container
make docker-logs        # Tail all container logs
make docker-reset       # Nuke volumes and rebuild from scratch
```

### Testing

```bash
make test               # Full Django test suite
make companies          # Tests for companies app only
make registers          # Tests for registers app only
make users              # Tests for users app only
make analyses           # Tests for analyses app only

# Single test class or method:
venv/bin/python backend/manage.py test registers.tests.SomeTestClass
venv/bin/python backend/manage.py test registers.tests.SomeTestClass.test_method
```

### Celery (background workers)

```bash
make run-celery-worker           # All queues
make run-celery-worker-sync      # Data sync queues (ruz_full, orsr, financials)
make run-celery-worker-insurance # Insurance + default queue
make run-celery-beat         # Periodic task scheduler
make celery-down             # Kill all Celery processes
make celery-purge            # Flush all pending tasks from Redis
```

### Data sync commands

```bash
make fetch-ruz               # Incremental RUZ data fetch
make fetch-ruz-full          # Full RUZ resync from 2000-01-01
make update-fs               # Update Financna Sprava data
```

## Architecture

CistaFirma is a Slovak company registry intelligence platform. The backend is a Django monolith exposing a REST API; the frontend is a React SPA that consumes it.

### Backend apps (`backend/`)

| App | Purpose |
|---|---|
| `companies` | Core company model (ICO-keyed), search, profile views |
| `registers` | External data integrations: RUZ scraper, ORSR profiles, financial results, insurance debt checks |
| `users` | Custom User model with email-based auth, SimpleJWT tokens |
| `subscriptions` | Subscription plans and feature gating |
| `analyses` | Risk scoring and reporting |
| `api` | Shared/cross-app endpoints |
| `adminapi` | Admin API endpoints, audit logging middleware |

Settings live in `backend/backend/settings.py`. Celery config is in `backend/backend/celery.py`.

### Celery task queues

| Queue | Workers | Purpose |
|---|---|---|
| `ruz_full` | 1 (sequential) | RUZ bulk sync, holds SyncProgress cursor |
| `orsr` | 1+ (scalable) | ORSR scraper per-company (rate-limited) |
| `financials` | 1+ | RUZ financial results per-company |
| `insurance` | 1+ | VSZP + Social insurance debt checks (rate-limited) |
| `celery` (default) | 1+ | FS updates, orchestration, ad-hoc tasks |

Periodic tasks are managed via `django-celery-beat` (admin → Periodic Tasks).

### External data sources

- **RUZ** – Register účtovných závierok (financial statements)
- **ORSR** – Obchodný register (company profiles, statutory officers)
- **VSZP / Social insurance** – Insurance debt checks
- **Financná správa (FS)** – Tax authority data

Scrapers/clients live under `backend/registers/scrapers/` and `backend/registers/tasks.py`.

### Frontend (`frontend/`)

React 19 + TypeScript + Vite SPA. API calls go through `frontend/services/`. Types shared with the backend contract are in `frontend/types.ts`. Routes use React Router 7.

### Infrastructure (`deploy/`)

- `deploy/helm/cistafirma/` – Helm chart used in CI/CD and K8s deployments
- `deploy/k8s/` – Kustomize overlays for base/dev/prod
- `values.yaml` = production defaults; `values-dev.yaml` = dev overrides

### Environment variables

Local: copy `.env.default` to `.env` and fill in secrets. Docker Compose reads `.env` at repo root. Key vars:
- `DATABASE_URL` – Postgres DSN (falls back to SQLite when unset)
- `REDIS_URL` – Redis DSN
- `SECRET_KEY` – Django secret key
- `DEBUG` – Enable Django debug mode

### CI/CD (GitLab)

Pipeline stages: **validate** → **test** → **build** → **deploy**. Dev branch auto-deploys; production deploys on `v*.*.*` tags (manual trigger).
