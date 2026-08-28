"""
Production settings for config project.

Settings specific to production environment.
"""

from .base import *  # noqa
import os

from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# SECRET_KEY fail-fast guard
# ---------------------------------------------------------------------------
# In production, SECRET_KEY MUST be provided via environment variable.
# If it is missing or still set to the development fallback, Django will
# refuse to start.  This prevents accidentally deploying with an insecure key.
_secret_key = os.environ.get('SECRET_KEY', '')
_insecure_prefix = 'django-insecure'

if not _secret_key:
    raise ImproperlyConfigured(
        "SECRET_KEY environment variable is not set. "
        "Generate a strong key with: "
        "python -c \"from django.core.management.utils import get_random_secret_key; "
        "print(get_random_secret_key())\""
    )

if _secret_key.startswith(_insecure_prefix):
    raise ImproperlyConfigured(
        "SECRET_KEY starts with 'django-insecure', which is not allowed in production. "
        "Set a strong random SECRET_KEY in your environment."
    )

if len(_secret_key) < 50:
    raise ImproperlyConfigured(
        f"SECRET_KEY is only {len(_secret_key)} characters. "
        "Production SECRET_KEY must be at least 50 characters for HS256 JWT signing."
    )

# Override SECRET_KEY with the validated value (base.py already read it, but
# we re-assert here to make the production guard explicit).
SECRET_KEY = _secret_key  # noqa: F811

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database - Use PostgreSQL in production
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

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Email backend (SMTP in production)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
