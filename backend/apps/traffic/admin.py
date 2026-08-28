from django.contrib import admin
from apps.traffic.models import SignalPhase, TrafficEvent, TrafficIncident, TrafficMeasurement, TrafficSignal


@admin.register(TrafficSignal)
class TrafficSignalAdmin(admin.ModelAdmin):
    list_display = ("name", "intersection", "controller_type", "is_active", "created_at")
    list_filter  = ("is_active",)
    search_fields = ("name", "controller_identifier")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("intersection",)


@admin.register(SignalPhase)
class SignalPhaseAdmin(admin.ModelAdmin):
    list_display = (
        "signal", "phase_number", "name",
        "minimum_green_seconds", "maximum_green_seconds",
        "yellow_seconds", "all_red_seconds",
        "is_active",
    )
    list_filter  = ("is_active",)
    search_fields = ("signal__name", "name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("signal",)


@admin.register(TrafficMeasurement)
class TrafficMeasurementAdmin(admin.ModelAdmin):
    """Read-only admin for TrafficMeasurement — append-only records."""

    list_display = (
        "id", "measured_at", "segment", "camera", "sensor",
        "vehicle_count", "avg_speed_kmh", "occupancy_pct", "created_at",
    )
    list_filter  = ("camera", "sensor")
    search_fields = ("segment__road__name",)
    readonly_fields = (
        "id", "segment", "camera", "sensor",
        "measured_at", "vehicle_count", "avg_speed_kmh",
        "occupancy_pct", "created_at",
    )
    raw_id_fields = ("segment", "camera", "sensor")
    ordering = ("-measured_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TrafficEvent)
class TrafficEventAdmin(admin.ModelAdmin):
    list_display = (
        "id", "event_type", "description", "occurred_at",
        "segment", "intersection", "created_by", "is_active", "created_at",
    )
    list_filter  = ("event_type", "is_active")
    search_fields = ("description",)
    readonly_fields = ("created_at", "updated_at", "created_by")
    raw_id_fields = ("segment", "intersection")
    ordering = ("-occurred_at",)


@admin.register(TrafficIncident)
class TrafficIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "incident_type", "state",
        "occurred_at", "intersection", "is_active", "created_at",
    )
    list_filter  = ("incident_type", "state", "is_active")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at", "created_by", "state")
    raw_id_fields = ("intersection",)
    filter_horizontal = ("segments",)
    ordering = ("-occurred_at",)
