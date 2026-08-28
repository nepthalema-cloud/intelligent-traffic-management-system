"""Django admin for the analytics app — Phase 4E. All views are read-only."""

from django.contrib import admin
from apps.analytics.models import IncidentReport, TrafficFlowSummary, ViolationSummary


class _ReadOnlyAdmin(admin.ModelAdmin):
    """Base admin class that prevents add/change/delete via the admin UI."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TrafficFlowSummary)
class TrafficFlowSummaryAdmin(_ReadOnlyAdmin):
    list_display  = ("id", "segment", "period_type", "period_start", "period_end",
                     "total_vehicle_count", "avg_speed_kmh", "sample_count", "created_at")
    list_filter   = ("period_type",)
    search_fields = ("segment__name",)
    readonly_fields = [f.name for f in TrafficFlowSummary._meta.get_fields()
                       if hasattr(f, "name")]
    ordering = ("-period_start",)


@admin.register(IncidentReport)
class IncidentReportAdmin(_ReadOnlyAdmin):
    list_display  = ("id", "segment", "period_type", "period_start",
                     "total_incidents", "created_at")
    list_filter   = ("period_type",)
    search_fields = ("segment__name",)
    readonly_fields = [f.name for f in IncidentReport._meta.get_fields()
                       if hasattr(f, "name")]
    ordering = ("-period_start",)


@admin.register(ViolationSummary)
class ViolationSummaryAdmin(_ReadOnlyAdmin):
    list_display  = ("id", "segment", "period_type", "period_start",
                     "total_violations", "created_at")
    list_filter   = ("period_type",)
    search_fields = ("segment__name",)
    readonly_fields = [f.name for f in ViolationSummary._meta.get_fields()
                       if hasattr(f, "name")]
    ordering = ("-period_start",)
