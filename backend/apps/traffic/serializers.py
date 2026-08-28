"""Serializers for the traffic app — Phase 4C.1."""

from rest_framework import serializers

from apps.traffic.models import SignalPhase, TrafficEvent, TrafficIncident, TrafficMeasurement, TrafficSignal


# ---------------------------------------------------------------------------
# TrafficSignal
# ---------------------------------------------------------------------------

class TrafficSignalSerializer(serializers.ModelSerializer):
    """Read serializer for TrafficSignal responses."""

    intersection_name = serializers.CharField(
        source="intersection.name", read_only=True
    )

    class Meta:
        model = TrafficSignal
        fields = [
            "id",
            "name",
            "intersection",
            "intersection_name",
            "controller_type",
            "controller_identifier",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TrafficSignalWriteSerializer(serializers.ModelSerializer):
    """Write serializer for TrafficSignal create/update requests."""

    class Meta:
        model = TrafficSignal
        fields = [
            "name",
            "intersection",
            "controller_type",
            "controller_identifier",
        ]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Signal name may not be blank.")
        return value


# ---------------------------------------------------------------------------
# SignalPhase
# ---------------------------------------------------------------------------

class SignalPhaseSerializer(serializers.ModelSerializer):
    """Read serializer for SignalPhase responses."""

    signal_name = serializers.CharField(source="signal.name", read_only=True)

    class Meta:
        model = SignalPhase
        fields = [
            "id",
            "signal",
            "signal_name",
            "phase_number",
            "name",
            "movement",
            "minimum_green_seconds",
            "maximum_green_seconds",
            "yellow_seconds",
            "all_red_seconds",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SignalPhaseWriteSerializer(serializers.ModelSerializer):
    """Write serializer for SignalPhase create/update requests."""

    class Meta:
        model = SignalPhase
        fields = [
            "phase_number",
            "name",
            "movement",
            "minimum_green_seconds",
            "maximum_green_seconds",
            "yellow_seconds",
            "all_red_seconds",
        ]

    def validate_phase_number(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Phase number must be at least 1.")
        return value

    def validate(self, data):
        min_g = data.get(
            "minimum_green_seconds",
            getattr(self.instance, "minimum_green_seconds", None),
        )
        max_g = data.get(
            "maximum_green_seconds",
            getattr(self.instance, "maximum_green_seconds", None),
        )
        if min_g is not None and max_g is not None and min_g > max_g:
            raise serializers.ValidationError(
                "minimum_green_seconds must not exceed maximum_green_seconds."
            )
        return data


# ---------------------------------------------------------------------------
# TrafficMeasurement
# ---------------------------------------------------------------------------

class TrafficMeasurementSerializer(serializers.ModelSerializer):
    """Read serializer for TrafficMeasurement responses."""

    segment_name = serializers.SerializerMethodField()
    camera_name  = serializers.SerializerMethodField()
    sensor_name  = serializers.SerializerMethodField()

    class Meta:
        model = TrafficMeasurement
        fields = [
            "id",
            "segment",
            "segment_name",
            "camera",
            "camera_name",
            "sensor",
            "sensor_name",
            "measured_at",
            "vehicle_count",
            "avg_speed_kmh",
            "occupancy_pct",
            "data_source",
            "created_at",
        ]
        read_only_fields = fields

    def get_segment_name(self, obj) -> str | None:
        if obj.segment_id:
            return getattr(obj.segment, "road", None) and str(obj.segment)
        return None

    def get_camera_name(self, obj) -> str | None:
        return obj.camera.name if obj.camera_id and obj.camera else None

    def get_sensor_name(self, obj) -> str | None:
        return obj.sensor.name if obj.sensor_id and obj.sensor else None


class TrafficMeasurementWriteSerializer(serializers.ModelSerializer):
    """Write serializer for TrafficMeasurement ingestion."""

    class Meta:
        model = TrafficMeasurement
        fields = [
            "segment",
            "camera",
            "sensor",
            "measured_at",
            "vehicle_count",
            "avg_speed_kmh",
            "occupancy_pct",
            "data_source",   # Phase 5: ai | sensor | manual | demo
        ]

    def validate_occupancy_pct(self, value):
        if value is not None and not (0.0 <= value <= 100.0):
            raise serializers.ValidationError(
                "occupancy_pct must be between 0 and 100."
            )
        return value

    def validate_avg_speed_kmh(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "avg_speed_kmh must be non-negative."
            )
        return value

    def validate(self, data):
        camera = data.get("camera")
        sensor = data.get("sensor")
        if camera is not None and sensor is not None:
            raise serializers.ValidationError(
                "Provide either 'camera' or 'sensor', not both."
            )
        if camera is None and sensor is None:
            raise serializers.ValidationError(
                "Either 'camera' or 'sensor' must be provided."
            )
        if not data.get("measured_at"):
            raise serializers.ValidationError(
                "'measured_at' is required."
            )
        # All three metric fields cannot be null simultaneously
        if (data.get("vehicle_count") is None
                and data.get("avg_speed_kmh") is None
                and data.get("occupancy_pct") is None):
            raise serializers.ValidationError(
                "At least one metric (vehicle_count, avg_speed_kmh, "
                "occupancy_pct) must be provided."
            )
        return data


# ---------------------------------------------------------------------------
# TrafficEvent
# ---------------------------------------------------------------------------

class TrafficEventSerializer(serializers.ModelSerializer):
    """Read serializer for TrafficEvent responses."""

    segment_road_name  = serializers.SerializerMethodField()
    intersection_name  = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()

    class Meta:
        model = TrafficEvent
        fields = [
            "id",
            "event_type",
            "description",
            "occurred_at",
            "segment",
            "segment_road_name",
            "intersection",
            "intersection_name",
            "created_by",
            "created_by_username",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_segment_road_name(self, obj) -> str | None:
        if obj.segment_id and obj.segment:
            return getattr(getattr(obj.segment, "road", None), "name", None)
        return None

    def get_intersection_name(self, obj) -> str | None:
        if obj.intersection_id and obj.intersection:
            return obj.intersection.name
        return None

    def get_created_by_username(self, obj) -> str | None:
        if obj.created_by_id and obj.created_by:
            return obj.created_by.username
        return None


class TrafficEventWriteSerializer(serializers.ModelSerializer):
    """Write serializer for TrafficEvent create/update requests."""

    class Meta:
        model = TrafficEvent
        fields = [
            "event_type",
            "description",
            "occurred_at",
            "segment",
            "intersection",
        ]

    def validate_description(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Description may not be blank.")
        return value.strip()


# ---------------------------------------------------------------------------
# TrafficIncident
# ---------------------------------------------------------------------------

class TrafficIncidentSerializer(serializers.ModelSerializer):
    """Read serializer for TrafficIncident responses."""

    segment_ids          = serializers.SerializerMethodField()
    intersection_name    = serializers.SerializerMethodField()
    created_by_username  = serializers.SerializerMethodField()

    class Meta:
        model = TrafficIncident
        fields = [
            "id",
            "title",
            "description",
            "incident_type",
            "state",
            "occurred_at",
            "segment_ids",
            "intersection",
            "intersection_name",
            "created_by",
            "created_by_username",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_segment_ids(self, obj) -> list[int]:
        return list(obj.segments.values_list("pk", flat=True))

    def get_intersection_name(self, obj) -> str | None:
        return obj.intersection.name if obj.intersection_id and obj.intersection else None

    def get_created_by_username(self, obj) -> str | None:
        return obj.created_by.username if obj.created_by_id and obj.created_by else None


class TrafficIncidentWriteSerializer(serializers.ModelSerializer):
    """Write serializer for TrafficIncident create/update requests."""

    segment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )

    class Meta:
        model = TrafficIncident
        fields = [
            "title",
            "description",
            "incident_type",
            "occurred_at",
            "segment_ids",
            "intersection",
        ]

    def validate_title(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Title may not be blank.")
        return value.strip()

    def validate_description(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Description may not be blank.")
        return value.strip()

    def validate_segment_ids(self, value: list[int]) -> list[int]:
        from apps.roads.models import RoadSegment
        if value:
            existing = set(
                RoadSegment.objects.filter(pk__in=value).values_list("pk", flat=True)
            )
            missing = set(value) - existing
            if missing:
                raise serializers.ValidationError(
                    f"RoadSegment IDs not found: {sorted(missing)}"
                )
        return value


class TrafficIncidentStateSerializer(serializers.Serializer):
    """Validates a lifecycle state-transition request."""

    state = serializers.ChoiceField(choices=TrafficIncident.State.choices)
