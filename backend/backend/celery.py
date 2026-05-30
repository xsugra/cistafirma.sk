import os
import sys
from pathlib import Path
from celery import Celery

# Add the project's 'backend' directory to the Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Get Redis URL from environment or use default
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)

app = Celery('backend',
             broker=CELERY_BROKER_URL,
             backend=CELERY_RESULT_BACKEND)

# Load other settings from Django settings, but broker/backend are now fixed.
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.update(
    worker_lost_wait=120,
    broker_transport_options={'visibility_timeout': 43200},
)

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
