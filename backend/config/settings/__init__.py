"""
Django settings configuration.

Environment-specific settings are loaded based on the DJANGO_SETTINGS_MODULE environment variable.
Default to development settings if not specified.
"""

import os

# Default to development settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

from .development import *  # noqa
