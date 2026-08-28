"""
Base Django settings for config project.

Common settings shared across all environments.
"""

from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # required for BLACKLIST_AFTER_ROTATION
    'corsheaders',
    'channels',
    
    # Local apps
    'apps.common',
    'apps.accounts',
    'apps.core',
    'apps.audit',
    'apps.roads',
    'apps.cameras',
    'apps.traffic',
    'apps.violations',
    'apps.analytics',
    # Newly added domain apps for organizational scope, drivers, fines, notifications
    'apps.organizations',
    'apps.drivers',
    'apps.fines',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS middleware should be at the top
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Use PostgreSQL by default, fallback to SQLite if not configured
if os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'traffic_management'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Ensure unittest discovery uses the project base dir as the top-level
# This avoids ambiguous imports of same-named test modules (e.g. test_api)
# across multiple app test directories.
TEST_DISCOVER_TOP_LEVEL = str(BASE_DIR)
TEST_RUNNER = 'config.test_runner.ForcePackageDiscoverRunner'

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# JWT Settings
# ACCESS_TOKEN_LIFETIME: 15 minutes chosen for this project because:
#   - Sensitive roles exist (System Administrator, Law Enforcement, Traffic Control Officer)
#   - Logout does not immediately invalidate access tokens (stateless JWTs)
#   - Shorter lifetime limits the window of exposure if a token is intercepted
#   - Clients use refresh token rotation (ROTATE_REFRESH_TOKENS=True) to stay logged in
#   - 15 minutes is the industry-standard recommendation for high-security APIs
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Set to True in development only

# Allow WebSocket connections from the same origins
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
]

# ---------------------------------------------------------------------------
# Celery — Phase 4E: analytics aggregation scheduled tasks
# ---------------------------------------------------------------------------
# High-throughput async ingest queue is deferred to Phase 5.
# This configuration covers only the periodic analytics aggregation jobs.

_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
_REDIS_DB   = os.environ.get("REDIS_DB", "0")
_REDIS_URL  = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}"

CELERY_BROKER_URL        = _REDIS_URL
CELERY_RESULT_BACKEND    = _REDIS_URL
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE          = "UTC"
CELERY_ENABLE_UTC        = True

# ---------------------------------------------------------------------------
# Django Channels — Phase 5: WebSocket real-time push
# ---------------------------------------------------------------------------
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(
                os.environ.get("REDIS_HOST", "localhost"),
                int(os.environ.get("REDIS_PORT", "6379")),
            )],
            "prefix": "trafficops",
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# MediaMTX media gateway (Phase 5)
# MEDIAMTX_URL is used by server-side probes and internal container networking.
MEDIAMTX_URL = os.environ.get("MEDIAMTX_URL", "http://localhost:8888")
MEDIAMTX_BROWSER_URL = os.environ.get("MEDIAMTX_BROWSER_URL")
MEDIAMTX_RTSP = os.environ.get("MEDIAMTX_RTSP", "rtsp://localhost:8554")

# Periodic task schedule (Celery Beat)
from celery.schedules import crontab  # noqa: E402 — Celery must be installed

CELERY_BEAT_SCHEDULE = {
    # Camera health probe — every 60 seconds
    "check-camera-connectivity": {
        "task":     "apps.cameras.tasks.check_camera_connectivity",
        "schedule": 60.0,   # seconds
    },
    # Aggregate hourly flow summaries — runs at the top of every hour
    "aggregate-flow-hourly": {
        "task":     "apps.analytics.tasks.aggregate_flow_hourly",
        "schedule": crontab(minute=0),  # every hour at :00
    },
    # Aggregate daily flow summaries — runs at 00:05 UTC each day
    "aggregate-flow-daily": {
        "task":     "apps.analytics.tasks.aggregate_flow_daily",
        "schedule": crontab(hour=0, minute=5),
    },
    # Aggregate daily incident reports — runs at 00:10 UTC each day
    "aggregate-incidents-daily": {
        "task":     "apps.analytics.tasks.aggregate_incidents_daily",
        "schedule": crontab(hour=0, minute=10),
    },
    # Aggregate daily violation summaries — runs at 00:15 UTC each day
    "aggregate-violations-daily": {
        "task":     "apps.analytics.tasks.aggregate_violations_daily",
        "schedule": crontab(hour=0, minute=15),
    },
}
