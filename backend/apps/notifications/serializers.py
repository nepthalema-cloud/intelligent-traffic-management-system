from rest_framework import serializers

from apps.notifications.models import Notification, NotificationTemplate


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "code", "notification_type", "subject", "body", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class NotificationTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["code", "notification_type", "subject", "body", "is_active"]


class NotificationSerializer(serializers.ModelSerializer):
    recipient_username = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "recipient_username",
            "notification_type",
            "title",
            "message",
            "related_model",
            "related_id",
            "is_read",
            "delivery_status",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields

    def get_recipient_username(self, obj):
        return obj.recipient.username if obj.recipient else None


class NotificationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["recipient", "notification_type", "title", "message", "related_model", "related_id", "delivery_status"]
