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

# Hostnames Django answers to, comma-separated. The value ships in `.env.default`
# as `localhost,127.0.0.1,backend` and until now did nothing at all: this line was
# the literal `["*"]` and the variable was never read, so the setting looked
# configured while every Host header was accepted regardless of it.
#
# The fallback stays `["*"]` so an environment that predates this change keeps
# behaving exactly as it did -- the app answers on loopback, and on the server
# only over the tailnet, so the Host header is not attacker-controlled from
# anywhere else. Tightening a deployment is now a one-line `.env` edit rather
# than a code change. A leading dot matches subdomains, the way it does in
# `FRONTEND_ALLOWED_HOSTS`: `.example.ts.net` covers a host that may be renamed.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '').split(',')
    if host.strip()
] or ["*"]

# How many proxies sit between the client and gunicorn, for DRF's throttling.
# It decides which entry of `X-Forwarded-For` is treated as the caller: DRF
# takes the `n`-th from the right, so `1` means "the address the nearest proxy
# saw", which is the only entry a client cannot forge. Locally that nearest
# proxy is the Vite dev server (or `frontend/nginx.conf`), so `1` is right.
# A deployment with an extra ingress hop needs `2` -- with `1` there, every
# caller shares the ingress's address and one bucket, which limits harder than
# intended rather than not at all. Override with `THROTTLE_NUM_PROXIES`.
_num_proxies = os.getenv('THROTTLE_NUM_PROXIES', '1').strip()

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "NUM_PROXIES": int(_num_proxies) if _num_proxies else None,
    # Only the scopes named here exist; every other endpoint is unlimited, as
    # it was before. `companies.views.CompanyViewSet.get_throttles` is what
    # attaches them, and only to the two actions that cost real work.
    "DEFAULT_THROTTLE_RATES": {
        "report": os.getenv('REPORT_THROTTLE_RATE', '30/hour'),
        "peers": os.getenv('PEERS_THROTTLE_RATE', '120/hour'),
        # Each call re-reads the company's statement list from RUZ, and the
        # download behind it moves a PDF of up to a few megabytes. Fitted to a
        # person working through a company's years rather than to a page load:
        # the section withholds the list until a year is clicked, so ordinary
        # reading costs one call per year looked at.
        "documents": os.getenv('DOCUMENTS_THROTTLE_RATE', '120/hour'),
        # One request to orsr.sk per uncached query, against an endpoint that
        # answers a free-text name. Cached for `ORSR_PERSON_CACHE_SECONDS`, so
        # this bounds traffic rather than reading; a person looking up names
        # will not approach it.
        "orsr_person": os.getenv('ORSR_PERSON_THROTTLE_RATE', '60/hour'),
    },
}

# How long a register person-search answer is reused. The register's own
# search covers current records only and changes on the scale of days, so a
# short window removes almost all repeat traffic at no cost to freshness.
ORSR_PERSON_CACHE_SECONDS = int(os.getenv('ORSR_PERSON_CACHE_SECONDS', '900'))

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
#
# Those two cover a browser on this machine. Anywhere else, the origin Django has
# to trust is the one the *browser* used -- which this process cannot derive, so
# it arrives as configuration instead: `CSRF_TRUSTED_ORIGINS_EXTRA`,
# comma-separated and scheme included, e.g. `https://box.example.ts.net`.
#
# It is needed even though the browser sees the frontend and this API as one
# origin. The Vite dev server reaches gunicorn over plain HTTP, so on an HTTPS
# page `request.is_secure()` is False and the origin Django derives for itself is
# `http://<host>` -- which can never equal the `https://<host>` the browser sent.
# Naming the origin explicitly is what closes that gap.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
] + [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS_EXTRA", "").split(",")
    if origin.strip()
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
    'registers.tasks.read_person_history': {'queue': 'orsr'},
    'registers.tasks.sync_company_financials_from_ruz': {'queue': 'financials'},
    'registers.tasks.schedule_ruz_financials_sync': {'queue': 'financials'},
    'registers.tasks.update_insurance_debt': {'queue': 'insurance'},
    'registers.tasks.schedule_insurance_debt_checks': {'queue': 'celery'},
    'registers.tasks.schedule_person_history_resync': {'queue': 'celery'},
    'registers.tasks.force_check_all_companies_debts': {'queue': 'insurance'},
    'registers.tasks.update_fs_data_task': {'queue': 'celery'},
    'registers.tasks.sync_single_company_from_ruz': {'queue': 'celery'},
    'registers.tasks.sync_company_now': {'queue': 'celery'},
    'registers.tasks.orchestrate_full_company_sync': {'queue': 'celery'},
}

CELERY_BEAT_SCHEDULE = {
    # `queue: celery`, not `insurance`, and `args: [14400]` -- see the comment
    # above `INSURANCE_BATCH_PER_TICK` in `registers/tasks.py` for the measured
    # reason. The scheduler used to run on the queue it floods, so it waited
    # behind its own backlog and then fired repeatedly.
    #
    # Note that `DatabaseScheduler` runs the `PeriodicTask` row, not this entry:
    # while a row of the same name exists, everything here except the schedule
    # itself is inert. The row was updated to match, and all three layers agree,
    # but changing this dict alone would change nothing on a live system.
    'schedule-insurance-debt-checks-every-12-hours': {
        'task': 'registers.tasks.schedule_insurance_debt_checks',
        'schedule': 43200.0,
        'args': [14400],
        'options': {'expires': 43000.0, 'queue': 'celery'},
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
    # One-time repair, self-emptying: it selects companies whose profile has no
    # `osoby_historia` (24 237 of them when this was written) and stops
    # selecting anything once the last one has been read. Delete this entry and
    # its `PeriodicTask` row when `refresh_person_history --dry-run` reports 0.
    #
    # 2 000 every 4 h, and both numbers are load-bearing:
    #
    # * The `orsr` queue drains at 15 requests a minute -- orsr.sk has no API and
    #   this is somebody else's server. 2 000 tasks take 133 minutes to drain,
    #   which leaves the queue empty well inside the 4 h interval even with the
    #   500 companies the entry above adds to the same queue. Raising the batch
    #   past ~3 000 would push the next dispatch of `schedule_missing_orsr_sync`
    #   behind its own backlog -- the failure the insurance entry's comment
    #   describes.
    # * The pass is therefore ~48 h of wall clock, not the 27 h the requests
    #   alone would take, because it shares the queue with that lane.
    #
    # `queue: celery`, not `orsr`: a dispatcher that waits behind the 2 000
    # tasks it just queued would run hours late.
    #
    # The `expires` here is inert on this instance, and the arithmetic above does
    # not depend on it: all nine `PeriodicTask` rows carry `expires=None` while
    # their `args` and `queue` do match this dict (checked 2026-09-13), so
    # `options` does not reach the row. It is set for a fresh install, where the
    # row would be created from here. What bounds this lane in practice is the
    # batch size against the drain rate, not an expiry.
    'refresh-person-history-every-4-hours': {
        'task': 'registers.tasks.schedule_person_history_resync',
        'schedule': 14400.0,
        'args': [2000],
        'options': {'expires': 14000.0, 'queue': 'celery'},
    },
    # 2 000 companies every 12 h, not 500. The rotation walks the eligible
    # population (251 598 legal persons: forms 112/121/321/721/801/205, not
    # struck off) and 250 480 of them had no result yet, so at 500 a cycle the
    # book would take ~250 days to be read once. This entry is only half the
    # schedule -- the dispatcher reads `PeriodicTask` rows, not this dict, so
    # the DB row has to carry the same args (see docs/ARCHITECTURE.md §4).
    'sync-ruz-financials-every-12-hours': {
        'task': 'registers.tasks.schedule_ruz_financials_sync',
        'schedule': 43200.0,
        'args': [2000],
        'options': {'expires': 43000.0, 'queue': 'financials'},
    },
    # Recomputes the sector medians the benchmark table compares a company
    # against. It was written to run daily -- its own docstring says so -- but
    # no entry here and no `PeriodicTask` row ever existed, so
    # `SectorBenchmark` was empty and the benchmark block rendered nowhere: not
    # on the company page, not in the PDF export. Writes only `SectorBenchmark`
    # rows (one per NACE section, `update_or_create`), reads only our own
    # database, and issues no request to any register.
    'compute-sector-benchmarks-daily': {
        'task': 'registers.tasks.compute_sector_benchmarks',
        'schedule': 86400.0,
        'options': {'expires': 85000.0, 'queue': 'celery'},
    },
    'send-pending-notifications-every-15-min': {
        'task': 'notifications.tasks.send_pending_notifications',
        'schedule': 900.0,
        'options': {'expires': 800.0, 'queue': 'celery'},
    },
    # Reaps sync jobs whose worker died. Without it a dead import stays
    # `running` forever and is counted as active by the dashboard -- job #3 did
    # exactly that for 15 days. The staleness threshold is
    # CISTAFIRMA_STUCK_HEARTBEAT_MINUTES (default 30); it must stay well above
    # the slowest legitimate gap between heartbeats, or the reaper starts
    # killing healthy imports instead.
    'detect-stuck-sync-jobs-every-10-min': {
        'task': 'registers.tasks.detect_stuck_sync_jobs',
        'schedule': 600.0,
        'options': {'expires': 550.0, 'queue': 'celery'},
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
