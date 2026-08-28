"""
Serializers for the roads app.

All serializers use explicit field lists.  No ModelSerializer with
``fields = '__all__'`` is used.  Write serializers validate input;
read serializers are used for responses.
"""

from rest_framework import serializers

from apps.roads.models import Intersection, Lane, Road, RoadSegment


# ---------------------------------------------------------------------------
# Road
# ---------------------------------------------------------------------------

class RoadSerializer(serializers.ModelSerializer):
    """Read serializer for Road — used in list and detail responses."""

    class Meta:
        model = Road
        fields = [
            "id", "name", "description", "road_type",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class RoadWriteSerializer(serializers.ModelSerializer):
    """Write serializer for Road — used for create and update requests."""

    class Meta:
        model = Road
        fields = ["name", "description", "road_type"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Road name may not be blank.")
        return value


# ---------------------------------------------------------------------------
# Intersection
# ---------------------------------------------------------------------------

class IntersectionSerializer(serializers.ModelSerializer):
    """Read serializer for Intersection."""

    class Meta:
        model = Intersection
        fields = [
            "id", "name", "description", "latitude", "longitude",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class IntersectionWriteSerializer(serializers.ModelSerializer):
    """Write serializer for Intersection."""

    class Meta:
        model = Intersection
        fields = ["name", "description", "latitude", "longitude"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Intersection name may not be blank.")
        return value

    def validate(self, data):
        lat = data.get("latitude")
        lon = data.get("longitude")
        if (lat is None) != (lon is None):
            raise serializers.ValidationError(
                "latitude and longitude must both be provided or both omitted."
            )
        return data


# ---------------------------------------------------------------------------
# RoadSegment
# ---------------------------------------------------------------------------

class RoadSegmentSerializer(serializers.ModelSerializer):
    """Read serializer for RoadSegment — includes related IDs."""

    road_name = serializers.CharField(source="road.name", read_only=True)
    start_intersection_name = serializers.SerializerMethodField()
    end_intersection_name   = serializers.SerializerMethodField()

    class Meta:
        model = RoadSegment
        fields = [
            "id", "road", "road_name", "name",
            "start_intersection", "start_intersection_name",
            "end_intersection",   "end_intersection_name",
            "length_meters", "speed_limit_kmh", "lane_count",
            "direction", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_start_intersection_name(self, obj) -> str | None:
        return obj.start_intersection.name if obj.start_intersection else None

    def get_end_intersection_name(self, obj) -> str | None:
        return obj.end_intersection.name if obj.end_intersection else None


class RoadSegmentWriteSerializer(serializers.ModelSerializer):
    """Write serializer for RoadSegment."""

    class Meta:
        model = RoadSegment
        fields = [
            "road", "name",
            "start_intersection", "end_intersection",
            "length_meters", "speed_limit_kmh", "lane_count",
            "direction",
        ]

    def validate_road(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot add a segment to an inactive road."
            )
        return value

    def validate_speed_limit_kmh(self, value):
        if value is not None and (value < 1 or value > 300):
            raise serializers.ValidationError(
                "Speed limit must be between 1 and 300 km/h."
            )
        return value

    def validate_lane_count(self, value):
        if value < 1:
            raise serializers.ValidationError("Lane count must be at least 1.")
        return value

    def validate(self, data):
        start = data.get("start_intersection")
        end   = data.get("end_intersection")
        if start and end and start == end:
            raise serializers.ValidationError(
                "start_intersection and end_intersection must be different."
            )
        return data


# ---------------------------------------------------------------------------
# Lane
# ---------------------------------------------------------------------------

class LaneSerializer(serializers.ModelSerializer):
    """Read serializer for Lane."""

    segment_road_name = serializers.CharField(
        source="segment.road.name", read_only=True
    )

    class Meta:
        model = Lane
        fields = [
            "id", "segment", "segment_road_name",
            "lane_number", "lane_type", "description",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class LaneWriteSerializer(serializers.ModelSerializer):
    """Write serializer for Lane."""

    class Meta:
        model = Lane
        fields = ["segment", "lane_number", "lane_type", "description"]

    def validate_segment(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot add a lane to an inactive road segment."
            )
        return value

    def validate_lane_number(self, value):
        if value < 1:
            raise serializers.ValidationError("Lane number must be at least 1.")
        return value

    def validate(self, data):
        segment = data.get("segment")
        lane_number = data.get("lane_number")
        if segment and lane_number:
            # On create, check for duplicate. On update, instance is set.
            instance = getattr(self, "instance", None)
            qs = Lane.objects.filter(segment=segment, lane_number=lane_number)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f"Lane {lane_number} already exists on segment {segment.pk}."
                )
        return data
