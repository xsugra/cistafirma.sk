# Copilot Instructions for CistaFirma

This file contains critical guidance for AI assistants working on CistaFirma codebase.

## Build, Test & Lint

### Backend (Django)

**Test suite:**
```bash
make test                                    # Full suite
make companies                               # Companies app only
make registers                               # Registers app (RUZ/ORSR integration)
make users                                   # Users/auth app
make analyses                                # Risk analysis app
make api                                     # Shared endpoints
venv/bin/python backend/manage.py test registers.tests.SomeTestClass
venv/bin/python backend/manage.py test registers.tests.SomeTestClass.test_method
```

**Linting & validation:**
```bash
cd backend && python manage.py check           # Django system checks
```

**Migrations:**
```bash
make migrate                                 # Apply migrations
make migrations                              # Generate new migrations
```

### Frontend (React + Vite)

```bash
cd frontend && npm install
cd frontend && npm run build                 # Production build → frontend/dist/
```

### Local Development (Manual)

```bash
make venv-create                             # Create venv and install backend deps
make runserver                               # Django dev server (localhost:8000)
```

### Docker (Recommended)

```bash
make docker-up                               # Start all services (backend, frontend, db, redis, workers)
make docker-logs                             # Tail all logs
make docker-shell                            # Bash into backend container
make docker-migrate                          # Run migrations in container
make db-backup                               # Create a PostgreSQL backup outside Docker volumes
make db-backup-verify BACKUP_FILE=/abs/path  # Verify checksum and archive structure
make db-backup-replicate BACKUP_FILE=/abs/path # Copy verified backup to encrypted external volume
make db-restore-drill BACKUP_FILE=/abs/path  # Restore only into an isolated temporary container
make docker-reset                            # DANGER: permanently deletes Docker volumes and DB data
```

### Data protection

`cistafirma_postgres_data` contains durable company data. Never run
`make docker-reset`, `docker compose down -v`, `make celery-purge`, or a
database restore without explicit approval and a verified backup. The canonical
local backup and isolated restore-drill procedure is
[`docs/DATA_PROTECTION.md`](../docs/DATA_PROTECTION.md).

An unencrypted external backup disk is prohibited by default. The temporary
`CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true` override requires explicit
owner approval and must be removed once the disk is encrypted.

### Pre-push checks

```bash
make docs-audit                              # Validate Markdown links + inline citations
helm lint deploy/helm/cistafirma             # Validate Helm chart syntax
```

## High-Level Architecture

**CistaFirma** is a Slovak company registry intelligence platform combining public data sources into a single company verification workflow.

### System Flow (60-second overview)

```
User Browser
    ↓
React 19 + TypeScript + Vite Frontend (localhost:5173)
    ↓
Django 6 REST API (localhost:8000)
    ↓
PostgreSQL (production) / SQLite (local)
    ├── Redis broker/backend
    │   ├── Celery Workers (5 queues: ruz_full, orsr, financials, insurance, celery)
    │   └── Celery Beat (periodic task scheduler)
    │
External Data Sources:
    ├── RUZ – Financial statements register
    ├── ORSR – Commercial register (company profiles, officers)
    ├── VSZP / Social Insurance – Debt checks
    └── Financná Správa (FS) – Tax authority data
```

### Backend Architecture

**Django apps** (`backend/`):

| App | Purpose | Key Models |
|---|---|---|
| `companies` | Core company entity (ICO-keyed) and search | Company, CompanyProfile |
| `registers` | External data integrations (RUZ, ORSR, insurance) | RegisterRecord, InsuranceDebt |
| `users` | Email-based auth, SimpleJWT tokens | User, RefreshToken |
| `subscriptions` | Subscription plans and feature gating | Subscription, Feature |
| `analyses` | Risk scoring and reporting | RiskScore, Report |
| `api` | Shared/cross-app endpoints | (ViewSets, serializers) |

**Key config files:**
- `backend/backend/settings.py` – Django settings, installed apps, middleware, **Celery queue definitions** (`CELERY_TASK_QUEUES` / `CELERY_TASK_ROUTES`)
- `backend/backend/celery.py` – Celery app wiring (the queues themselves are in `settings.py`)
- `backend/backend/urls.py` – Root URL routing

### Frontend Architecture

**React 19 + TypeScript + Vite SPA:**

- `frontend/lib/apiClient.ts` + `frontend/api.ts` – API client layer (fetch wrappers for backend endpoints)
- `frontend/types.ts` – Shared TypeScript types mirroring backend API contracts
- `frontend/` – React components and pages (**there is no `frontend/src/`** — sources live directly under `frontend/`)
- **Routing:** React Router 7 (`createBrowserRouter`)

### Data Flow

1. **Async Task Queues** (Celery):
   - `high_priority` – RUZ bulk sync, FS updates (1+ workers)
   - `low_priority` – Insurance debt checks (VSZP, social), orchestration (1+ workers)
   - `celery` (default) – General tasks (runs in low_priority workers)

2. **Periodic Tasks** (Celery Beat) – scheduled via Django admin (`/admin/django_celery_beat/periodictask/`)

3. **Scrapers/Data Clients** – in `backend/registers/scrapers/` and `backend/registers/tasks.py`

### Infrastructure

**Deployment targets:**

- `deploy/helm/cistafirma/` – Helm 3 chart (backend, frontend, worker, beat, ingress, migrate job)
- `deploy/k8s/` – Kustomize overlays:
  - `base/` – shared resources
  - `overlays/dev/` – development environment overrides
  - `overlays/prod/` – production environment overrides

**Environment variables** (local: copy `.env.default` to `.env`; Docker: reads from repo root `.env`):
- `DATABASE_URL` – Postgres DSN (falls back to SQLite when unset)
- `REDIS_URL` – Redis broker URL
- `SECRET_KEY` – Django secret key (never commit)
- `DEBUG` – Enable Django debug mode

### CI/CD (GitLab)

Pipeline stages: `validate` → `test`, and that is all.

- **Validate:** backend compile check (`compileall`), frontend build, Markdown +
  inline-citation audits, Helm lint/render + rendered-manifest runtime check
- **Test:** Django test suite (against Postgres + Redis service containers),
  frontend Vitest + typecheck

There is **no `build` stage and no `deploy` stage**: nothing consumes registry
images (production builds from source on `dell`), and the K8s deploy job could
never pass because no cluster exists. Both were removed on 2026-09-15 — the
reasoning is preserved in the comment at the end of `.gitlab-ci.yml`.
Deploy is a **manual** step on `dell` (`git pull gitlab-home <branch>` +
`docker compose up -d --build` + `migrate`).

See `.gitlab-ci.yml` and `docs/DEVOPS_CICD.md` for details.

## Key Conventions

### Branching

- Feature work: `feature/<scope>-<name>` (e.g., `feature/auth-oauth-integration`)
- Urgent fixes: `hotfix/<scope>-<name>`
- **Integration branch is `main`.** A `dev` branch exists but is dormant: its
  last commit is 2026-05-20 and `main` has run ~457 commits ahead of it since.
  Do not treat `dev` as a merge target.
- **Release tags are not in use.** The repo has no tags at all and production
  deploys from `main` by hand, so `vX.Y.Z` describes an intent rather than a
  step anyone performs. Name a branch after the work, not a version.

### Commit Messages

Follow conventional commits:
```
<type>(<scope>): <subject>

<optional body>

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

**Scope examples:** `auth`, `api`, `ruz`, `frontend`, `helm`, `celery`

### Merge Request Checklist

Every MR must include:

1. Clear title + description (what, why, how to verify)
2. Local validation passed:
   - Backend: `make test` (relevant app or full suite)
   - Frontend: `npm run build` (if UI/API changed)
   - Docs: `make docs-audit` (if docs/API changed)
3. **Documentation updated** (if API/deploy/workflow changed):
   - `README.md`
   - `docs/API_REFERENCE.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPER_GUIDE.md` (if workflow impacted)
   - `docs/DEVOPS_CICD.md` (if CI/deploy changed)
4. **No secrets committed** (passwords, tokens, keys)
5. **Rollback plan documented** (if schema/deploy risk exists)

### Code Style & Testing

- **Backend:** Django conventions; tests in `<app>/tests/` (auto-discovered by Django test runner)
- **Frontend:** TypeScript enforced; React Router 7 for navigation; Recharts for charts
- **Async work:** Use Celery tasks for long-running jobs (external API calls, bulk syncs)

### Documentation

Critical docs (read before major changes):
- `docs/ARCHITECTURE.md` – system design, data flows, queues
- `docs/DEVELOPER_GUIDE.md` – local setup, testing, debugging
- `docs/API_REFERENCE.md` – endpoint specs, request/response examples
- `docs/DEPLOYMENT_RUNBOOK.md` – production deployment steps
- `docs/DEVOPS_CICD.md` – CI/CD pipeline, release flow

### Common Patterns

**External data integration (RUZ, ORSR, insurance):**
- Scraper logic: `backend/registers/scrapers/<source>.py`
- Celery task: `backend/registers/tasks.py`
- Models: `backend/registers/models.py`
- Pattern: fetch → parse → upsert to DB → emit signals for dependent tasks

**API endpoints:**
- Serializers: `backend/<app>/serializers.py`
- ViewSets: `backend/<app>/views.py`
- Routes: `backend/<app>/urls.py` (imported in `backend/backend/urls.py`)
- Auth: SimpleJWT (validate token in request headers)

**Frontend components:**
- API calls: `frontend/api.ts` plus the JWT-aware `frontend/lib/apiClient.ts` (centralized fetch layer)
- Types: `frontend/types.ts` (sync with backend models/serializers)
- Pages/components: organized by feature, use React Router hooks (`useParams`, `useLocation`)

### Testing Tips

- **Django ORM in tests:** use `TransactionTestCase` for testing Celery tasks (they run in separate process)
- **Isolated units:** mock external API calls (RUZ, ORSR, insurance) to avoid slow/flaky tests
- **Frontend:** test component props and event handlers; mock API responses

### When Debugging

**Backend is slow:**
- Check `make docker-logs celery*` for stuck workers or failed tasks
- Inspect Redis: `redis-cli` (inside container: `docker compose exec redis redis-cli`)
- Check DB queries: Django debug toolbar or `django-extensions` shell_plus

**Frontend not updating:**
- Clear browser cache or use hard refresh (`Cmd+Shift+R`)
- Check browser console for errors and network tab for API response status
- Verify API endpoint in `frontend/api.ts`

## Pre-Push Workflow

Before pushing to GitLab, run:

```bash
make clean-pre-push-dry                      # Check what will be cleaned
make clean-pre-push-commit                   # Clean artifacts and auto-commit
make test                                    # Run backend tests
cd frontend && npm run build                 # Verify frontend builds
make docs-audit                              # Validate doc links
```

Then push:

```bash
git push origin <branch>
```

## See Also

- `CLAUDE.md` – Companion file with full command reference
- `CONTRIBUTING.md` – Contribution guidelines
- `.gitlab-ci.yml` – CI/CD pipeline definition
- `docs/` – Extended documentation hub
