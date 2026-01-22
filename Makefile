.PHONY: help venv runserver migrations migrate superuser freeze clean

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

venv:
	touch $(VENV_DIR)/bin/activate

venv-create:
	@echo "Creating virtual environment and installing dependencies..."
	@python3 -m venv $(VENV_DIR)
	@$(PIP) install -r $(REQUIREMENTS_DIR)
	@touch $(VENV_DIR)/bin/activate

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