"""URL configuration for the roads app."""

from django.urls import path

from apps.roads.views import (
    IntersectionDetailView,
    IntersectionListView,
    IntersectionStatusView,
    LaneDetailView,
    LaneListView,
    LaneStatusView,
    RoadDetailView,
    RoadListView,
    RoadStatusView,
    SegmentDetailView,
    SegmentListView,
    SegmentStatusView,
)

app_name = "roads"

urlpatterns = [
    # Roads
    path("", RoadListView.as_view(), name="road-list"),
    path("<int:road_id>/", RoadDetailView.as_view(), name="road-detail"),
    path("<int:road_id>/status/", RoadStatusView.as_view(), name="road-status"),

    # Intersections
    path("intersections/", IntersectionListView.as_view(), name="intersection-list"),
    path("intersections/<int:intersection_id>/", IntersectionDetailView.as_view(), name="intersection-detail"),
    path("intersections/<int:intersection_id>/status/", IntersectionStatusView.as_view(), name="intersection-status"),

    # Segments
    path("segments/", SegmentListView.as_view(), name="segment-list"),
    path("segments/<int:segment_id>/", SegmentDetailView.as_view(), name="segment-detail"),
    path("segments/<int:segment_id>/status/", SegmentStatusView.as_view(), name="segment-status"),

    # Lanes
    path("lanes/", LaneListView.as_view(), name="lane-list"),
    path("lanes/<int:lane_id>/", LaneDetailView.as_view(), name="lane-detail"),
    path("lanes/<int:lane_id>/status/", LaneStatusView.as_view(), name="lane-status"),
]
