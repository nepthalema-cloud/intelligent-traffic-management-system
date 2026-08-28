"""
Violations domain models — Phase 4D.

Entities
--------
Vehicle          — reference metadata for a vehicle (Phase 4D.1, unchanged)
TrafficViolation — a recorded violation (append-only, legal record)
ViolationEvidence— external evidence reference attached to a violation (append-only)
Citation         — formal citation issued for a violation (lifecycle: issued→contested→adjudicated)

Architecture sources
---------------------
domain-model.md:
  TrafficViolation: "A recorded violation (type, time, location, vehicle, evidence)" — append-only
  ViolationEvidence: "Images, video clips, sensor readings attached to a violation" — append-only
  Citation: "A formal citation issued for a violation" — lifecycle issued→contested→adjudicated
  Sensitive data: "Plate numbers, driver identity, evidence images"
    → access restricted to Law Enforcement and System Administrator

rbac-matrix.md:
  TrafficViolation  — Admin: CRUD, Law Enf: CRUD, Analyst: R(aggregated), Pay/Fines: R
  ViolationEvidence — Admin: CRUD, Law Enf: CR
  Citation          — Admin: CRUD, Law Enf: CRUD, Pay/Fines: R

Assumptions (documented — architecture is silent on these specifics)
---------------------------------------------------------------------
1. violation_type choices: speeding, red_light, illegal_parking, wrong_way,
   illegal_turn, other.  Architecture does not enumerate these; this is a
   minimal reasonable set.  Can be extended in a future migration.
2. ViolationEvidence.evidence_url stores an external object-storage URL.
   The architecture says evidence is in object storage (ai-integration.md);
   Django stores only the reference, not binary data.
3. evidence_type choices: image, video, sensor_reading — directly from the
   architecture description ("Images, video clips, sensor readings").
4. Citation issued→adjudicated shortcut is allowed.  The architecture uses
   arrow notation "issued → contested → adjudicated" but does not prohibit
   a direct path.  Implemented to match legal reality (some citations are
   uncontested and go straight to adjudication).
5. Citation.adjudicated is terminal — no further transitions.  Architecture
   does not specify this; treating terminal status as the minimal design.
6. No source/confidence fields on TrafficViolation.  Architecture is silent
   on these; they belong to a future AI integration phase.
7. No outcome field on Citation.  Architecture does not define one.
8. TrafficViolation.reported_by is the officer who entered it (SET_NULL so
   user deletion does not cascade to legal records).
"""

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


def _current_year() -> int:
    return timezone.now().year


# ---------------------------------------------------------------------------
# Vehicle (Phase 4D.1 — unchanged)
# ---------------------------------------------------------------------------

class Vehicle(models.Model):
    """
    Reference metadata for a physical vehicle.

    Fields
    ------
    plate_number          : str  — licence plate (required, PII)
    vehicle_type          : str  — classification (car, motorcycle, truck, etc.)
    registration_country  : str  — country of registration (optional)
    color                 : str  — vehicle colour (optional)
    make                  : str  — manufacturer brand (optional)
    model                 : str  — model name/number (optional)
    year                  : int  — manufacture year (optional, validated)
    is_active             : bool — soft-deactivation flag
    created_at            : datetime
    updated_at            : datetime
    """

    class VehicleType(models.TextChoices):
        CAR           = "car",           "Car"
        MOTORCYCLE    = "motorcycle",    "Motorcycle"
        TRUCK         = "truck",         "Truck"
        BUS           = "bus",           "Bus"
        VAN           = "van",           "Van"
        BICYCLE       = "bicycle",       "Bicycle"
        OTHER         = "other",         "Other"

    plate_number = models.CharField(max_length=30)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.OTHER,
        db_index=True,
    )
    registration_country = models.CharField(max_length=60, blank=True, default="")
    color = models.CharField(max_length=50, blank=True, default="")
    make  = models.CharField(max_length=100, blank=True, default="")
    model = models.CharField(max_length=100, blank=True, default="")
    year  = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1886),
            MaxValueValidator(2100),
        ],
    )
    is_active  = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Optional link to an identified driver when available
    driver = models.ForeignKey(
        "drivers.Driver",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicles",
    )

    class Meta:
        app_label  = "violations"
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"
        ordering   = ["-created_at"]
        indexes    = [
            models.Index(fields=["vehicle_type", "is_active"],
                         name="vio_veh_type_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.plate_number} ({self.vehicle_type})"


# ---------------------------------------------------------------------------
# TrafficViolation (Phase 4D.2)
# ---------------------------------------------------------------------------

class TrafficViolation(models.Model):
    """
    A recorded traffic violation.

    Append-only — records are legal evidence.  No UPDATE or DELETE API
    or service method is provided.  ``is_active`` allows administrative
    flagging without destroying the record (e.g. duplicate detected).

    Fields
    ------
    violation_type : str   — classification of the violation
    description    : str   — optional officer notes
    occurred_at    : datetime — when the violation occurred (required)
    vehicle        : FK Vehicle (PROTECT)
    segment        : FK roads.RoadSegment (SET_NULL, nullable)
    intersection   : FK roads.Intersection (SET_NULL, nullable)
    camera         : FK cameras.Camera (SET_NULL, nullable — the capturing device)
    reported_by    : FK accounts.User (SET_NULL, nullable — the entering officer)
    is_active      : bool  — administrative flag (True = legally active record)
    created_at     : datetime
    """

    class ViolationType(models.TextChoices):
        SPEEDING         = "speeding",         "Speeding"
        RED_LIGHT        = "red_light",        "Red Light"
        ILLEGAL_PARKING  = "illegal_parking",  "Illegal Parking"
        WRONG_WAY        = "wrong_way",        "Wrong Way"
        ILLEGAL_TURN     = "illegal_turn",     "Illegal Turn"
        OTHER            = "other",            "Other"

    violation_type = models.CharField(
        max_length=20,
        choices=ViolationType.choices,
        default=ViolationType.OTHER,
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    occurred_at = models.DateTimeField(db_index=True)
    vehicle = models.ForeignKey(
        "violations.Vehicle",
        on_delete=models.PROTECT,
        related_name="violations",
    )
    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="violations",
    )
    intersection = models.ForeignKey(
        "roads.Intersection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="violations",
    )
    camera = models.ForeignKey(
        "cameras.Camera",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="violations",
    )
    reported_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reported_violations",
    )

    # ── Phase 5 AI metadata fields ────────────────────────────────────────
    # source: how the violation was created
    class ViolationSource(models.TextChoices):
        AI_GENERATED = "ai",     "AI Generated"
        MANUAL       = "manual", "Manually Entered"

    source = models.CharField(
        max_length=10,
        choices=ViolationSource.choices,
        default=ViolationSource.MANUAL,
        db_index=True,
    )
    # AI confidence score (0.0–1.0); null for manual entries
    confidence = models.FloatField(null=True, blank=True)

    # review_status: derived from confidence on creation; can be overridden by officers
    class ReviewStatus(models.TextChoices):
        AUTO_ACCEPTED    = "auto_accepted",  "Auto Accepted"   # confidence >= 0.95
        PENDING_REVIEW   = "pending",        "Pending Review"  # 0.70–0.94
        LOW_CONFIDENCE   = "low_confidence", "Low Confidence"  # < 0.70
        VERIFIED         = "verified",       "Verified"        # human-confirmed
        REJECTED         = "rejected",       "Rejected"        # human-rejected

    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.VERIFIED,  # manual entries default to verified
        db_index=True,
    )
    model_name    = models.CharField(max_length=100, blank=True, default="")
    model_version = models.CharField(max_length=50,  blank=True, default="")

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label  = "violations"
        verbose_name = "Traffic Violation"
        verbose_name_plural = "Traffic Violations"
        ordering   = ["-occurred_at"]
        verbose_name = "Traffic Violation"
        verbose_name_plural = "Traffic Violations"
        ordering   = ["-occurred_at"]
        indexes    = [
            models.Index(
                fields=["violation_type", "is_active"],
                name="vio_tv_type_active_idx",
            ),
            models.Index(
                fields=["vehicle", "occurred_at"],
                name="vio_tv_vehicle_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        """Enforce append-only: block updates to existing records."""
        if self._state.adding is False:
            raise RuntimeError(
                "TrafficViolation records are append-only and may not be modified. "
                "Use is_active=False to administratively deactivate a record."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enforce append-only: block deletion of violation records."""
        raise RuntimeError(
            "TrafficViolation records are append-only and may not be deleted."
        )

    def __str__(self) -> str:
        return f"[{self.violation_type}] {self.vehicle} @ {self.occurred_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# ViolationEvidence (Phase 4D.2)
# ---------------------------------------------------------------------------

class ViolationEvidence(models.Model):
    """
    An external evidence reference attached to a TrafficViolation.

    Append-only — evidence records are part of the legal chain.

    Architecture note (ai-integration.md):
    "Raw camera frames: apps.cameras, read-only via object storage"
    Django stores only the URL reference; binary data lives in object storage.

    Fields
    ------
    violation     : FK TrafficViolation (PROTECT, required)
    evidence_type : str — image | video | sensor_reading
    evidence_url  : URLField — external reference (S3, CDN, or object store URL)
    description   : str — optional notes about this evidence item
    created_at    : datetime
    """

    class EvidenceType(models.TextChoices):
        IMAGE          = "image",          "Image"
        VIDEO          = "video",          "Video"
        SENSOR_READING = "sensor_reading", "Sensor Reading"

    violation = models.ForeignKey(
        "violations.TrafficViolation",
        on_delete=models.PROTECT,
        related_name="evidence",
    )
    evidence_type = models.CharField(
        max_length=20,
        choices=EvidenceType.choices,
        default=EvidenceType.IMAGE,
        db_index=True,
    )
    evidence_url = models.URLField(
        max_length=2048,
        help_text="External object-storage URL (S3, CDN, etc.). No binary data stored here.",
    )
    description = models.CharField(max_length=500, blank=True, default="")
    # AI confidence for this specific evidence frame (null for non-AI evidence)
    confidence  = models.FloatField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label  = "violations"
        verbose_name = "Violation Evidence"
        verbose_name_plural = "Violation Evidence"
        ordering   = ["created_at"]
        indexes    = [
            models.Index(
                fields=["violation", "evidence_type"],
                name="vio_evid_viol_type_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        """Enforce append-only: block updates to existing records."""
        if self._state.adding is False:
            raise RuntimeError(
                "ViolationEvidence records are append-only and may not be modified."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enforce append-only: block deletion of evidence records."""
        raise RuntimeError(
            "ViolationEvidence records are append-only and may not be deleted."
        )

    def __str__(self) -> str:
        return f"Evidence [{self.evidence_type}] for violation #{self.violation_id}"


# ---------------------------------------------------------------------------
# Citation (Phase 4D.2)
# ---------------------------------------------------------------------------

class Citation(models.Model):
    """
    A formal citation issued for a TrafficViolation.

    Lifecycle (from domain-model.md):
      issued → contested → adjudicated   (contested is optional)
      issued → adjudicated               (assumption: direct path is valid)

    adjudicated is terminal — no further transitions.

    Fields
    ------
    violation  : OneToOneField TrafficViolation (PROTECT)
    issued_by  : FK accounts.User (SET_NULL, nullable)
    issued_at  : datetime — when the citation was formally issued
    state      : str — lifecycle state
    notes      : TextField — optional officer notes (updated at each transition)
    created_at : datetime
    updated_at : datetime
    """

    class State(models.TextChoices):
        ISSUED      = "issued",      "Issued"
        CONTESTED   = "contested",   "Contested"
        ADJUDICATED = "adjudicated", "Adjudicated"

    # Forward-only transitions from the architecture plus the documented shortcut.
    # adjudicated is terminal (empty list).
    VALID_TRANSITIONS: dict[str, list[str]] = {
        State.ISSUED:      [State.CONTESTED, State.ADJUDICATED],
        State.CONTESTED:   [State.ADJUDICATED],
        State.ADJUDICATED: [],  # terminal
    }

    violation = models.OneToOneField(
        "violations.TrafficViolation",
        on_delete=models.PROTECT,
        related_name="citation",
    )
    issued_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_citations",
    )
    issued_at = models.DateTimeField()
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ISSUED,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = "violations"
        verbose_name = "Citation"
        verbose_name_plural = "Citations"
        ordering   = ["-issued_at"]
        indexes    = [
            models.Index(fields=["state"], name="vio_cit_state_idx"),
        ]

    def __str__(self) -> str:
        return f"Citation #{self.pk} [{self.state}] for violation #{self.violation_id}"
