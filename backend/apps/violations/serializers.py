"""Serializers for the violations app."""

from django.utils import timezone
from rest_framework import serializers

from apps.violations.models import Citation, TrafficViolation, Vehicle, ViolationEvidence


# ---------------------------------------------------------------------------
# Vehicle serializers (Phase 4D.1 — unchanged)
# ---------------------------------------------------------------------------

class VehicleSerializer(serializers.ModelSerializer):
    """Read serializer for Vehicle responses."""

    class Meta:
        model = Vehicle
        fields = [
            "id", "plate_number", "vehicle_type", "registration_country",
            "color", "make", "model", "year", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class VehicleWriteSerializer(serializers.ModelSerializer):
    """Write serializer for Vehicle create/update requests."""

    class Meta:
        model = Vehicle
        fields = [
            "plate_number", "vehicle_type", "registration_country",
            "color", "make", "model", "year",
        ]

    def validate_plate_number(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("plate_number may not be blank.")
        return value

    def validate_vehicle_type(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("vehicle_type may not be blank.")
        return value

    def validate_year(self, value: int | None) -> int | None:
        if value is None:
            return value
        current_year = timezone.now().year
        if value < 1886:
            raise serializers.ValidationError(
                "year must be 1886 or later."
            )
        if value > current_year + 2:
            raise serializers.ValidationError(
                f"year must not exceed {current_year + 2}."
            )
        return value


# ---------------------------------------------------------------------------
# TrafficViolation serializers (Phase 4D.2)
# ---------------------------------------------------------------------------

class TrafficViolationSerializer(serializers.ModelSerializer):
    """Read serializer for TrafficViolation.

    PII note: vehicle plate_number is accessible to authorised readers
    (Admin, Law Enforcement) via the nested vehicle_id.  This serializer
    does NOT expand the vehicle record — callers must make a separate
    vehicle detail request.  This avoids inadvertent plate PII leakage
    to roles that read violation aggregates without full vehicle access.
    """

    vehicle_type    = serializers.CharField(source="vehicle.vehicle_type", read_only=True)
    segment_name    = serializers.SerializerMethodField()
    intersection_name = serializers.SerializerMethodField()
    camera_name     = serializers.SerializerMethodField()
    reported_by_username = serializers.SerializerMethodField()
    has_citation    = serializers.SerializerMethodField()

    class Meta:
        model = TrafficViolation
        fields = [
            "id",
            "violation_type",
            "description",
            "occurred_at",
            "vehicle",          # FK id only — plate_number NOT exposed here
            "vehicle_type",
            "segment",
            "segment_name",
            "intersection",
            "intersection_name",
            "camera",
            "camera_name",
            "reported_by",
            "reported_by_username",
            "is_active",
            "has_citation",
            "created_at",
        ]
        read_only_fields = fields

    def get_segment_name(self, obj) -> str | None:
        return obj.segment.name if obj.segment_id and obj.segment else None

    def get_intersection_name(self, obj) -> str | None:
        return obj.intersection.name if obj.intersection_id and obj.intersection else None

    def get_camera_name(self, obj) -> str | None:
        return obj.camera.name if obj.camera_id and obj.camera else None

    def get_reported_by_username(self, obj) -> str | None:
        return obj.reported_by.username if obj.reported_by_id and obj.reported_by else None

    def get_has_citation(self, obj) -> bool:
        return hasattr(obj, "citation") and obj.citation is not None


class TrafficViolationWriteSerializer(serializers.ModelSerializer):
    """Write serializer for TrafficViolation creation (append-only)."""

    class Meta:
        model = TrafficViolation
        fields = [
            "violation_type",
            "description",
            "occurred_at",
            "vehicle",
            "segment",
            "intersection",
            "camera",
        ]

    def validate_violation_type(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("violation_type may not be blank.")
        return value

    def validate_occurred_at(self, value):
        if value is None:
            raise serializers.ValidationError("occurred_at is required.")
        return value

    def validate_vehicle(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot record a violation for an inactive vehicle."
            )
        return value


# ---------------------------------------------------------------------------
# ViolationEvidence serializers (Phase 4D.2)
# ---------------------------------------------------------------------------

class ViolationEvidenceSerializer(serializers.ModelSerializer):
    """Read serializer for ViolationEvidence."""

    class Meta:
        model = ViolationEvidence
        fields = [
            "id",
            "violation",
            "evidence_type",
            "evidence_url",
            "description",
            "created_at",
        ]
        read_only_fields = fields


class ViolationEvidenceWriteSerializer(serializers.ModelSerializer):
    """Write serializer for ViolationEvidence creation (append-only)."""

    class Meta:
        model = ViolationEvidence
        fields = [
            "violation",
            "evidence_type",
            "evidence_url",
            "description",
        ]

    def validate_evidence_url(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("evidence_url may not be blank.")
        return value


# ---------------------------------------------------------------------------
# Citation serializers (Phase 4D.2)
# ---------------------------------------------------------------------------

class CitationSerializer(serializers.ModelSerializer):
    """Read serializer for Citation."""

    issued_by_username = serializers.SerializerMethodField()
    violation_type     = serializers.CharField(
        source="violation.violation_type", read_only=True
    )

    class Meta:
        model = Citation
        fields = [
            "id",
            "violation",
            "violation_type",
            "issued_by",
            "issued_by_username",
            "issued_at",
            "state",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_issued_by_username(self, obj) -> str | None:
        return obj.issued_by.username if obj.issued_by_id and obj.issued_by else None


class CitationWriteSerializer(serializers.ModelSerializer):
    """Write serializer for Citation creation (issue a new citation)."""

    class Meta:
        model = Citation
        fields = ["violation", "issued_at", "notes"]

    def validate_violation(self, value: TrafficViolation):
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot issue a citation for an inactive violation record."
            )
        # Check for existing citation
        if Citation.objects.filter(violation=value).exists():
            raise serializers.ValidationError(
                f"Violation #{value.pk} already has a citation."
            )
        return value


class CitationStateSerializer(serializers.Serializer):
    """Validates a Citation lifecycle state-transition request."""

    state = serializers.ChoiceField(choices=Citation.State.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
