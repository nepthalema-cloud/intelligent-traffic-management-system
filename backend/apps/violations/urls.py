"""URL configuration for the violations app."""

from django.urls import path

from apps.violations.views import (
    CitationDetailView,
    CitationListView,
    CitationStateView,
    VehicleDetailView,
    VehicleListView,
    VehicleStatusView,
    ViolationDetailView,
    ViolationEvidenceListView,
    ViolationListView,
    ViolationStatusView,
)

app_name = "violations"

urlpatterns = [
    # ── Vehicles (Phase 4D.1) ─────────────────────────────────────────────
    path("vehicles/",                   VehicleListView.as_view(),   name="vehicle-list"),
    path("vehicles/<int:vehicle_id>/",  VehicleDetailView.as_view(), name="vehicle-detail"),
    path("vehicles/<int:vehicle_id>/status/", VehicleStatusView.as_view(), name="vehicle-status"),

    # ── TrafficViolations (Phase 4D.2) ───────────────────────────────────
    path("",                                    ViolationListView.as_view(),   name="violation-list"),
    path("<int:violation_id>/",                 ViolationDetailView.as_view(), name="violation-detail"),
    path("<int:violation_id>/status/",          ViolationStatusView.as_view(), name="violation-status"),
    path("<int:violation_id>/evidence/",        ViolationEvidenceListView.as_view(), name="evidence-list"),

    # ── Citations (Phase 4D.2) ────────────────────────────────────────────
    path("citations/",                  CitationListView.as_view(),  name="citation-list"),
    path("citations/<int:citation_id>/", CitationDetailView.as_view(), name="citation-detail"),
    path("citations/<int:citation_id>/state/", CitationStateView.as_view(), name="citation-state"),
]
