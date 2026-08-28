from django.contrib import admin
from apps.roads.models import Intersection, Lane, Road, RoadSegment


@admin.register(Road)
class RoadAdmin(admin.ModelAdmin):
    list_display = ("name", "road_type", "is_active", "created_at")
    list_filter  = ("road_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Intersection)
class IntersectionAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "is_active", "created_at")
    list_filter  = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(RoadSegment)
class RoadSegmentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "road", "speed_limit_kmh", "lane_count",
                    "direction", "is_active")
    list_filter  = ("is_active", "direction")
    search_fields = ("road__name", "name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("road", "start_intersection", "end_intersection")


@admin.register(Lane)
class LaneAdmin(admin.ModelAdmin):
    list_display = ("__str__", "segment", "lane_number", "lane_type", "is_active")
    list_filter  = ("lane_type", "is_active")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("segment",)
