"""
Road infrastructure models.

Entities
--------
Intersection  — a named junction point (defined before RoadSegment to allow FK)
Road          — a named road (e.g. "Main Street")
RoadSegment   — a directed portion of a Road, optionally connecting two Intersections
Lane          — a single lane within a RoadSegment

Lifecycle
---------
All entities support soft-deactivation via ``is_active``.  Hard deletion is
intentionally not exposed through the API; records are never physically removed
because they serve as reference data for other domains (cameras, traffic events,
violations).  Deactivation signals that the record is no longer operationally
current without destroying historical integrity.

Audit
-----
All mutating operations generate audit events via ``apps.audit.services``.
Audit calls are made in the service layer, not in models.

Relationships
-------------
Road          1──* RoadSegment
Intersection  1──* RoadSegment (as start_intersection, optional)
Intersection  1──* RoadSegment (as end_intersection, optional)
RoadSegment   1──* Lane

The start/end intersection FKs are nullable because a segment may be entered
into the system before intersection data is complete.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Intersection(models.Model):
    """
    A named junction point where two or more road segments meet.

    Defined before RoadSegment so that the FK from RoadSegment can reference it.

    Fields
    ------
    name        : str  — human-readable name (e.g. "Main St / Oak Ave")
    description : str  — optional operational notes
    latitude    : float — WGS84 latitude (nullable; populated when GIS data is available)
    longitude   : float — WGS84 longitude (nullable)
    is_active   : bool  — soft-deactivation flag
    created_at  : datetime — UTC creation timestamp
    updated_at  : datetime — UTC last-modification timestamp
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    latitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "roads"
        verbose_name = "Intersection"
        verbose_name_plural = "Intersections"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Road(models.Model):
    """
    A named road — the top-level grouping for road segments.

    A Road is primarily metadata: it gives a human-readable name to a
    collection of related segments.  It does not store geometric data.

    Fields
    ------
    name        : str  — unique road name (e.g. "Main Street")
    description : str  — optional notes
    road_type   : str  — classification (motorway, primary, secondary, etc.)
    is_active   : bool  — soft-deactivation flag
    created_at  : datetime
    updated_at  : datetime
    """

    class RoadType(models.TextChoices):
        MOTORWAY   = "motorway",   "Motorway"
        PRIMARY    = "primary",    "Primary Road"
        SECONDARY  = "secondary",  "Secondary Road"
        TERTIARY   = "tertiary",   "Tertiary Road"
        RESIDENTIAL = "residential", "Residential"
        SERVICE    = "service",    "Service Road"
        OTHER      = "other",      "Other"

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    road_type = models.CharField(
        max_length=20,
        choices=RoadType.choices,
        default=RoadType.OTHER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "roads"
        verbose_name = "Road"
        verbose_name_plural = "Roads"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RoadSegment(models.Model):
    """
    A directed portion of a Road, optionally connecting two Intersections.

    A segment represents a single physical stretch of road between two
    reference points.  It carries operational attributes (speed limit,
    lane count) that may be queried by traffic management systems.

    Fields
    ------
    road                : FK Road — the road this segment belongs to
    name                : str — optional descriptive name (e.g. "northbound section")
    start_intersection  : FK Intersection (nullable) — segment origin
    end_intersection    : FK Intersection (nullable) — segment destination
    length_meters       : float — segment length in metres (positive)
    speed_limit_kmh     : int — posted speed limit in km/h (positive)
    lane_count          : int — total number of lanes (positive)
    direction           : str — directionality (bidirectional, one_way_forward, one_way_reverse)
    is_active           : bool — soft-deactivation flag
    created_at          : datetime
    updated_at          : datetime
    """

    class Direction(models.TextChoices):
        BIDIRECTIONAL    = "bidirectional",    "Bidirectional"
        ONE_WAY_FORWARD  = "one_way_forward",  "One-way (Forward)"
        ONE_WAY_REVERSE  = "one_way_reverse",  "One-way (Reverse)"

    road = models.ForeignKey(
        Road,
        on_delete=models.PROTECT,
        related_name="segments",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    start_intersection = models.ForeignKey(
        Intersection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outgoing_segments",
    )
    end_intersection = models.ForeignKey(
        Intersection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incoming_segments",
    )
    length_meters = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
    )
    speed_limit_kmh = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(300)],
    )
    lane_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        default=Direction.BIDIRECTIONAL,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "roads"
        verbose_name = "Road Segment"
        verbose_name_plural = "Road Segments"
        ordering = ["road", "id"]
        indexes = [
            models.Index(fields=["road", "is_active"], name="roads_seg_road_active_idx"),
        ]

    def __str__(self) -> str:
        name_part = f" — {self.name}" if self.name else ""
        return f"{self.road.name}{name_part} (segment {self.pk})"


class Lane(models.Model):
    """
    A single lane within a road segment.

    Fields
    ------
    segment     : FK RoadSegment — the segment this lane belongs to
    lane_number : int — 1-based lane number within the segment (left to right)
    lane_type   : str — operational classification
    description : str — optional notes
    is_active   : bool — soft-deactivation flag
    created_at  : datetime
    updated_at  : datetime
    """

    class LaneType(models.TextChoices):
        TRAVEL      = "travel",      "Travel Lane"
        TURN_LEFT   = "turn_left",   "Left Turn Lane"
        TURN_RIGHT  = "turn_right",  "Right Turn Lane"
        BUS         = "bus",         "Bus Lane"
        CYCLE       = "cycle",       "Cycle Lane"
        EMERGENCY   = "emergency",   "Emergency Lane"
        PARKING     = "parking",     "Parking Lane"
        OTHER       = "other",       "Other"

    segment = models.ForeignKey(
        RoadSegment,
        on_delete=models.PROTECT,
        related_name="lanes",
    )
    lane_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    lane_type = models.CharField(
        max_length=20,
        choices=LaneType.choices,
        default=LaneType.TRAVEL,
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "roads"
        verbose_name = "Lane"
        verbose_name_plural = "Lanes"
        ordering = ["segment", "lane_number"]
        # A lane_number must be unique within a segment
        unique_together = [("segment", "lane_number")]
        indexes = [
            models.Index(fields=["segment", "is_active"], name="roads_lane_seg_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Lane {self.lane_number} ({self.lane_type}) — segment {self.segment_id}"
