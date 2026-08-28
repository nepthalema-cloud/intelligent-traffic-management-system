"""Django admin for the violations app."""

from django.contrib import admin

from apps.violations.models import Citation, TrafficViolation, Vehicle, ViolationEvidence


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display  = ("id", "plate_number", "vehicle_type", "make", "model",
                     "year", "registration_country", "is_active", "created_at")
    list_filter   = ("vehicle_type", "is_active")
    search_fields = ("plate_number", "make", "model")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(TrafficViolation)
class TrafficViolationAdmin(admin.ModelAdmin):
    """
    TrafficViolation records are append-only legal evidence.
    Admin staff may view but should not modify records.
    """
    list_display  = ("id", "violation_type", "vehicle", "occurred_at",
                     "reported_by", "is_active", "created_at")
    list_filter   = ("violation_type", "is_active")
    search_fields = ("vehicle__plate_number",)
    readonly_fields = ("violation_type", "description", "occurred_at",
                       "vehicle", "segment", "intersection", "camera",
                       "reported_by", "is_active", "created_at")
    ordering = ("-occurred_at",)

    def has_add_permission(self, request):
        return False  # Use the API, not admin, to create violations

    def has_delete_permission(self, request, obj=None):
        return False  # Append-only


@admin.register(ViolationEvidence)
class ViolationEvidenceAdmin(admin.ModelAdmin):
    list_display  = ("id", "violation", "evidence_type", "evidence_url", "created_at")
    list_filter   = ("evidence_type",)
    readonly_fields = ("violation", "evidence_type", "evidence_url",
                       "description", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    list_display  = ("id", "violation", "state", "issued_by", "issued_at",
                     "created_at", "updated_at")
    list_filter   = ("state",)
    readonly_fields = ("violation", "issued_by", "issued_at", "created_at", "updated_at")
    ordering = ("-issued_at",)
