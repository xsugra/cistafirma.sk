import os
import sys
from pathlib import Path
from celery import Celery

# --- Diagnostics Step 1: Print environment variables Celery might be using ---
print("--- CELERY DIAGNOSTICS ---")
print(f"ENV 'CELERY_BROKER_URL': {os.environ.get('CELERY_BROKER_URL')}")
print(f"ENV 'KOMBU_URL': {os.environ.get('KOMBU_URL')}")
print("--------------------------")

# Add the project's 'backend' directory to the Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# --- Definitive Solution: Force broker and backend in the constructor ---
# This has higher precedence than config_from_object and should override
# any conflicting settings that cause the AMQP transport issue.
app = Celery('backend',
             broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0')

# Load other settings from Django settings, but broker/backend are now fixed.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# --- Diagnostics Step 2: Print the final resolved configuration ---
print("--- FINAL RESOLVED CELERY CONFIG ---")
print(f"app.conf.broker_url: {app.conf.broker_url}")
print(f"app.conf.result_backend: {app.conf.result_backend}")
print(f"app.conf.broker_transport: {app.conf.broker_transport}")
print("------------------------------------")
