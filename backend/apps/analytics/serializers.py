"""Serializers for the analytics app — Phase 4E. All read-only."""

from rest_framework import serializers
from apps.analytics.models import IncidentReport, TrafficFlowSummary, ViolationSummary


class TrafficFlowSummarySerializer(serializers.ModelSerializer):
    segment_name = serializers.SerializerMethodField()

    class Meta:
        model = TrafficFlowSummary
        fields = [
            "id", "segment", "segment_name", "period_type",
            "period_start", "period_end",
            "total_vehicle_count", "avg_speed_kmh", "avg_occupancy_pct",
            "sample_count", "created_at",
        ]
        read_only_fields = fields

    def get_segment_name(self, obj) -> str | None:
        return obj.segment.name if obj.segment_id and obj.segment else None


class IncidentReportSerializer(serializers.ModelSerializer):
    segment_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentReport
        fields = [
            "id", "segment", "segment_name", "period_type",
            "period_start", "period_end",
            "total_incidents", "by_type", "by_state", "created_at",
        ]
        read_only_fields = fields

    def get_segment_name(self, obj) -> str | None:
        return obj.segment.name if obj.segment_id and obj.segment else None


class ViolationSummarySerializer(serializers.ModelSerializer):
    segment_name = serializers.SerializerMethodField()

    class Meta:
        model = ViolationSummary
        fields = [
            "id", "segment", "segment_name", "period_type",
            "period_start", "period_end",
            "total_violations", "by_type", "created_at",
        ]
        read_only_fields = fields

    def get_segment_name(self, obj) -> str | None:
        return obj.segment.name if obj.segment_id and obj.segment else None
