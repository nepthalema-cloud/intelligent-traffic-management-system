from django.contrib import admin
from apps.cameras.models import Camera, CameraHealth, Sensor, SensorHealth


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "camera_type", "is_active", "ip_address", "created_at")
    list_filter  = ("camera_type", "is_active")
    search_fields = ("name", "ip_address")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("segment", "intersection")


@admin.register(CameraHealth)
class CameraHealthAdmin(admin.ModelAdmin):
    list_display = ("camera", "health_status", "connectivity_status", "checked_at")
    list_filter  = ("health_status", "connectivity_status")
    readonly_fields = ("checked_at",)
    raw_id_fields = ("camera",)


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ("name", "sensor_type", "is_active", "created_at")
    list_filter  = ("sensor_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("segment", "intersection")


@admin.register(SensorHealth)
class SensorHealthAdmin(admin.ModelAdmin):
    list_display = ("sensor", "health_status", "connectivity_status", "checked_at")
    list_filter  = ("health_status", "connectivity_status")
    readonly_fields = ("checked_at",)
    raw_id_fields = ("sensor",)
