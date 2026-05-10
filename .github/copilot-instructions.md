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
make docker-reset                            # Nuke volumes, rebuild from scratch
```

### Pre-push checks

```bash
make docs-audit                              # Validate Markdown link integrity
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
    │   ├── Celery Workers (3 queues: high_priority, low_priority, default)
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
- `backend/backend/settings.py` – Django settings, installed apps, middleware
- `backend/backend/celery.py` – Celery config, queue definitions
- `backend/backend/urls.py` – Root URL routing

### Frontend Architecture

**React 19 + TypeScript + Vite SPA:**

- `frontend/src/services/` – API client layer (fetch wrappers for backend endpoints)
- `frontend/src/types.ts` – Shared TypeScript types mirroring backend API contracts
- `frontend/src/` – React components and pages
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

Pipeline stages: `validate` → `test` → `build` → `deploy`

- **Validate:** backend compile check, frontend build, Helm render + K8s dry-run
- **Test:** Django test suite runs
- **Build:** backend + frontend Docker images built/pushed to registry
- **Deploy:** auto-deploy from `dev` branch; manual prod deploy from `v*.*.*` tags

See `.gitlab-ci.yml` and `docs/DEVOPS_CICD.md` for details.

## Key Conventions

### Branching

- Feature work: `feature/<scope>-<name>` (e.g., `feature/auth-oauth-integration`)
- Urgent fixes: `hotfix/<scope>-<name>`
- Integration: merge to `dev`
- Production releases: tag as `vX.Y.Z` (e.g., `v1.2.3`)

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
- API calls: `frontend/src/services/api.ts` (centralized fetch layer)
- Types: `frontend/src/types.ts` (sync with backend models/serializers)
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
- Verify API endpoint in `frontend/src/services/api.ts`

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
