.PHONY: help venv runserver migrations migrate superuser freeze clean clean-pre-push clean-pre-push-dry clean-pre-push-commit docs-audit db-backup db-backup-verify db-backup-replicate db-restore-drill run-celery-worker run-celery-worker-sync run-celery-worker-insurance run-celery-beat celery-down celery-purge

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

test: venv
	@$(PYTHON) $(DJANGO_MANAGE_DIR) test

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

db-backup-replicate:
	@test -n "$(BACKUP_FILE)" || (echo "ERROR: BACKUP_FILE is required" >&2; exit 2)
	@test -n "$(CISTAFIRMA_OFFSITE_BACKUP_DIR)" || (echo "ERROR: CISTAFIRMA_OFFSITE_BACKUP_DIR is required" >&2; exit 2)
	@CISTAFIRMA_OFFSITE_BACKUP_DIR="$(CISTAFIRMA_OFFSITE_BACKUP_DIR)" CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP="$(CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP)" scripts/local/replicate_postgres_backup.sh "$(BACKUP_FILE)"

db-restore-drill:
	@test -n "$(BACKUP_FILE)" || (echo "ERROR: BACKUP_FILE is required" >&2; exit 2)
	@scripts/local/restore_postgres_drill.sh "$(BACKUP_FILE)"

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
	@echo "Showing Celery worker logs..."
	@docker compose logs -f celery_worker celery_beat

docker-shell:
	@echo "Opening shell in backend container..."
	@docker compose exec backend bash

docker-migrate:
	@echo "Running migrations in Docker..."
	@docker compose exec backend python manage.py migrate --settings=backend.settings

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

docker-reset:
	@echo "DANGER: Resetting Docker environment permanently removes volumes, including PostgreSQL data."
	@docker compose down -v
	@docker compose build --no-cache
	@docker compose up -d
