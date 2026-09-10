.PHONY: help venv runserver migrations migrate superuser freeze clean clean-pre-push clean-pre-push-dry clean-pre-push-commit docs-audit db-backup db-backup-verify db-backup-replicate db-backup-prune db-offsite-status db-offsite-configure db-restore-drill db-backup-schedule-install db-backup-schedule-uninstall db-backup-schedule-status ops-check run-celery-worker run-celery-worker-sync run-celery-worker-insurance run-celery-beat celery-down celery-purge metrics docker-metrics-up docker-metrics-down

# ====================================================================================
# HELP
# ====================================================================================

help:
	@echo "==========================================================================="
	@echo " CistaFirma.sk Project Makefile"
	@echo "==========================================================================="
	@echo "  Manual (Legacy) Development:"
	@echo "    make venv           - Create a virtual environment and install dependencies"
	@echo "    make runserver      - Run the Django development server manually"
	@echo "    make migrate        - Apply database migrations manually"
	@echo "    make test           - Run the test suite manually"
	@echo "    make freeze         - Freeze dependencies to requirements.txt"
	@echo "    make clean          - Remove temporary files and venv"
	@echo "    make docs-audit     - Validate internal Markdown links"
	@echo "---------------------------------------------------------------------------"
	@echo "  Pre-Push Cleanup (Git):"
	@echo "    make clean-pre-push      - Clean and prepare git for push"
	@echo "    make clean-pre-push-dry  - Dry-run cleanup (no changes)"
	@echo "    make clean-pre-push-commit - Cleanup + auto-commit changes"
	@echo "---------------------------------------------------------------------------"

# ====================================================================================
# MANUAL (LEGACY) DEVELOPMENT
# ====================================================================================
BACKEND_DIR=backend
FRONTEND_DIR=frontend
DJANGO_MANAGE_DIR=$(BACKEND_DIR)/manage.py
VENV_DIR=venv
PYTHON=$(VENV_DIR)/bin/python
PIP=$(VENV_DIR)/bin/pip
REQUIREMENTS_DIR=$(BACKEND_DIR)/requirements.txt


run-frontend: venv
	@echo "Building frontend..."
	@cd $(FRONTEND_DIR) && npm run build
	@echo "Running server on developer environment..."
	@cd $(FRONTEND_DIR) && npm run dev

venv:
	@touch $(VENV_DIR)/bin/activate

venv-create:
	@echo "Creating virtual environment and installing dependencies..."
	@python3 -m venv $(VENV_DIR)
	@$(PIP) install -r $(REQUIREMENTS_DIR)
	@touch $(VENV_DIR)/bin/activate

collectstatic: venv
	@echo "Collecting static files..."
	@$(PYTHON) $(DJANGO_MANAGE_DIR) collectstatic

runserver: venv
	@echo "Starting Django development server on localhost:8000..."
	@$(PYTHON) $(DJANGO_MANAGE_DIR) runserver "localhost:8000"

migrations: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) makemigrations

migrate: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) migrate

superuser: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) createsuperuser

# Run from inside backend/: unittest discovery starts at the working directory
# and cannot descend into a directory that is not a package, so from the repo
# root `backend/` (which has no __init__.py) was invisible and this target found
# 0 tests while still exiting 0 -- a silent false green. CI already does the
# equivalent with `cd backend`. The labelled targets below (users, registers, …)
# are unaffected: a label is an importable module, not a discovery root.
test: venv
	@cd $(BACKEND_DIR) && $(CURDIR)/$(PYTHON) manage.py test

users: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test users

subscriptions: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test subscriptions

registers: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test registers

analyses: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test analyses

companies: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test companies

api: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test api

freeze: venv
	@echo "Freezing dependencies to requirements.txt..."
	@$(PIP) freeze > $(REQUIREMENTS_DIR)

clean:
	@echo "Cleaning up temporary files and virtual environment..."
	@rm -rf .cache
	@rm -rf htmlcov coverage.xml .coverage
	@find . -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@rm -rf $(VENV_DIR)

clean-pre-push:
	@bash scripts/pre-push-cleanup.sh

clean-pre-push-dry:
	@bash scripts/pre-push-cleanup.sh --dry-run

clean-pre-push-commit:
	@bash scripts/pre-push-cleanup.sh --commit

docs-audit:
	@echo "Running Markdown link audit..."
	@python3 scripts/docs/check_markdown_links.py

db-backup:
	@scripts/local/backup_postgres.sh

db-backup-verify:
	@test -n "$(BACKUP_FILE)" || (echo "ERROR: BACKUP_FILE is required" >&2; exit 2)
	@scripts/local/verify_postgres_backup.sh "$(BACKUP_FILE)"

# CISTAFIRMA_OFFSITE_BACKUP_DIR is optional here: when omitted, the script reads
# it from the machine-local config written by `make db-offsite-configure`. An
# empty value is forwarded as an empty string, which the loader treats as unset.
db-backup-replicate:
	@test -n "$(BACKUP_FILE)" || (echo "ERROR: BACKUP_FILE is required" >&2; exit 2)
	@CISTAFIRMA_OFFSITE_BACKUP_DIR="$(CISTAFIRMA_OFFSITE_BACKUP_DIR)" CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP="$(CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP)" scripts/local/replicate_postgres_backup.sh "$(BACKUP_FILE)"

db-restore-drill:
	@test -n "$(BACKUP_FILE)" || (echo "ERROR: BACKUP_FILE is required" >&2; exit 2)
	@scripts/local/restore_postgres_drill.sh "$(BACKUP_FILE)"

# Retention: keeps the newest N local backups (default 7). Dry-run unless
# applied, e.g. make db-backup-prune PRUNE_ARGS="--apply" (add --offsite to
# mirror the retention onto CISTAFIRMA_OFFSITE_BACKUP_DIR).
db-backup-prune:
	@scripts/local/prune_postgres_backups.sh $(PRUNE_ARGS)

# Off-site readiness report. Read-only; exits non-zero when a control is unmet.
db-offsite-status:
	@scripts/local/offsite_status.sh

# Aggregate operational gate: stack, queues, backups, off-site controls and the
# weekly job's own firing record. Read-only; exits non-zero when a control is
# unmet. NOTE: the off-site *mount* is required here (a deliberate check wants
# the truth), unlike in the unattended run, which treats a disconnected volume
# as the documented normal state.
ops-check:
	@scripts/local/ops_check.sh

# Record where the off-site backup volume lives on *this* machine, so the weekly
# launchd job (which inherits almost no environment) can find it. Writes
# ~/.config/cistafirma/backup.env; the repository stays free of machine paths.
db-offsite-configure:
	@test -n "$(CISTAFIRMA_OFFSITE_BACKUP_DIR)" || (echo "ERROR: CISTAFIRMA_OFFSITE_BACKUP_DIR is required, e.g. make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/Verbatim/cistafirmaBackups" >&2; exit 2)
	@scripts/local/configure_offsite.sh "$(CISTAFIRMA_OFFSITE_BACKUP_DIR)" "$(CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP)"

# Weekly unattended backup via launchd (backup -> verify -> replica if mounted).
db-backup-schedule-install:
	@scripts/local/install_backup_schedule.sh

db-backup-schedule-uninstall:
	@scripts/local/uninstall_backup_schedule.sh

db-backup-schedule-status:
	@scripts/local/backup_schedule_status.sh

celery-down: venv
	@echo "Turning off all backend Celery tasks..."
	@pkill -f "celery -A backend" || true

celery-purge: venv
	@test "$(CONFIRM_CELERY_PURGE)" = "DELETE_PENDING_MESSAGES" || (echo "ERROR: celery-purge permanently removes queued work. Re-run only with CONFIRM_CELERY_PURGE=DELETE_PENDING_MESSAGES." >&2; exit 2)
	@echo "DANGER: Purging all pending Celery tasks from Redis..."
	@cd $(BACKEND_DIR) && $(PYTHON) -c "from backend.celery import app; app.control.purge(); print('All pending tasks purged!')"

run-celery-worker: venv
	@echo "Running backend Celery worker (all queues)..."
	@cd $(BACKEND_DIR) && celery -A backend worker -l info -Q celery,ruz_full,orsr,financials,insurance

run-celery-worker-sync: venv
	@echo "Running Celery worker for data sync (RUZ, ORSR, financials)..."
	@cd $(BACKEND_DIR) && celery -A backend worker -l info -Q ruz_full,orsr,financials -n worker_sync@%h

run-celery-worker-insurance: venv
	@echo "Running Celery worker for insurance checks..."
	@cd $(BACKEND_DIR) && celery -A backend worker -l info -Q insurance,celery -n worker_insurance@%h

run-celery-beat: venv
	@echo "Running Celery Beat scheduler"
	@cd $(BACKEND_DIR) && celery -A backend beat -l info

fetch-ruz: venv
	@echo "Fetching RUZ data (incremental)..."
	@cd $(BACKEND_DIR) && $(PYTHON) manage.py fetch_ruz_data

fetch-ruz-full: venv
	@echo "Fetching RUZ data (full resync from 2000-01-01)..."
	@cd $(BACKEND_DIR) && $(PYTHON) manage.py fetch_ruz_data --full-resync


update-fs: venv
	@echo "Updating Financna Sprava data..."
	@cd $(BACKEND_DIR) && $(PYTHON) manage.py update_fs_data


# ====================================================================================
# DOCKER COMMANDS
# ====================================================================================

docker-build:
	@echo "Building Docker images..."
	@docker compose build

docker-up:
	@echo "Starting all Docker services..."
	@docker compose up -d

docker-down:
	@echo "Stopping all Docker services..."
	@docker compose down

docker-logs:
	@echo "Showing logs from all services..."
	@docker compose logs -f

docker-logs-backend:
	@echo "Showing backend logs..."
	@docker compose logs -f backend

docker-logs-celery:
	@echo "Showing Celery worker + beat logs..."
	@docker compose logs -f --tail=200 celery_worker_ruz celery_worker_orsr celery_worker_financials celery_worker_insurance celery_worker_default celery_beat

docker-shell:
	@echo "Opening shell in backend container..."
	@docker compose exec backend bash

metrics:
	@echo "Fetching /metrics from inside the backend container (loopback client)..."
	@docker compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=5).read().decode())"

docker-metrics-up:
	@echo "Starting optional Prometheus + Grafana (monitoring profile)..."
	@docker compose --profile monitoring up -d prometheus grafana
	@echo "  Prometheus: http://127.0.0.1:9090   Grafana: http://127.0.0.1:3000"

docker-metrics-down:
	@echo "Stopping Prometheus + Grafana (volumes are kept)..."
	@docker compose --profile monitoring stop prometheus grafana

docker-migrate:
	@echo "Running migrations in Docker (one-shot migrate service)..."
	@docker compose run --rm -T --build migrate

docker-superuser:
	@echo "Creating superuser in Docker..."
	@docker compose exec backend python manage.py createsuperuser --settings=backend.settings

docker-collectstatic:
	@echo "Collecting static files in Docker..."
	@docker compose exec backend python manage.py collectstatic --noinput --settings=backend.settings

docker-fetch-ruz:
	@echo "Running RUZ fetch in Docker..."
	@docker compose exec backend python manage.py fetch_ruz_data --settings=backend.settings

docker-fetch-ruz-full:
	@echo "Running full RUZ resync in Docker..."
	@docker compose exec backend python manage.py fetch_ruz_data --full-resync --settings=backend.settings

# docker-reset permanently deletes ALL volumes, including the PostgreSQL data
# volume cistafirma_postgres_data. It is an emergency-only recovery tool, not a
# routine command. Token-gated like celery-purge so an accidental or scripted
# run fails closed. Never use it while your only backup is unverified.
docker-reset:
	@test "$(CONFIRM_DOCKER_RESET)" = "DESTROY_VOLUMES_AND_REBUILD" || (echo "ERROR: docker-reset permanently removes ALL Docker volumes, including PostgreSQL data (cistafirma_postgres_data). This is emergency-only. Re-run only after a verified backup (make db-backup && make db-backup-verify) with CONFIRM_DOCKER_RESET=DESTROY_VOLUMES_AND_REBUILD." >&2; exit 2)
	@echo "DANGER: Destroying all Docker volumes, including PostgreSQL data. This is final."
	@docker compose down -v
	@docker compose build --no-cache
	@docker compose up -d
