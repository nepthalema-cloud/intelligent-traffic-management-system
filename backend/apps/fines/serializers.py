from rest_framework import serializers

from apps.fines.models import Fine, Payment


class FineSerializer(serializers.ModelSerializer):
    violation_type = serializers.CharField(source="violation.violation_type", read_only=True)
    vehicle_id = serializers.IntegerField(source="violation.vehicle_id", read_only=True)

    class Meta:
        model = Fine
        fields = [
            "id",
            "violation",
            "violation_type",
            "vehicle_id",
            "amount",
            "status",
            "reference",
            "notes",
            "issued_at",
            "updated_at",
        ]
        read_only_fields = fields


class FineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fine
        fields = ["violation", "amount", "status", "reference", "notes"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    fine_reference = serializers.CharField(source="fine.reference", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "fine",
            "fine_reference",
            "amount",
            "status",
            "payment_reference",
            "payment_method",
            "provider",
            "provider_reference",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["fine", "amount", "status", "payment_reference", "payment_method", "provider", "provider_reference", "notes"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
