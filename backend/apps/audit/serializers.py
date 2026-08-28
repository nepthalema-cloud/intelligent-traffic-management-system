"""Serializers for the audit app."""

from rest_framework import serializers
from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """Read-only serializer for audit events."""

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "timestamp",
            "actor_id",
            "actor_username",
            "action",
            "target_type",
            "target_id",
            "ip_address",
            "user_agent",
            "outcome",
            "detail",
        ]
        read_only_fields = fields
