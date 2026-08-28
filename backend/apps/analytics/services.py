"""
Analytics aggregation services — Phase 4E.

These functions are called by Celery tasks (apps.analytics.tasks).
They must NEVER be called from within a web request handler.
(data-flow.md: "Analytics: Written by cron/Celery tasks, never by web requests.")

Design
------
Each function is idempotent: it uses get_or_create with a unique key of
(segment, period_type, period_start).  Running the same function twice for the
same window is safe — the second call is a no-op.

Dependency direction
--------------------
analytics.services → traffic, violations, roads  (read-only)
traffic / violations must NOT import analytics   (forbidden)

No audit events are emitted — architecture explicitly says "Audit: No".
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_hour_window(dt: datetime) -> tuple[datetime, datetime]:
    """Return the (period_start, period_end) for the UTC hour containing dt."""
    start = dt.replace(minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
    return start, start + timedelta(hours=1)


def _utc_day_window(dt: datetime) -> tuple[datetime, datetime]:
    """Return the (period_start, period_end) for the UTC day containing dt."""
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
    return start, start + timedelta(days=1)


# ---------------------------------------------------------------------------
# TrafficFlowSummary — hourly
# ---------------------------------------------------------------------------

def aggregate_flow_for_hour(period_start: datetime) -> int:
    """
    Aggregate TrafficMeasurement data into TrafficFlowSummary for one UTC hour.

    Returns the number of new summary records created (0 if all already existed).
    """
    from apps.analytics.models import TrafficFlowSummary, PeriodType
    from apps.traffic.models import TrafficMeasurement
    from apps.roads.models import RoadSegment
    from django.db.models import Avg, Sum, Count

    period_end = period_start + timedelta(hours=1)
    created_count = 0

    # Get all segments that have measurements in this window
    qs = (
        TrafficMeasurement.objects
        .filter(measured_at__gte=period_start, measured_at__lt=period_end)
        .values("segment")
        .annotate(
            total_vehicles=Sum("vehicle_count"),
            avg_speed=Avg("avg_speed_kmh"),
            avg_occ=Avg("occupancy_pct"),
            samples=Count("id"),
        )
    )

    with transaction.atomic():
        for row in qs:
            seg_id = row["segment"]
            _, created = TrafficFlowSummary.objects.get_or_create(
                segment_id=seg_id,
                period_type=PeriodType.HOURLY,
                period_start=period_start,
                defaults={
                    "period_end":           period_end,
                    "total_vehicle_count":  row["total_vehicles"],
                    "avg_speed_kmh":        row["avg_speed"],
                    "avg_occupancy_pct":    row["avg_occ"],
                    "sample_count":         row["samples"] or 0,
                },
            )
            if created:
                created_count += 1

    logger.info(
        "aggregate_flow_for_hour: period=%s created=%d",
        period_start.isoformat(), created_count,
    )
    return created_count


def aggregate_flow_hourly() -> int:
    """Aggregate the most recently completed UTC hour."""
    now = timezone.now()
    # Most recently completed hour = now's hour - 1
    period_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    return aggregate_flow_for_hour(period_start)


# ---------------------------------------------------------------------------
# TrafficFlowSummary — daily
# ---------------------------------------------------------------------------

def aggregate_flow_for_day(period_start: datetime) -> int:
    """
    Aggregate TrafficMeasurement data into TrafficFlowSummary for one UTC day.
    """
    from apps.analytics.models import TrafficFlowSummary, PeriodType
    from apps.traffic.models import TrafficMeasurement
    from django.db.models import Avg, Sum, Count

    period_end = period_start + timedelta(days=1)
    created_count = 0

    qs = (
        TrafficMeasurement.objects
        .filter(measured_at__gte=period_start, measured_at__lt=period_end)
        .values("segment")
        .annotate(
            total_vehicles=Sum("vehicle_count"),
            avg_speed=Avg("avg_speed_kmh"),
            avg_occ=Avg("occupancy_pct"),
            samples=Count("id"),
        )
    )

    with transaction.atomic():
        for row in qs:
            _, created = TrafficFlowSummary.objects.get_or_create(
                segment_id=row["segment"],
                period_type=PeriodType.DAILY,
                period_start=period_start,
                defaults={
                    "period_end":          period_end,
                    "total_vehicle_count": row["total_vehicles"],
                    "avg_speed_kmh":       row["avg_speed"],
                    "avg_occupancy_pct":   row["avg_occ"],
                    "sample_count":        row["samples"] or 0,
                },
            )
            if created:
                created_count += 1

    logger.info(
        "aggregate_flow_for_day: period=%s created=%d",
        period_start.date(), created_count,
    )
    return created_count


def aggregate_flow_daily() -> int:
    """Aggregate yesterday's UTC day."""
    yesterday_start = (timezone.now() - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return aggregate_flow_for_day(yesterday_start)


# ---------------------------------------------------------------------------
# IncidentReport — daily
# ---------------------------------------------------------------------------

def aggregate_incidents_for_day(period_start: datetime) -> int:
    """
    Aggregate TrafficIncident data into IncidentReport for one UTC day.
    Produces one city-wide record (segment=None) plus one per affected segment.
    """
    from apps.analytics.models import IncidentReport, PeriodType
    from apps.traffic.models import TrafficIncident

    period_end = period_start + timedelta(days=1)
    created_count = 0

    incidents = list(
        TrafficIncident.objects.filter(
            occurred_at__gte=period_start,
            occurred_at__lt=period_end,
        ).prefetch_related("segments")
    )

    # Build per-segment aggregates
    # seg_id → {"total": int, "by_type": {}, "by_state": {}}
    aggregates: dict = defaultdict(lambda: {"total": 0, "by_type": defaultdict(int), "by_state": defaultdict(int)})
    city_agg = {"total": 0, "by_type": defaultdict(int), "by_state": defaultdict(int)}

    for inc in incidents:
        city_agg["total"] += 1
        city_agg["by_type"][inc.incident_type] += 1
        city_agg["by_state"][inc.state] += 1
        for seg in inc.segments.all():
            aggregates[seg.pk]["total"] += 1
            aggregates[seg.pk]["by_type"][inc.incident_type] += 1
            aggregates[seg.pk]["by_state"][inc.state] += 1

    def _save(seg_id, agg):
        nonlocal created_count
        _, created = IncidentReport.objects.get_or_create(
            segment_id=seg_id,
            period_type=PeriodType.DAILY,
            period_start=period_start,
            defaults={
                "period_end":       period_end,
                "total_incidents":  agg["total"],
                "by_type":          dict(agg["by_type"]),
                "by_state":         dict(agg["by_state"]),
            },
        )
        if created:
            created_count += 1

    with transaction.atomic():
        # City-wide record
        _save(None, city_agg)
        # Per-segment records
        for seg_id, agg in aggregates.items():
            _save(seg_id, agg)

    logger.info(
        "aggregate_incidents_for_day: period=%s created=%d",
        period_start.date(), created_count,
    )
    return created_count


def aggregate_incidents_daily() -> int:
    """Aggregate yesterday's incidents."""
    yesterday_start = (timezone.now() - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return aggregate_incidents_for_day(yesterday_start)


# ---------------------------------------------------------------------------
# ViolationSummary — daily
# ---------------------------------------------------------------------------

def aggregate_violations_for_day(period_start: datetime) -> int:
    """
    Aggregate TrafficViolation data into ViolationSummary for one UTC day.
    Produces one city-wide record plus one per affected segment.
    """
    from apps.analytics.models import ViolationSummary, PeriodType
    from apps.violations.models import TrafficViolation

    period_end = period_start + timedelta(days=1)
    created_count = 0

    violations = list(
        TrafficViolation.objects.filter(
            occurred_at__gte=period_start,
            occurred_at__lt=period_end,
            is_active=True,
        ).select_related("segment")
    )

    aggregates: dict = defaultdict(lambda: {"total": 0, "by_type": defaultdict(int)})
    city_agg = {"total": 0, "by_type": defaultdict(int)}

    for v in violations:
        city_agg["total"] += 1
        city_agg["by_type"][v.violation_type] += 1
        if v.segment_id:
            aggregates[v.segment_id]["total"] += 1
            aggregates[v.segment_id]["by_type"][v.violation_type] += 1

    def _save(seg_id, agg):
        nonlocal created_count
        _, created = ViolationSummary.objects.get_or_create(
            segment_id=seg_id,
            period_type=PeriodType.DAILY,
            period_start=period_start,
            defaults={
                "period_end":       period_end,
                "total_violations": agg["total"],
                "by_type":          dict(agg["by_type"]),
            },
        )
        if created:
            created_count += 1

    with transaction.atomic():
        _save(None, city_agg)
        for seg_id, agg in aggregates.items():
            _save(seg_id, agg)

    logger.info(
        "aggregate_violations_for_day: period=%s created=%d",
        period_start.date(), created_count,
    )
    return created_count


def aggregate_violations_daily() -> int:
    """Aggregate yesterday's violations."""
    yesterday_start = (timezone.now() - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return aggregate_violations_for_day(yesterday_start)
