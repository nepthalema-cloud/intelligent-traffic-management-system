"""
Service layer for the cameras app.

Audit events are emitted for all mutating Camera and Sensor operations.
CameraHealth and SensorHealth updates are NOT audited (classified as
operational noise per the architecture document).

Dependency direction: cameras.services → audit.services (correct)
"""

from django.utils import timezone

from apps.audit.services import AuditAction, Outcome, log_audit_event
from apps.cameras.models import Camera, CameraHealth, Sensor, SensorHealth


class CameraServiceError(Exception):
    """Base exception for camera service errors."""


class DuplicateCameraNameError(CameraServiceError):
    pass


class DuplicateSensorNameError(CameraServiceError):
    pass


class CameraService:
    """All create/update/deactivate operations for Camera devices."""

    @staticmethod
    def create_camera(actor, name: str, camera_type: str = "fixed",
                      request=None, **fields) -> Camera:
        if Camera.objects.filter(name=name).exists():
            raise DuplicateCameraNameError(f"A camera named '{name}' already exists.")
        camera = Camera.objects.create(name=name, camera_type=camera_type, **fields)
        log_audit_event(
            action=AuditAction.CAMERA_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=camera,
            detail={"name": name, "camera_type": camera_type},
        )
        return camera

    @staticmethod
    def update_camera(actor, camera: Camera, request=None, **fields) -> Camera:
        old_name = camera.name
        for attr, value in fields.items():
            setattr(camera, attr, value)
        camera.save()
        log_audit_event(
            action=AuditAction.CAMERA_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=camera,
            detail={"fields_changed": list(fields.keys()), "old_name": old_name},
        )
        return camera

    @staticmethod
    def set_camera_active(actor, camera: Camera, is_active: bool,
                          request=None) -> Camera:
        camera.is_active = is_active
        camera.save(update_fields=["is_active", "updated_at"])
        action = (AuditAction.CAMERA_ACTIVATED if is_active
                  else AuditAction.CAMERA_DEACTIVATED)
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=camera,
            detail={"is_active": is_active},
        )
        return camera

    @staticmethod
    def upsert_health(camera: Camera, health_status: str,
                      connectivity_status: str, last_seen=None,
                      detail: str = "") -> CameraHealth:
        """
        Create or update the single CameraHealth record for this camera.
        Replace-latest semantics: no historical health records are kept.
        Not audited — health updates are high-frequency operational noise.
        """
        health, _ = CameraHealth.objects.get_or_create(camera=camera)
        health.health_status = health_status
        health.connectivity_status = connectivity_status
        health.last_seen = last_seen
        health.checked_at = timezone.now()
        health.detail = detail
        health.save()
        return health


class SensorService:
    """All create/update/deactivate operations for Sensor devices."""

    @staticmethod
    def create_sensor(actor, name: str, sensor_type: str = "other",
                      request=None, **fields) -> Sensor:
        if Sensor.objects.filter(name=name).exists():
            raise DuplicateSensorNameError(f"A sensor named '{name}' already exists.")
        sensor = Sensor.objects.create(name=name, sensor_type=sensor_type, **fields)
        log_audit_event(
            action=AuditAction.SENSOR_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=sensor,
            detail={"name": name, "sensor_type": sensor_type},
        )
        return sensor

    @staticmethod
    def update_sensor(actor, sensor: Sensor, request=None, **fields) -> Sensor:
        old_name = sensor.name
        for attr, value in fields.items():
            setattr(sensor, attr, value)
        sensor.save()
        log_audit_event(
            action=AuditAction.SENSOR_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=sensor,
            detail={"fields_changed": list(fields.keys()), "old_name": old_name},
        )
        return sensor

    @staticmethod
    def set_sensor_active(actor, sensor: Sensor, is_active: bool,
                          request=None) -> Sensor:
        sensor.is_active = is_active
        sensor.save(update_fields=["is_active", "updated_at"])
        action = (AuditAction.SENSOR_ACTIVATED if is_active
                  else AuditAction.SENSOR_DEACTIVATED)
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=sensor,
            detail={"is_active": is_active},
        )
        return sensor

    @staticmethod
    def upsert_health(sensor: Sensor, health_status: str,
                      connectivity_status: str, last_seen=None,
                      detail: str = "") -> SensorHealth:
        """
        Create or update the single SensorHealth record for this sensor.
        Replace-latest semantics. Not audited.
        """
        health, _ = SensorHealth.objects.get_or_create(sensor=sensor)
        health.health_status = health_status
        health.connectivity_status = connectivity_status
        health.last_seen = last_seen
        health.checked_at = timezone.now()
        health.detail = detail
        health.save()
        return health
