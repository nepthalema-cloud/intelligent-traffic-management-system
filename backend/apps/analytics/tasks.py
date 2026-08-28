"""
Celery tasks for analytics aggregation — Phase 4E.

Each task is a thin wrapper that delegates to the service layer.
Tasks are registered in the CELERY_BEAT_SCHEDULE in config/settings/base.py.

Error handling: tasks catch all exceptions and log them rather than propagating,
so a single aggregation failure does not stop the beat scheduler.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.analytics.tasks.aggregate_flow_hourly", bind=True, max_retries=3)
def aggregate_flow_hourly(self):
    """Aggregate the most recently completed UTC hour of TrafficMeasurement data."""
    try:
        from apps.analytics.services import aggregate_flow_hourly as _run
        created = _run()
        logger.info("aggregate_flow_hourly: created %d summaries", created)
        return {"created": created}
    except Exception as exc:
        logger.error("aggregate_flow_hourly failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="apps.analytics.tasks.aggregate_flow_daily", bind=True, max_retries=3)
def aggregate_flow_daily(self):
    """Aggregate the previous UTC day of TrafficMeasurement data."""
    try:
        from apps.analytics.services import aggregate_flow_daily as _run
        created = _run()
        logger.info("aggregate_flow_daily: created %d summaries", created)
        return {"created": created}
    except Exception as exc:
        logger.error("aggregate_flow_daily failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name="apps.analytics.tasks.aggregate_incidents_daily", bind=True, max_retries=3)
def aggregate_incidents_daily(self):
    """Aggregate the previous UTC day of TrafficIncident data."""
    try:
        from apps.analytics.services import aggregate_incidents_daily as _run
        created = _run()
        logger.info("aggregate_incidents_daily: created %d reports", created)
        return {"created": created}
    except Exception as exc:
        logger.error("aggregate_incidents_daily failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name="apps.analytics.tasks.aggregate_violations_daily", bind=True, max_retries=3)
def aggregate_violations_daily(self):
    """Aggregate the previous UTC day of TrafficViolation data."""
    try:
        from apps.analytics.services import aggregate_violations_daily as _run
        created = _run()
        logger.info("aggregate_violations_daily: created %d summaries", created)
        return {"created": created}
    except Exception as exc:
        logger.error("aggregate_violations_daily failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)
