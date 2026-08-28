from rest_framework import serializers

from apps.organizations.models import City, Region, TrafficControlCenter


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name", "code", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class RegionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["name", "code", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Region name is required.")
        return value


class CitySerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)

    class Meta:
        model = City
        fields = ["id", "region", "region_name", "name", "code", "description", "latitude", "longitude", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class CityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["region", "name", "code", "description", "latitude", "longitude"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("City name is required.")
        return value


class TrafficControlCenterSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = TrafficControlCenter
        fields = ["id", "name", "code", "region", "region_name", "city", "city_name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class TrafficControlCenterWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrafficControlCenter
        fields = ["name", "code", "region", "city", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Control center name is required.")
        return value
