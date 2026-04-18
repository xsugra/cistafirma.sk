from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import os

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
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', default='django-insecure-nq_rv8nr_-xa(y^)la9g$rguj_k4^19t5gj7xi)0%me!n8g0ma')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', default=True)

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
    'users',
    'subscriptions',
    'companies',
    'registers',
    'analyses',
    'api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + CUSTOM_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # DÔLEŽITÉ PRE PRODUKCIU
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

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

# Django Celery Beat - fix for Python 3.12+ zoneinfo issue
DJANGO_CELERY_BEAT_TZ_AWARE = False

# Queue configuration - high_priority for RUZ/FS, low_priority for insurance checks
CELERY_TASK_QUEUES = {
    'high_priority': {
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
    },
    'low_priority': {
        'exchange': 'low_priority',
        'routing_key': 'low_priority',
    },
    'celery': {
        'exchange': 'celery',
        'routing_key': 'celery',
    },
}

# Default queue
CELERY_TASK_DEFAULT_QUEUE = 'celery'

CELERY_BEAT_SCHEDULE = {
    # Kontrola dlhov v poisťovniach každých 12 hodín (low priority)
    'schedule-insurance-debt-checks-every-12-hours': {
        'task': 'registers.tasks.schedule_insurance_debt_checks',
        'schedule': 43200.0,  # 12 hodín v sekundách (12 * 60 * 60)
        'options': {'expires': 43000.0, 'queue': 'low_priority'},
    },
    # Aktualizácia dát z RUZ API každých 6 hodín (high priority)
    'fetch-ruz-data-every-6-hours': {
        'task': 'registers.tasks.fetch_ruz_data_task',
        'schedule': 21600.0,  # 6 hodín v sekundách (6 * 60 * 60)
        'options': {'expires': 21000.0, 'queue': 'high_priority'},
    },
    # Aktualizácia dát z Finančnej správy raz denne (high priority)
    'update-fs-data-daily': {
        'task': 'registers.tasks.update_fs_data_task',
        'schedule': 86400.0,  # 24 hodín v sekundách
        'options': {'expires': 85000.0, 'queue': 'high_priority'},
    },
    # ORSR profily pre firmy bez ORSR záznamu (každé 4 hodiny, dávka 500)
    'sync-missing-orsr-profiles-every-4-hours': {
        'task': 'registers.tasks.schedule_missing_orsr_sync',
        'schedule': 14400.0,
        'args': [500],
        'options': {'expires': 14000.0, 'queue': 'low_priority'},
    },
    # Hospodárske výsledky z RUZ (každých 12 hodín, dávka 500)
    'sync-ruz-financials-every-12-hours': {
        'task': 'registers.tasks.schedule_ruz_financials_sync',
        'schedule': 43200.0,
        'args': [500],
        'options': {'expires': 43000.0, 'queue': 'low_priority'},
    },
}

# =============================================================================
# DJANGO UNFOLD - MODERN ADMIN THEME
# =============================================================================
from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "CistaFirma",
    "SITE_HEADER": "CistaFirma Admin",
    "SITE_SUBHEADER": "Správa firiem a registrov",
    "SITE_SYMBOL": "verified",  # Material Symbols icon
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    
    # Sidebar konfigurácia
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": True,
                "items": [
                    {
                        "title": "Prehľad",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": "Správa firiem",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Firmy",
                        "icon": "business",
                        "link": reverse_lazy("admin:companies_company_changelist"),
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
                        "title": "Plány predplatného",
                        "icon": "credit_card",
                        "link": reverse_lazy("admin:subscriptions_subscriptionplan_changelist"),
                    },
                ],
            },
            {
                "title": "Systém",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Synchronizácia RUZ",
                        "icon": "sync",
                        "link": reverse_lazy("admin:registers_syncprogress_changelist"),
                    },
                    {
                        "title": "Periodické úlohy",
                        "icon": "schedule",
                        "link": reverse_lazy("admin:django_celery_beat_periodictask_changelist"),
                    },
                ],
            },
        ],
    },
    
    # Farby a štýl - modrá téma
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
}
