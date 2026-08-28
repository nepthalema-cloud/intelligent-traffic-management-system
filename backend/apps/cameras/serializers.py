"""Serializers for the cameras app."""

from rest_framework import serializers

from apps.cameras.models import Camera, CameraHealth, Sensor, SensorHealth


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

class CameraSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source="segment.road.name", read_only=True, default=None)
    intersection_name = serializers.CharField(source="intersection.name", read_only=True, default=None)

    class Meta:
        model = Camera
        fields = [
            "id", "name", "camera_type", "model", "description",
            "ip_address", "stream_url",
            "segment", "segment_name",
            "intersection", "intersection_name",
            "installed_at", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class CameraWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = [
            "name", "camera_type", "model", "description",
            "ip_address", "stream_url",
            "segment", "intersection", "installed_at",
        ]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Camera name may not be blank.")
        return value

    def validate(self, data):
        segment = data.get("segment") or getattr(self.instance, "segment", None)
        intersection = data.get("intersection") or getattr(self.instance, "intersection", None)
        if segment and intersection:
            raise serializers.ValidationError(
                "A camera may be associated with either a segment or an intersection, not both."
            )
        return data


# ---------------------------------------------------------------------------
# CameraHealth
# ---------------------------------------------------------------------------

class CameraHealthSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = CameraHealth
        fields = [
            "camera", "camera_name",
            "health_status", "connectivity_status",
            "last_seen", "checked_at", "detail",
        ]
        read_only_fields = ["camera", "camera_name", "checked_at"]


class CameraHealthWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CameraHealth
        fields = ["health_status", "connectivity_status", "last_seen", "detail"]


# ---------------------------------------------------------------------------
# Sensor
# ---------------------------------------------------------------------------

class SensorSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source="segment.road.name", read_only=True, default=None)
    intersection_name = serializers.CharField(source="intersection.name", read_only=True, default=None)

    class Meta:
        model = Sensor
        fields = [
            "id", "name", "sensor_type", "model", "description",
            "segment", "segment_name",
            "intersection", "intersection_name",
            "installed_at", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class SensorWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = [
            "name", "sensor_type", "model", "description",
            "segment", "intersection", "installed_at",
        ]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Sensor name may not be blank.")
        return value

    def validate(self, data):
        segment = data.get("segment") or getattr(self.instance, "segment", None)
        intersection = data.get("intersection") or getattr(self.instance, "intersection", None)
        if segment and intersection:
            raise serializers.ValidationError(
                "A sensor may be associated with either a segment or an intersection, not both."
            )
        return data


# ---------------------------------------------------------------------------
# SensorHealth
# ---------------------------------------------------------------------------

class SensorHealthSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source="sensor.name", read_only=True)

    class Meta:
        model = SensorHealth
        fields = [
            "sensor", "sensor_name",
            "health_status", "connectivity_status",
            "last_seen", "checked_at", "detail",
        ]
        read_only_fields = ["sensor", "sensor_name", "checked_at"]


class SensorHealthWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorHealth
        fields = ["health_status", "connectivity_status", "last_seen", "detail"]
