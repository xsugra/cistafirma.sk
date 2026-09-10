import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# Load environment from root .env first (centralized config)
# Then fall back to backend-specific .env.dev/.env.docker if root .env doesn't exist
ROOT_ENV_PATH = PROJECT_ROOT / '.env'
BACKEND_ENV_PATH = BASE_DIR / '.env.dev'
DOCKER_ENV_PATH = BASE_DIR / '.env.docker'

# Try to load from root .env (centralized), then fall back to backend-specific files
if ROOT_ENV_PATH.exists():
    load_dotenv(dotenv_path=ROOT_ENV_PATH)
elif DOCKER_ENV_PATH.exists():
    load_dotenv(dotenv_path=DOCKER_ENV_PATH)
elif BACKEND_ENV_PATH.exists():
    load_dotenv(dotenv_path=BACKEND_ENV_PATH)
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# --- Structured logging (Phase 3) ---
# LOG_LEVEL governs the root level (independent of DEBUG); LOG_FORMAT selects
# the console formatter. Fail fast: an invalid value is a config bug.
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').strip().upper()
if LOG_LEVEL not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
    raise ImproperlyConfigured(
        f'LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL, got {LOG_LEVEL!r}'
    )

LOG_FORMAT = os.getenv('LOG_FORMAT', 'json').strip().lower()
if LOG_FORMAT not in {'json', 'text'}:
    raise ImproperlyConfigured(f'LOG_FORMAT must be "json" or "text", got {LOG_FORMAT!r}')

# --- Prometheus metrics (Phase 3, pillar 2) ---
# METRICS_ENABLED turns the /metrics scrape target on or off. The endpoint is
# never public regardless: core/metrics.py restricts it to loopback/private
# clients, or to a bearer METRICS_TOKEN when that variable is set.
_raw_metrics_enabled = os.getenv('METRICS_ENABLED', 'true').strip().lower()
if _raw_metrics_enabled not in {'true', 'false', '1', '0', 'yes', 'no'}:
    raise ImproperlyConfigured(
        f'METRICS_ENABLED must be a boolean-ish value, got {_raw_metrics_enabled!r}'
    )
METRICS_ENABLED = _raw_metrics_enabled in {'true', '1', 'yes'}

# SECURITY WARNING: keep the secret key used in production secret!
_default_secret = 'django-insecure-nq_rv8nr_-xa(y^)la9g$rguj_k4^19t5gj7xi)0%me!n8g0ma'
SECRET_KEY = os.getenv('SECRET_KEY', default=_default_secret if DEBUG else '')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be set in production (DEBUG=False).')

ALLOWED_HOSTS = ["*"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# Application definition

DJANGO_APPS = [
    'unfold',  # Django Unfold musí byť pred admin
    'unfold.contrib.filters',  # Filtre pre Unfold
    'unfold.contrib.forms',  # Formuláre pre Unfold
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_celery_beat', # Added for Celery Beat
]

CUSTOM_APPS = [
    'core',
    'users',
    'subscriptions',
    'companies',
    'registers',
    'connections',
    'analyses',
    'api',
    'adminapi',
    'notifications',
    'lead_scoring',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + CUSTOM_APPS

MIDDLEWARE = [
    'core.middleware.RequestLogMiddleware',  # structured request access-log (first)
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # DÔLEŽITÉ PRE PRODUKCIU
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'adminapi.middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND':
            'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            FRONTEND_DIR / 'dist',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Cache
#
# Keep cache entries in a Redis database separate from Celery's broker/result
# database. CACHE_REDIS_URL takes precedence for deployments that provision a
# dedicated Redis instance or database. Otherwise, use the next Redis database
# after the configured Celery broker database.
def _default_cache_redis_url(broker_url: str) -> str:
    parsed = urlparse(broker_url)
    if parsed.scheme not in {'redis', 'rediss'}:
        raise ImproperlyConfigured(
            'CACHE_REDIS_URL must be set when CELERY_BROKER_URL is not a Redis URL.'
        )

    try:
        broker_db = int(parsed.path.lstrip('/') or '0')
    except ValueError as exc:
        raise ImproperlyConfigured(
            'The Redis database in CELERY_BROKER_URL must be an integer.'
        ) from exc

    return urlunparse(parsed._replace(path=f'/{broker_db + 1}'))


_celery_broker_url = os.getenv('CELERY_BROKER_URL') or os.getenv(
    'REDIS_URL', 'redis://localhost:6379/0'
)
_cache_source_url = _celery_broker_url
if urlparse(_cache_source_url).scheme not in {'redis', 'rediss'}:
    _cache_source_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL') or _default_cache_redis_url(
    _cache_source_url
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': CACHE_REDIS_URL,
        'TIMEOUT': 300,
        'OPTIONS': {
            'socket_connect_timeout': 1,
            'socket_timeout': 5,
        },
    },
}

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# Support for DATABASE_URL environment variable (Docker/Production)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Parse DATABASE_URL for PostgreSQL
    import urllib.parse
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or 5432,
        }
    }
else:
    # Fallback to SQLite for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 30,  # Čakaj 30 sekúnd na uvoľnenie zámku
            },
        }
    }

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

# --- STATIC FILES CONFIG ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Sem sa všetko pozbiera príkazom collectstatic

# Django musí servovať 'frontend/dist' na URL '/static/'.
STATICFILES_DIRS = [
    FRONTEND_DIR / 'dist',
]

# Whitenoise nastavenie pre kompresiu a caching
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 1. Pridaj adresu frontendu medzi dôveryhodné pre CSRF (Django 4.0+)
# Toto je presne to, čo vyrieši chybu "CSRF verification failed"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# 2. Nastav CORS (ak používaš django-cors-headers)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # Pre istotu nechaj aj starý
]

# 3. Pre istotu povoľ credentials
CORS_ALLOW_CREDENTIALS = True

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    'users.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',  # Záloha (klasické prihlásenie)
]


# Celery Settings
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = "Europe/Bratislava"
CELERY_ENABLE_UTC = True

# Django Celery Beat -- timezone-aware scheduling.
#
# This was False to dodge a Python 3.12+ zoneinfo problem. That problem is gone
# in django-celery-beat 2.9.0: TzAwareCrontab uses only stdlib `datetime.now(tz)`
# and `astimezone`, with no pytz `.localize()`. With the flag False the scheduler
# builds a plain `crontab`, whose timezone comes from CELERY_TIMEZONE rather than
# from each row -- so a row given a *different* timezone in the admin is silently
# ignored. Setting it True makes the row's own `timezone` field authoritative.
#
# No firing time changes today: the only crontab row (`celery.backend_cleanup`,
# "0 4 * * *") already carries Europe/Bratislava, which is also CELERY_TIMEZONE,
# so both readings agree. Verified before flipping -- next run 04:00 Bratislava
# either way. The flag is what makes PeriodicTask.last_run_at aware, so leaving
# it False logged `RuntimeWarning: ... received a naive datetime` on every due
# task, about 100 times a day.
DJANGO_CELERY_BEAT_TZ_AWARE = True

# Queue layout: každá queue mapuje na samostatný Celery worker deployment v k8s.
# - ruz_full: sekvenčné RUZ bulk operácie (1 worker only, drží SyncProgress kurzor)
# - orsr: ORSR scraper per-company (horizontálne škálovateľný, pozor na rate limit)
# - financials: RUZ hospodárske výsledky per-company
# - insurance: VSZP + Soc. poisťovňa scrapery (rate-limited, riziko banu)
# - celery: default queue pre FS, orchestračné a ad-hoc úlohy
CELERY_TASK_QUEUES = {
    'ruz_full': {
        'exchange': 'ruz_full',
        'routing_key': 'ruz_full',
    },
    'orsr': {
        'exchange': 'orsr',
        'routing_key': 'orsr',
    },
    'financials': {
        'exchange': 'financials',
        'routing_key': 'financials',
    },
    'insurance': {
        'exchange': 'insurance',
        'routing_key': 'insurance',
    },
    'celery': {
        'exchange': 'celery',
        'routing_key': 'celery',
    },
}

# Default queue
CELERY_TASK_DEFAULT_QUEUE = 'celery'

CELERY_TASK_ROUTES = {
    'registers.tasks.fetch_ruz_data_task': {'queue': 'ruz_full'},
    'registers.tasks.resume_full_ruz_sync': {'queue': 'ruz_full'},
    'registers.tasks.start_full_ruz_sync': {'queue': 'ruz_full'},
    'registers.tasks.start_full_ruz_sync_from_id': {'queue': 'ruz_full'},
    'registers.tasks.start_incremental_sync': {'queue': 'ruz_full'},
    'registers.tasks.start_repair_sync': {'queue': 'ruz_full'},
    'registers.tasks.resume_repair_sync': {'queue': 'ruz_full'},
    'registers.tasks.analyze_ruz_gaps': {'queue': 'ruz_full'},
    'registers.tasks.repair_ruz_gaps': {'queue': 'ruz_full'},
    'registers.tasks.resume_gap_repair': {'queue': 'ruz_full'},
    'registers.tasks.sync_company_orsr_data': {'queue': 'orsr'},
    'registers.tasks.schedule_missing_orsr_sync': {'queue': 'orsr'},
    'registers.tasks.sync_company_financials_from_ruz': {'queue': 'financials'},
    'registers.tasks.schedule_ruz_financials_sync': {'queue': 'financials'},
    'registers.tasks.update_insurance_debt': {'queue': 'insurance'},
    'registers.tasks.schedule_insurance_debt_checks': {'queue': 'insurance'},
    'registers.tasks.force_check_all_companies_debts': {'queue': 'insurance'},
    'registers.tasks.update_fs_data_task': {'queue': 'celery'},
    'registers.tasks.sync_single_company_from_ruz': {'queue': 'celery'},
    'registers.tasks.sync_company_now': {'queue': 'celery'},
    'registers.tasks.orchestrate_full_company_sync': {'queue': 'celery'},
}

CELERY_BEAT_SCHEDULE = {
    'schedule-insurance-debt-checks-every-12-hours': {
        'task': 'registers.tasks.schedule_insurance_debt_checks',
        'schedule': 43200.0,
        'options': {'expires': 43000.0, 'queue': 'insurance'},
    },
    'fetch-ruz-data-every-6-hours': {
        'task': 'registers.tasks.fetch_ruz_data_task',
        'schedule': 21600.0,
        'options': {'expires': 21000.0, 'queue': 'ruz_full'},
    },
    'update-fs-data-daily': {
        'task': 'registers.tasks.update_fs_data_task',
        'schedule': 86400.0,
        'options': {'expires': 85000.0, 'queue': 'celery'},
    },
    'sync-missing-orsr-profiles-every-4-hours': {
        'task': 'registers.tasks.schedule_missing_orsr_sync',
        'schedule': 14400.0,
        'args': [500],
        'options': {'expires': 14000.0, 'queue': 'orsr'},
    },
    'sync-ruz-financials-every-12-hours': {
        'task': 'registers.tasks.schedule_ruz_financials_sync',
        'schedule': 43200.0,
        'args': [500],
        'options': {'expires': 43000.0, 'queue': 'financials'},
    },
    'send-pending-notifications-every-15-min': {
        'task': 'notifications.tasks.send_pending_notifications',
        'schedule': 900.0,
        'options': {'expires': 800.0, 'queue': 'celery'},
    },
}

# =============================================================================
# DJANGO UNFOLD - MODERN ADMIN THEME
# =============================================================================
from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "CistaFirma",
    "SITE_HEADER": "CistaFirma",
    "SITE_SUBHEADER": "Verifikacia a monitoring firiem",
    "SITE_SYMBOL": "verified",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "ENVIRONMENT": "development" if DEBUG else "production",

    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Prehľad",
                "separator": True,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": "Dáta",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Firmy",
                        "icon": "business",
                        "link": reverse_lazy("admin:companies_company_changelist"),
                    },
                    {
                        "title": "ORSR profily",
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:registers_orsrcompanyprofile_changelist"),
                    },
                ],
            },
            {
                "title": "Používatelia",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Používatelia",
                        "icon": "people",
                        "link": reverse_lazy("admin:users_user_changelist"),
                    },
                    {
                        "title": "Predplatné",
                        "icon": "credit_card",
                        "link": reverse_lazy("admin:subscriptions_subscriptionplan_changelist"),
                    },
                ],
            },
            {
                "title": "Synchronizácia",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Sync RUZ",
                        "icon": "sync",
                        "link": reverse_lazy("admin:registers_syncprogress_changelist"),
                    },
                    {
                        "title": "Gap Analysis",
                        "icon": "troubleshoot",
                        "link": reverse_lazy("admin:registers_syncgapanalysis_changelist"),
                    },
                    {
                        "title": "Focus Mode",
                        "icon": "center_focus_strong",
                        "link": reverse_lazy("admin:registers_syncfocusmodestate_changelist"),
                    },
                ],
            },
            {
                "title": "Systém",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Periodické úlohy",
                        "icon": "schedule",
                        "link": reverse_lazy("admin:django_celery_beat_periodictask_changelist"),
                    },
                ],
            },
        ],
    },

    "COLORS": {
        "primary": {
            "50": "239 246 255",
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "147 197 253",
            "400": "96 165 250",
            "500": "59 130 246",
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
            "950": "23 37 84",
        },
    },
}

# Email configuration (for notifications)
# Defaults to the console backend (prints emails to the backend logs in dev).
# For real SMTP, set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# and the EMAIL_* vars in the environment (.env).
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
DEFAULT_FROM_EMAIL = os.getenv('EMAIL_FROM', 'CistaFirma <noreply@cistafirma.sk>')

# =============================================================================
# LOGGING — structured (JSON) console logging, stdlib only.
#
# Django applies its DEFAULT_LOGGING before settings.LOGGING, so the django*
# loggers are named explicitly below to replace the default text handlers and
# avoid duplicate lines. disable_existing_loggers=False is required: in Celery
# workers the backend.celery loggers are imported before django.setup() runs
# dictConfig, and re-enabling the default would silence them.
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'core.logging.JsonFormatter',  # lazy-imported by dictConfig
        },
        'text': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S%z',
        },
    },
    'filters': {
        # Adds task_id/task_name to records logged while a Celery task runs, so
        # a task's own logs (and anything it calls) can be correlated.
        'celery_task': {'()': 'core.logging.CeleryTaskFilter'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # structured logs to stdout, not stderr
            'formatter': LOG_FORMAT,
            'filters': ['celery_task'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        # Django internals
        'django': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        # runserver logs every request at INFO — suppressed; the middleware is
        # the single request-log source. Broken-pipe etc. (WARNING+) remain.
        'django.server': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        # 5xx (with traceback -> JSON exc_info) stays; 4xx is covered by the
        # request-log middleware only, so there is a single source.
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        # Celery
        'celery': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'celery.task': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'celery.redirected': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        # Peers emit "missed heartbeat from worker_insurance" every ~100s for as
        # long as a worker is busy, because the gossip thread shares the event
        # loop with the task. The insurance queue is deliberately rate-limited
        # (20/m) over 441k companies, so it is saturated more or less
        # permanently -- the message fires forever by design and is not
        # actionable. Measured at 1094 of ~1750 lines (63%) of all worker
        # output, which buried every real message. Genuine gossip problems log
        # at WARNING and above, so those still come through.
        'celery.worker.consumer.gossip': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        # App request access-log (structured, single source)
        'cistafirma.request': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
