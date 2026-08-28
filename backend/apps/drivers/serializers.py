from rest_framework import serializers

from apps.drivers.models import Driver


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            "id",
            "first_name",
            "last_name",
            "driver_identifier",
            "license_number",
            "date_of_birth",
            "phone",
            "email",
            "license_status",
            "license_issue_date",
            "license_expiry_date",
            "registration_status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DriverWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            "first_name",
            "last_name",
            "driver_identifier",
            "license_number",
            "date_of_birth",
            "phone",
            "email",
            "license_status",
            "license_issue_date",
            "license_expiry_date",
            "registration_status",
        ]

    def validate_license_number(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("license_number is required.")
        return value
