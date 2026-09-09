# AGENTS.md

Guidance for AI coding agents (Claude Code, GitHub Copilot, Cursor, and other
agentic tools) working in this repository.

## Where to look first

- `CLAUDE.md` — full project orientation: architecture, commands, app map,
  Celery queues, data sources, conventions. **Read it before changing code.**
- `docs/` — architecture, API reference, developer guide, data protection,
  deployment contract, source-data integrity, devops/CI-CD.

## Data safety (applies to every agent, every session)

This project runs "in production" as a **local Docker Compose stack**. The
PostgreSQL volume `cistafirma_postgres_data` holds durable, irreplaceable Slovak
company-registry data.

**Never run** (these are also denied in `.claude/settings.json`):

- `make docker-reset`
- `docker compose down -v`
- `docker volume rm`, `docker volume prune`
- `make celery-purge` (unless the explicit token gate is deliberately met with
  prior human approval)
- a full RUZ resync or any database restore as a "routine" action
- `restore_postgres.sh` / any restore over the live `cistafirma` database

**Before** any migration, schema change, or data-affecting operation:

1. `make db-backup` — fresh timestamped dump
2. `make db-backup-verify BACKUP_FILE="<abs path>"` — checksum + readability
3. `make db-restore-drill BACKUP_FILE="<abs path>"` — isolated restore proof
   (never touches the live DB)

Recovery procedure, RPO/RTO, off-host encrypted replica and incident response
are documented in `docs/DATA_PROTECTION.md`.

## Key operational facts

- The DB schema, working tree, and `main` frequently diverge. Check
  `git status` and the current branch before assuming the checked-out code
  reflects the running system.
- Backend is a Django monolith (`backend/backend/settings.py`); frontend is
  React 19 + Vite under `frontend/` (no `frontend/src/` subdir).
- Data ingestion runs through Celery workers + Beat against real external
  registers (RUZ, ORSR/RPO, VSZP, Finančná správa). These are rate-limited and
  partially sequential; do not "optimize" by force-cancelling or purging.
- Full command reference and architecture: `CLAUDE.md`.
