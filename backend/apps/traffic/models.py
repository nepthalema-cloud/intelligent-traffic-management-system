"""
Traffic signal domain models — Phase 4C.1.
Traffic measurement model — Phase 4C.2.
Traffic event model — Phase 4C.3.

Entities
--------
TrafficSignal      — configurable signal controller at an intersection
SignalPhase        — timing phase belonging to a TrafficSignal
TrafficMeasurement — single sensor/camera reading (append-only, high-volume)
TrafficEvent       — operator-created or AI-flagged notable event (mutable)

Lifecycle
---------
TrafficSignal and SignalPhase use soft-deactivation (``is_active``).
TrafficMeasurement is APPEND-ONLY — immutable once created.
TrafficEvent is MUTABLE — full create/update/deactivate lifecycle with audit.

Relationships
-------------
roads.Intersection  1 ──* TrafficSignal   (PROTECT)
TrafficSignal       1 ──* SignalPhase      (PROTECT)
roads.RoadSegment   1 ──* TrafficMeasurement (SET_NULL)
cameras.Camera      1 ──* TrafficMeasurement (SET_NULL)
cameras.Sensor      1 ──* TrafficMeasurement (SET_NULL)
roads.RoadSegment   1 ──* TrafficEvent     (SET_NULL, nullable)
roads.Intersection  1 ──* TrafficEvent     (SET_NULL, nullable)
accounts.User       1 ──* TrafficEvent     (SET_NULL, nullable — created_by)

Architectural decisions
-----------------------
Phase 4C.2: TrafficMeasurement source is exclusively camera XOR sensor;
            NOT audited individually (volume too high).
Phase 4C.3: TrafficEvent.segment and .intersection are both nullable — an
            event may reference either, neither, or one of them.
            SET_NULL is used so infrastructure decommissioning does not
            delete event history.
            created_by uses SET_NULL so user deletion does not cascade to
            event history.
"""

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class TrafficSignal(models.Model):
    """
    A configurable traffic signal controller installed at an intersection.

    Fields
    ------
    name                  : str  — unique human-readable name (e.g. "SIGNAL-001")
    intersection          : FK roads.Intersection (PROTECT, NOT NULL)
    controller_type       : str  — hardware/protocol type (optional)
    controller_identifier : str  — serial number / asset tag (optional)
    is_active             : bool — administrative soft-deactivation flag
    created_at            : datetime
    updated_at            : datetime
    """

    name = models.CharField(max_length=150, unique=True)
    intersection = models.ForeignKey(
        "roads.Intersection",
        on_delete=models.PROTECT,
        related_name="traffic_signals",
    )
    controller_type = models.CharField(max_length=100, blank=True, default="")
    controller_identifier = models.CharField(max_length=150, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "traffic"
        verbose_name = "Traffic Signal"
        verbose_name_plural = "Traffic Signals"
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["intersection", "is_active"],
                name="traffic_sig_int_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} @ {self.intersection}"


class SignalPhase(models.Model):
    """
    A timing phase configured for a TrafficSignal.

    Fields
    ------
    signal                : FK TrafficSignal (PROTECT, NOT NULL)
    phase_number          : int — 1-based phase number, unique within signal
    name                  : str — descriptive name (e.g. "North-South Green")
    movement              : str — optional movement description
    minimum_green_seconds : int — minimum green duration (≥ 0, ≤ maximum_green)
    maximum_green_seconds : int — maximum green duration (≥ minimum_green)
    yellow_seconds        : int — yellow/amber duration (≥ 0)
    all_red_seconds       : int — all-red clearance duration (≥ 0)
    is_active             : bool — soft-deactivation flag
    created_at            : datetime
    updated_at            : datetime
    """

    signal = models.ForeignKey(
        TrafficSignal,
        on_delete=models.PROTECT,
        related_name="phases",
    )
    phase_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    name = models.CharField(max_length=100)
    movement = models.CharField(max_length=150, blank=True, default="")
    minimum_green_seconds = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
    )
    maximum_green_seconds = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
    )
    yellow_seconds = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
    )
    all_red_seconds = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "traffic"
        verbose_name = "Signal Phase"
        verbose_name_plural = "Signal Phases"
        ordering = ["signal", "phase_number"]
        unique_together = [("signal", "phase_number")]
        indexes = [
            models.Index(
                fields=["signal", "is_active"],
                name="traffic_phase_sig_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Phase {self.phase_number} ({self.name}) — {self.signal.name}"


class TrafficMeasurement(models.Model):
    """
    A single traffic measurement record produced by a camera or sensor.

    Append-only — no PATCH/PUT/DELETE endpoints or service methods exist.
    Records are immutable once created.

    Architecture decisions (Phase 4C.2)
    ------------------------------------
    - source is camera XOR sensor (exactly one, enforced at serializer level)
    - NOT audited individually (volume too high — see domain-model.md)
    - segment FK is SET_NULL so historical records survive infrastructure changes
    - ordering is newest-first (measured_at DESC)
    - vehicle_count, avg_speed_kmh, occupancy_pct are all nullable to support
      partial measurements (e.g. a sensor that only measures count)

    Fields
    ------
    segment        : FK roads.RoadSegment (nullable, SET_NULL)
    camera         : FK cameras.Camera (nullable, SET_NULL) — source device
    sensor         : FK cameras.Sensor (nullable, SET_NULL) — source device
    measured_at    : datetime — when the measurement was taken (required)
    vehicle_count  : int >= 0 — number of vehicles counted (nullable)
    avg_speed_kmh  : float >= 0 — average speed in km/h (nullable)
    occupancy_pct  : float 0–100 — lane occupancy percentage (nullable)
    created_at     : datetime — when this record was inserted
    """

    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="measurements",
    )
    camera = models.ForeignKey(
        "cameras.Camera",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="measurements",
    )
    sensor = models.ForeignKey(
        "cameras.Sensor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="measurements",
    )
    measured_at = models.DateTimeField(db_index=True)
    vehicle_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    avg_speed_kmh = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
    )
    occupancy_pct = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Phase 5: track data provenance
    class MeasurementSource(models.TextChoices):
        AI     = "ai",     "AI Service"
        SENSOR = "sensor", "Physical Sensor"
        MANUAL = "manual", "Manual Entry"
        DEMO   = "demo",   "Demo / Seed Data"

    data_source = models.CharField(
        max_length=10,
        choices=MeasurementSource.choices,
        default=MeasurementSource.DEMO,
        db_index=True,
    )

    class Meta:
        app_label = "traffic"
        verbose_name = "Traffic Measurement"
        verbose_name_plural = "Traffic Measurements"
        ordering = ["-measured_at"]
        indexes = [
            models.Index(
                fields=["segment", "measured_at"],
                name="traffic_meas_seg_time_idx",
            ),
            models.Index(
                fields=["camera", "measured_at"],
                name="traffic_meas_cam_time_idx",
            ),
            models.Index(
                fields=["sensor", "measured_at"],
                name="traffic_meas_sen_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        """Enforce append-only: block updates to existing records."""
        if self._state.adding is False:
            raise RuntimeError(
                "TrafficMeasurement records are append-only and may not be modified."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enforce append-only: block deletion of measurement records."""
        raise RuntimeError(
            "TrafficMeasurement records are append-only and may not be deleted."
        )

    def __str__(self) -> str:
        source = (
            f"camera:{self.camera_id}"
            if self.camera_id
            else f"sensor:{self.sensor_id}"
        )
        return f"Measurement [{self.measured_at}] {source} seg:{self.segment_id}"


class TrafficEvent(models.Model):
    """
    An operator-created or AI-flagged notable traffic event.

    Architecture source: domain-model.md
    ------------------------------------
    - Mutability: Mutable (create / update / soft-deactivate)
    - Audit: Yes — creation, updates, and status changes are audited
    - Relationships: may reference a RoadSegment or Intersection (both nullable)
    - created_by: the User who recorded/created the event (nullable)

    Assumptions (Phase 4C.3 — not specified by architecture docs)
    -------------------------------------------------------------
    1. event_type choices: congestion, incident, roadwork, weather,
       signal_fault, other — derived from the architecture example
       "congestion detected" and common traffic domain usage.
    2. No severity field — not mentioned in architecture docs.
    3. No lifecycle states — TrafficIncident (not this phase) has lifecycle;
       TrafficEvent is simply "mutable" with soft-deactivation only.
    4. Public User access ("R selected") deferred — no public endpoint in
       this phase; documented for Phase 4C.4+ review.

    Fields
    ------
    event_type   : str   — classification of the event
    description  : str   — human-readable description (required)
    occurred_at  : datetime — when the event occurred (required)
    segment      : FK roads.RoadSegment (nullable, SET_NULL)
    intersection : FK roads.Intersection (nullable, SET_NULL)
    created_by   : FK accounts.User (nullable, SET_NULL)
    is_active    : bool  — soft-deactivation flag (active = ongoing/relevant)
    created_at   : datetime
    updated_at   : datetime
    """

    class EventType(models.TextChoices):
        CONGESTION   = "congestion",   "Congestion"
        INCIDENT     = "incident",     "Incident"
        ROADWORK     = "roadwork",     "Roadwork"
        WEATHER      = "weather",      "Weather Hazard"
        SIGNAL_FAULT = "signal_fault", "Signal Fault"
        OTHER        = "other",        "Other"

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.OTHER,
        db_index=True,
    )
    description = models.TextField()
    occurred_at = models.DateTimeField(db_index=True)
    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="traffic_events",
    )
    intersection = models.ForeignKey(
        "roads.Intersection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="traffic_events",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="traffic_events",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "traffic"
        verbose_name = "Traffic Event"
        verbose_name_plural = "Traffic Events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["event_type", "is_active"],
                name="traffic_evt_type_active_idx",
            ),
            models.Index(
                fields=["segment", "occurred_at"],
                name="traffic_evt_seg_time_idx",
            ),
            models.Index(
                fields=["intersection", "occurred_at"],
                name="traffic_evt_int_time_idx",
            ),
        ]

    def __str__(self) -> str:
        loc = (
            f"seg:{self.segment_id}"
            if self.segment_id
            else f"int:{self.intersection_id}"
            if self.intersection_id
            else "no-location"
        )
        return f"[{self.event_type}] {self.description[:40]} @ {loc}"


class TrafficIncident(models.Model):
    """
    A verified traffic incident being actively managed.

    Architecture source: domain-model.md
    ------------------------------------
    - Mutability: Mutable with lifecycle — state transitions are audited
    - Audit: Yes — every state transition
    - Purpose: verified incident (accident, road closure) actively managed
    - Relationships: may reference multiple RoadSegment records (closure span)
                    + optional Intersection + created_by User
    - TrafficEvent relationship: NOT defined in architecture → independent

    Assumptions (Phase 4C.4 — not specified by architecture docs)
    -------------------------------------------------------------
    1. Lifecycle states: reported → investigating → managing → resolved → closed
       (Only forward transitions are valid; see VALID_TRANSITIONS below.)
    2. incident_type choices: accident, road_closure, hazard, flooding, fire, other
    3. Segments use ManyToManyField (architecture says "multiple segments").
    4. No explicit TrafficEvent FK — incidents and events are independent;
       both reference infrastructure (RoadSegment/Intersection) directly.
    5. Public User access ("R selected") deferred to a future phase.

    Fields
    ------
    title         : str  — short human-readable title (required)
    description   : str  — detailed description (required)
    incident_type : str  — classification
    state         : str  — lifecycle state (reported by default)
    occurred_at   : datetime — when the incident occurred (required)
    segments      : M2M roads.RoadSegment — affected road segments (nullable)
    intersection  : FK roads.Intersection (nullable, SET_NULL)
    created_by    : FK accounts.User (nullable, SET_NULL)
    is_active     : bool — administrative soft flag (independent of state)
    created_at    : datetime
    updated_at    : datetime
    """

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    class State(models.TextChoices):
        REPORTED      = "reported",      "Reported"
        INVESTIGATING = "investigating", "Investigating"
        MANAGING      = "managing",      "Managing"
        RESOLVED      = "resolved",      "Resolved"
        CLOSED        = "closed",        "Closed"

    # Forward-only allowed transitions:
    # {current_state: [allowed_next_states]}
    VALID_TRANSITIONS: dict[str, list[str]] = {
        State.REPORTED:      [State.INVESTIGATING, State.RESOLVED],
        State.INVESTIGATING: [State.MANAGING, State.RESOLVED],
        State.MANAGING:      [State.RESOLVED],
        State.RESOLVED:      [State.CLOSED],
        State.CLOSED:        [],  # terminal
    }

    # ------------------------------------------------------------------ #
    # Incident types                                                       #
    # ------------------------------------------------------------------ #

    class IncidentType(models.TextChoices):
        ACCIDENT     = "accident",     "Accident"
        ROAD_CLOSURE = "road_closure", "Road Closure"
        HAZARD       = "hazard",       "Hazard"
        FLOODING     = "flooding",     "Flooding"
        FIRE         = "fire",         "Fire"
        OTHER        = "other",        "Other"

    # ------------------------------------------------------------------ #
    # Fields                                                              #
    # ------------------------------------------------------------------ #

    title = models.CharField(max_length=255)
    description = models.TextField()
    incident_type = models.CharField(
        max_length=20,
        choices=IncidentType.choices,
        default=IncidentType.OTHER,
        db_index=True,
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.REPORTED,
        db_index=True,
    )
    occurred_at = models.DateTimeField(db_index=True)
    segments = models.ManyToManyField(
        "roads.RoadSegment",
        blank=True,
        related_name="incidents",
    )
    intersection = models.ForeignKey(
        "roads.Intersection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "traffic"
        verbose_name = "Traffic Incident"
        verbose_name_plural = "Traffic Incidents"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["state", "is_active"],
                name="traffic_inc_state_active_idx",
            ),
            models.Index(
                fields=["incident_type", "state"],
                name="traffic_inc_type_state_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.incident_type}/{self.state}] {self.title[:50]}"
