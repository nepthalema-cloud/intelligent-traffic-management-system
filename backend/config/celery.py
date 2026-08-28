"""
Celery application instance for the AI-Powered Smart Traffic Management System.

Phase 4E: Celery is introduced solely for scheduled analytics aggregation tasks.
The high-throughput async ingest queue (Phase 5) is a separate concern and is
NOT configured here.

Broker/backend: Redis (already in infrastructure — redis>=5.0.0 in requirements).
Redis connection uses REDIS_HOST / REDIS_PORT env vars from .env.

Usage:
    # Start worker (development)
    celery -A config worker -l info

    # Start beat scheduler (development)
    celery -A config beat -l info

    # Combined (development only — do not use in production)
    celery -A config worker --beat -l info
"""

import os
from celery import Celery

# Django settings module must be set before importing any Django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("traffic_mgmt")

# Read Celery configuration from Django settings, using the CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()
