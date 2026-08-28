"""
Development settings for config project.

Settings specific to development environment.
"""

from .base import *  # noqa
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow any LAN IP to reach Daphne in development.
# For multi-PC testing: run Daphne with -b 0.0.0.0 and add your PC's LAN IP here,
# or keep '*' for fully open dev access.
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '*']

# Database settings are inherited from base.py
# Base settings will use SQLite if DB_NAME is not set in environment

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# CORS settings (for development)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
]
CORS_ALLOW_ALL_ORIGINS = True  # Allow all origins in development

# Email backend (console in development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# MediaMTX HLS port — used by CameraStreamView to build browser-reachable URLs.
# The view derives the hostname from the HTTP request (so remote browsers get
# the correct IP), but needs this port to construct the full URL.
MEDIAMTX_HLS_PORT = int(os.environ.get("MEDIAMTX_HLS_PORT", "8888"))

# Do not set MEDIAMTX_URL here — leave it unset so the view uses request-derived
# host. Only set it in production when MediaMTX is on a different machine.
