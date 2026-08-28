"""
Analytics domain models — Phase 4E.

Architecture source: domain-model.md
--------------------------------------
  TrafficFlowSummary — Hourly/daily aggregated flow per segment. Append-only. No audit.
  IncidentReport     — Summarized incident statistics per area/period. Append-only. No audit.
  ViolationSummary   — Aggregated violation counts by type/location/period. Append-only. No audit.

Design principles (app-boundaries.md + data-flow.md):
  - Populated by background Celery jobs ONLY — never by web requests.
  - Append-only: save() raises RuntimeError on update; delete() always raises.
  - Unique constraints prevent duplicate summaries for the same window.
  - No audit events — architecture explicitly says "Audit: No" for these entities.
  - Dependency: analytics → roads, traffic, violations (read). Never the reverse.

Assumptions (architecture is silent on these):
  1. IncidentReport and ViolationSummary use DAILY aggregation in Phase 4E.
     Period type field is kept extensible (CharField choices) so weekly/monthly
     can be added later via migration without a schema redesign.
  2. segment=NULL means city-wide aggregate (all segments combined).
  3. period_start is inclusive, period_end is exclusive (standard convention).
  4. JSONField used for breakdown dicts (by_type, by_state) — keeps schema
     simple without requiring one row per sub-category.
"""

from django.db import models


def _append_only_save(instance, *args, **kwargs):
    if not instance._state.adding:
        raise RuntimeError(
            f"{instance.__class__.__name__} records are append-only "
            "and may not be modified after creation."
        )
    super(instance.__class__, instance).save(*args, **kwargs)


def _append_only_delete(instance, *args, **kwargs):
    raise RuntimeError(
        f"{instance.__class__.__name__} records are append-only "
        "and may not be deleted."
    )


class PeriodType(models.TextChoices):
    HOURLY = "hourly", "Hourly"
    DAILY  = "daily",  "Daily"


# ---------------------------------------------------------------------------
# TrafficFlowSummary
# ---------------------------------------------------------------------------

class TrafficFlowSummary(models.Model):
    """
    Pre-aggregated traffic flow metrics for a road segment over a time window.

    Populated by the ``aggregate_flow_hourly`` and ``aggregate_flow_daily``
    Celery tasks.  Never written directly via the API.

    Fields
    ------
    segment            : FK RoadSegment (SET_NULL, nullable — null = city-wide)
    period_type        : str — 'hourly' | 'daily'
    period_start       : datetime (UTC, inclusive)
    period_end         : datetime (UTC, exclusive)
    total_vehicle_count: int (nullable — may be absent if no count readings)
    avg_speed_kmh      : float (nullable)
    avg_occupancy_pct  : float (nullable)
    sample_count       : int — number of TrafficMeasurement rows aggregated
    created_at         : datetime
    """

    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="flow_summaries",
    )
    period_type = models.CharField(
        max_length=10, choices=PeriodType.choices, db_index=True
    )
    period_start = models.DateTimeField(db_index=True)
    period_end   = models.DateTimeField()
    total_vehicle_count = models.PositiveIntegerField(null=True, blank=True)
    avg_speed_kmh       = models.FloatField(null=True, blank=True)
    avg_occupancy_pct   = models.FloatField(null=True, blank=True)
    sample_count = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "analytics"
        verbose_name = "Traffic Flow Summary"
        verbose_name_plural = "Traffic Flow Summaries"
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["segment", "period_type", "period_start"],
                name="analytics_flow_segment_type_start_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["period_type", "period_start"],
                name="analytics_flow_type_start_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        _append_only_save(self, *args, **kwargs)

    def delete(self, *args, **kwargs):
        _append_only_delete(self, *args, **kwargs)

    def __str__(self) -> str:
        seg = f"seg:{self.segment_id}" if self.segment_id else "city-wide"
        return f"FlowSummary [{self.period_type}] {self.period_start:%Y-%m-%d %H:%M} {seg}"


# ---------------------------------------------------------------------------
# IncidentReport
# ---------------------------------------------------------------------------

class IncidentReport(models.Model):
    """
    Daily summary of traffic incidents per segment (or city-wide).

    Populated by the ``aggregate_incidents_daily`` Celery task.

    Fields
    ------
    segment        : FK RoadSegment (SET_NULL, nullable — null = city-wide)
    period_type    : str — 'daily' in Phase 4E (extensible)
    period_start   : datetime (UTC, inclusive — start of day)
    period_end     : datetime (UTC, exclusive — start of next day)
    total_incidents: int
    by_type        : JSON — {"accident": 2, "road_closure": 1, ...}
    by_state       : JSON — {"resolved": 2, "closed": 1, ...}
    created_at     : datetime
    """

    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="incident_reports",
    )
    period_type  = models.CharField(
        max_length=10, choices=PeriodType.choices,
        default=PeriodType.DAILY, db_index=True,
    )
    period_start  = models.DateTimeField(db_index=True)
    period_end    = models.DateTimeField()
    total_incidents = models.PositiveIntegerField(default=0)
    by_type       = models.JSONField(default=dict)
    by_state      = models.JSONField(default=dict)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "analytics"
        verbose_name = "Incident Report"
        verbose_name_plural = "Incident Reports"
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["segment", "period_type", "period_start"],
                name="analytics_inc_segment_type_start_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["period_type", "period_start"],
                name="analytics_inc_type_start_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        _append_only_save(self, *args, **kwargs)

    def delete(self, *args, **kwargs):
        _append_only_delete(self, *args, **kwargs)

    def __str__(self) -> str:
        seg = f"seg:{self.segment_id}" if self.segment_id else "city-wide"
        return f"IncidentReport [{self.period_type}] {self.period_start:%Y-%m-%d} {seg}"


# ---------------------------------------------------------------------------
# ViolationSummary
# ---------------------------------------------------------------------------

class ViolationSummary(models.Model):
    """
    Daily summary of traffic violations per segment (or city-wide).

    Populated by the ``aggregate_violations_daily`` Celery task.

    Fields
    ------
    segment          : FK RoadSegment (SET_NULL, nullable — null = city-wide)
    period_type      : str — 'daily' in Phase 4E (extensible)
    period_start     : datetime (UTC, inclusive)
    period_end       : datetime (UTC, exclusive)
    total_violations : int
    by_type          : JSON — {"speeding": 5, "red_light": 2, ...}
    created_at       : datetime
    """

    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="violation_summaries",
    )
    period_type  = models.CharField(
        max_length=10, choices=PeriodType.choices,
        default=PeriodType.DAILY, db_index=True,
    )
    period_start  = models.DateTimeField(db_index=True)
    period_end    = models.DateTimeField()
    total_violations = models.PositiveIntegerField(default=0)
    by_type       = models.JSONField(default=dict)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "analytics"
        verbose_name = "Violation Summary"
        verbose_name_plural = "Violation Summaries"
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["segment", "period_type", "period_start"],
                name="analytics_viol_segment_type_start_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["period_type", "period_start"],
                name="analytics_viol_type_start_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        _append_only_save(self, *args, **kwargs)

    def delete(self, *args, **kwargs):
        _append_only_delete(self, *args, **kwargs)

    def __str__(self) -> str:
        seg = f"seg:{self.segment_id}" if self.segment_id else "city-wide"
        return f"ViolationSummary [{self.period_type}] {self.period_start:%Y-%m-%d} {seg}"
