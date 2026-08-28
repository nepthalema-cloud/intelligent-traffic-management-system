"""
Cameras and Sensors domain models.

Entities
--------
Camera       — a physical traffic camera device (reference metadata)
CameraHealth — latest health/connectivity snapshot for a Camera (replace-latest)
Sensor       — a non-camera traffic sensing device (reference metadata)
SensorHealth — latest health/connectivity snapshot for a Sensor (replace-latest)

Lifecycle
---------
Camera and Sensor support soft-deactivation via ``is_active`` (same pattern as
roads domain).  Administrative lifecycle (is_active) is kept separate from
operational health (health_status / connectivity_status).

Health models
-------------
CameraHealth and SensorHealth represent the *current* device state only.
They use a OneToOneField to the parent device, enforcing at most one health
record per device.  When health state changes, the existing record is updated
in-place (replace-latest pattern).  This is explicitly not a time-series
history table.

Audit
-----
Camera and Sensor mutating operations generate audit events via
``apps.audit.services``.  Health updates are NOT audited — the architecture
document classifies health data as "operational noise" not worth auditing.

Relationships
-------------
Camera   ──* RoadSegment  (nullable SET_NULL)
Camera   ──* Intersection  (nullable SET_NULL)
Sensor   ──* RoadSegment  (nullable SET_NULL)
Sensor   ──* Intersection  (nullable SET_NULL)
Camera   1──1 CameraHealth  (OneToOneField, optional — health may not yet exist)
Sensor   1──1 SensorHealth  (OneToOneField, optional)

on_delete strategy for infrastructure FKs
------------------------------------------
SET_NULL is used so that decommissioning a road segment does not cascade-delete
camera or sensor records.  Historical camera/sensor records should survive
infrastructure changes.
"""

from django.db import models
from django.utils import timezone


class HealthStatus(models.TextChoices):
    HEALTHY   = "healthy",   "Healthy"
    DEGRADED  = "degraded",  "Degraded"
    OFFLINE   = "offline",   "Offline"
    UNKNOWN   = "unknown",   "Unknown"


class ConnectivityStatus(models.TextChoices):
    CONNECTED    = "connected",    "Connected"
    DISCONNECTED = "disconnected", "Disconnected"
    UNKNOWN      = "unknown",      "Unknown"


class Camera(models.Model):
    """
    A physical traffic camera device.

    Fields
    ------
    name            : str  — human-readable device name (e.g. "CAM-001")
    camera_type     : str  — classification (fixed, ptz, thermal, etc.)
    model           : str  — hardware model/manufacturer (optional)
    description     : str  — operational notes (optional)
    ip_address      : str  — device IP address (optional)
    stream_url      : str  — RTSP/HTTP stream URL (optional)
    segment         : FK RoadSegment (nullable) — associated road segment
    intersection    : FK Intersection (nullable) — associated intersection
    installed_at    : datetime — when the camera was physically installed (optional)
    is_active       : bool  — administrative soft-deactivation flag
    created_at      : datetime
    updated_at      : datetime

    Note: A camera may be associated with either a segment OR an intersection
    (or neither, if location is not yet assigned).  Both FKs are nullable.
    """

    class CameraType(models.TextChoices):
        FIXED   = "fixed",   "Fixed Camera"
        PTZ     = "ptz",     "PTZ (Pan-Tilt-Zoom)"
        THERMAL = "thermal", "Thermal Camera"
        OTHER   = "other",   "Other"

    name = models.CharField(max_length=255, unique=True)
    camera_type = models.CharField(
        max_length=20,
        choices=CameraType.choices,
        default=CameraType.FIXED,
        db_index=True,
    )
    model = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # stream_url accepts RTSP, RTSPS, HTTP, HTTPS schemes.
    # URLField rejected rtsp:// — replaced with CharField + validator.
    stream_url = models.CharField(max_length=1024, blank=True, default="")
    # hls_path: the safe path served by MediaMTX for browser playback
    # e.g. "/camera-001/index.m3u8" (no credentials)
    hls_path = models.CharField(max_length=512, blank=True, default="")
    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cameras",
    )
    intersection = models.ForeignKey(
        "roads.Intersection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cameras",
    )
    installed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cameras"
        verbose_name = "Camera"
        verbose_name_plural = "Cameras"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["segment", "is_active"], name="cams_cam_seg_active_idx"),
            models.Index(fields=["intersection", "is_active"], name="cams_cam_int_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.camera_type})"


class CameraHealth(models.Model):
    """
    Latest health/connectivity snapshot for a Camera.

    Replace-latest semantics: there is exactly one record per camera.
    When health state changes the record is updated in-place.

    Fields
    ------
    camera              : OneToOneField Camera — the device this record belongs to
    health_status       : enum — healthy / degraded / offline / unknown
    connectivity_status : enum — connected / disconnected / unknown
    last_seen           : datetime — last heartbeat/check-in from the device
    checked_at          : datetime — when this health record was last updated
    detail              : str — optional human-readable status message
    """

    camera = models.OneToOneField(
        Camera,
        on_delete=models.CASCADE,
        related_name="health",
        primary_key=True,
    )
    health_status = models.CharField(
        max_length=16,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
        db_index=True,
    )
    connectivity_status = models.CharField(
        max_length=16,
        choices=ConnectivityStatus.choices,
        default=ConnectivityStatus.UNKNOWN,
        db_index=True,
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)
    detail = models.TextField(blank=True, default="")

    class Meta:
        app_label = "cameras"
        verbose_name = "Camera Health"
        verbose_name_plural = "Camera Health Records"

    def __str__(self) -> str:
        return f"Health({self.camera.name}): {self.health_status}/{self.connectivity_status}"


class Sensor(models.Model):
    """
    A non-camera traffic sensing device (inductive loop, radar, LiDAR, etc.).

    Fields
    ------
    name            : str  — human-readable device name (e.g. "SENSOR-001")
    sensor_type     : str  — classification
    model           : str  — hardware model (optional)
    description     : str  — operational notes (optional)
    segment         : FK RoadSegment (nullable)
    intersection    : FK Intersection (nullable)
    installed_at    : datetime (optional)
    is_active       : bool — administrative soft-deactivation flag
    created_at      : datetime
    updated_at      : datetime
    """

    class SensorType(models.TextChoices):
        INDUCTIVE_LOOP = "inductive_loop", "Inductive Loop"
        RADAR          = "radar",          "Radar"
        LIDAR          = "lidar",          "LiDAR"
        INFRARED       = "infrared",       "Infrared"
        ACOUSTIC       = "acoustic",       "Acoustic"
        OTHER          = "other",          "Other"

    name = models.CharField(max_length=255, unique=True)
    sensor_type = models.CharField(
        max_length=20,
        choices=SensorType.choices,
        default=SensorType.OTHER,
        db_index=True,
    )
    model = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    segment = models.ForeignKey(
        "roads.RoadSegment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sensors",
    )
    intersection = models.ForeignKey(
        "roads.Intersection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sensors",
    )
    installed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cameras"
        verbose_name = "Sensor"
        verbose_name_plural = "Sensors"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["segment", "is_active"], name="cams_sen_seg_active_idx"),
            models.Index(fields=["intersection", "is_active"], name="cams_sen_int_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sensor_type})"


class SensorHealth(models.Model):
    """
    Latest health/connectivity snapshot for a Sensor.

    Replace-latest semantics — exactly one record per sensor.
    """

    sensor = models.OneToOneField(
        Sensor,
        on_delete=models.CASCADE,
        related_name="health",
        primary_key=True,
    )
    health_status = models.CharField(
        max_length=16,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
        db_index=True,
    )
    connectivity_status = models.CharField(
        max_length=16,
        choices=ConnectivityStatus.choices,
        default=ConnectivityStatus.UNKNOWN,
        db_index=True,
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)
    detail = models.TextField(blank=True, default="")

    class Meta:
        app_label = "cameras"
        verbose_name = "Sensor Health"
        verbose_name_plural = "Sensor Health Records"

    def __str__(self) -> str:
        return f"Health({self.sensor.name}): {self.health_status}/{self.connectivity_status}"


# ---------------------------------------------------------------------------
# CameraCredential  (Phase 5 — secure RTSP credential storage)
# ---------------------------------------------------------------------------

class CameraCredential(models.Model):
    """
    Stores RTSP/camera authentication credentials separately from the Camera model.

    Security rules:
    - NEVER returned in any public serializer
    - NEVER written to audit detail fields
    - Read/write restricted to System Admin and Camera Technician
    - Used only by the media gateway (MediaMTX) and the AI service — both
      access credentials via backend configuration, not via API responses
    - password stored as plain text in dev; use field encryption in production

    The full authenticated RTSP URL is:
        rtsp://{username}:{password}@{camera.ip_address}/{stream_path}
    This URL is assembled server-side and passed only to MediaMTX config.
    """

    camera   = models.OneToOneField(
        Camera,
        on_delete=models.CASCADE,
        related_name="credential",
    )
    username = models.CharField(max_length=150, blank=True, default="")
    # In production: encrypt this field (e.g. django-encrypted-fields)
    # In Phase 5 dev: stored as-is, access restricted by RBAC
    password = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = "cameras"
        verbose_name = "Camera Credential"
        verbose_name_plural = "Camera Credentials"

    def __str__(self) -> str:
        return f"Credential({self.camera.name})"

    def build_rtsp_url(self) -> str:
        """
        Return the full authenticated RTSP URL for use by MediaMTX/AI service.
        NEVER expose this in API responses.
        """
        base = self.camera.stream_url
        if not base:
            return ""
        if self.username and self.password:
            # Insert credentials: rtsp://user:pass@host/path
            proto, rest = base.split("://", 1)
            return f"{proto}://{self.username}:{self.password}@{rest}"
        return base


# ---------------------------------------------------------------------------
# CameraCalibration  (Phase 5 — speed estimation)
# ---------------------------------------------------------------------------

class CameraCalibration(models.Model):
    """
    Per-camera calibration data for speed estimation.

    Speed estimation formula:
        speed_ms = (pixel_distance * meters_per_pixel) / frame_interval_seconds
        speed_kmh = speed_ms * 3.6

    meters_per_pixel must be measured from the real-world scene:
        meters_per_pixel = known_real_world_distance_m / pixel_distance_for_same_distance

    This value is specific to each camera's field of view and installation angle.
    Without valid calibration, avg_speed_kmh is stored as NULL (never fabricated).

    Fields
    ------
    camera              : OneToOneField Camera
    meters_per_pixel    : float — real-world metres per pixel (must be > 0)
    calibrated_at       : datetime — when calibration was last performed
    calibrated_by       : FK User (nullable)
    notes               : str — optional calibration notes
    is_valid            : bool — set to False to disable speed estimation without deleting
    created_at          : datetime
    updated_at          : datetime
    """

    camera = models.OneToOneField(
        Camera,
        on_delete=models.CASCADE,
        related_name="calibration",
    )
    meters_per_pixel = models.FloatField(
        help_text=(
            "Real-world metres per pixel in the camera's field of view. "
            "Must be measured from a known reference object in the scene."
        )
    )
    calibrated_at = models.DateTimeField(default=timezone.now)
    calibrated_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="camera_calibrations",
    )
    notes    = models.TextField(blank=True, default="")
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = "cameras"
        verbose_name = "Camera Calibration"
        verbose_name_plural = "Camera Calibrations"

    def __str__(self) -> str:
        return (
            f"Calibration({self.camera.name}): "
            f"{self.meters_per_pixel:.6f} m/px "
            f"{'[valid]' if self.is_valid else '[INVALID]'}"
        )


# ---------------------------------------------------------------------------
# BrowserWebcamSession  (Phase 5C — browser webcam testing)
# ---------------------------------------------------------------------------

class BrowserWebcamSession(models.Model):
    """
    Tracks an active browser-webcam detection session.

    When a user opens the Cameras page and clicks "Start My Webcam", the
    frontend opens a WebSocket connection to ws/webcam-detection/.
    The consumer creates a BrowserWebcamSession on connect and marks it
    ended on disconnect.

    Each session:
    - Is tied to one authenticated user
    - Is not tied to a persistent camera record
    - Is clearly labelled source_type='browser_webcam'
    - Measurements produced during the session may be camera-less and
      are still marked as data_source='ai'

    Security:
    - Created server-side only; the browser never supplies its own session ID
    - session_token is a server-generated UUID used as the WS path identifier
    - No RTSP credentials are involved — the browser uses getUserMedia()

    Fields
    ------
    user            : FK User — the authenticated user running the session
    camera          : FK Camera — optional reference to a registered camera.
                        Browser webcam sessions do not require a persistent camera record.
    session_token   : UUID — server-generated, used to identify the WS channel
    device_label    : str — browser-reported MediaDeviceInfo.label (optional, user-visible only)
    source_type     : str — always 'browser_webcam'
    started_at      : datetime
    ended_at        : datetime (nullable — null while active)
    vehicle_count_total : int — running total of vehicles detected this session
    is_active       : bool — True while WS is open
    """

    SOURCE_BROWSER_WEBCAM = "browser_webcam"

    import uuid as _uuid

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="webcam_sessions",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webcam_sessions",
        help_text="Optional reference to a registered camera when available; browser webcam sessions do not require a camera record.",
    )
    session_token = models.UUIDField(
        default=_uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    device_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Browser MediaDeviceInfo.label — for display only, never used server-side for auth.",
    )
    source_type = models.CharField(
        max_length=32,
        default=SOURCE_BROWSER_WEBCAM,
        editable=False,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at   = models.DateTimeField(null=True, blank=True)
    vehicle_count_total = models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "cameras"
        verbose_name = "Browser Webcam Session"
        verbose_name_plural = "Browser Webcam Sessions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "is_active"], name="cams_bws_user_active_idx"),
        ]

    def __str__(self) -> str:
        return (
            f"WebcamSession({self.user.username}, "
            f"{'active' if self.is_active else 'ended'}, "
            f"token={str(self.session_token)[:8]}…)"
        )


# ---------------------------------------------------------------------------
# TemporaryVideoAnalysis — for user-uploaded video processing (ephemeral)
# ---------------------------------------------------------------------------

class TemporaryVideoAnalysis(models.Model):
    """
    Tracks a user-uploaded video that will be processed temporarily for AI analysis.

    Files and results are considered ephemeral and may be cleaned by periodic jobs.
    """

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='video_analyses')
    original_filename = models.CharField(max_length=255)
    upload = models.FileField(upload_to='uploads/tmp_videos/%Y/%m/%d')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_json = models.JSONField(null=True, blank=True)
    annotated_video = models.FileField(upload_to='uploads/annotated_videos/%Y/%m/%d', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'cameras'
        verbose_name = 'Temporary Video Analysis'
        verbose_name_plural = 'Temporary Video Analyses'

    def __str__(self) -> str:
        return f"TempAnalysis({self.user.username}, file={self.original_filename}, status={self.status})"
