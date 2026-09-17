import os
import sys
from pathlib import Path
from celery import Celery
from celery.signals import setup_logging

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
    # Keep Django settings.LOGGING (structured JSON) authoritative in worker and
    # beat processes. Inert once the setup_logging receiver below is wired, but
    # a belt-and-braces guard against Celery re-adding its own text handlers.
    worker_hijack_root_logger=False,
)


@setup_logging.connect
def _configure_logging(**kwargs):
    """Re-apply settings.LOGGING in worker/beat.

    Any receiver on this signal makes Celery skip its internal logger setup
    (root-handler hijack, its own celery.task handler, forced -l level), so the
    JSON console logging configured in Django settings stays in effect.
    """
    import logging.config
    from django.conf import settings

    logging.config.dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
