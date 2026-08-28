"""URL configuration for the traffic app — Phase 4C.1 / 4C.2 / 4C.3 / 4C.4."""

from django.urls import path

from apps.traffic.views import (
    EventDetailView,
    EventListView,
    EventStatusView,
    IncidentDetailView,
    IncidentListView,
    IncidentStateView,
    IncidentStatusView,
    MeasurementDetailView,
    MeasurementListView,
    PhaseDetailView,
    PhaseListView,
    PhaseStatusView,
    SignalDetailView,
    SignalListView,
    SignalStatusView,
)

app_name = "traffic"

urlpatterns = [
    # Traffic signals
    path("signals/", SignalListView.as_view(), name="signal-list"),
    path("signals/<int:signal_id>/", SignalDetailView.as_view(), name="signal-detail"),
    path("signals/<int:signal_id>/status/", SignalStatusView.as_view(), name="signal-status"),

    # Signal phases — nested under signals
    path("signals/<int:signal_id>/phases/", PhaseListView.as_view(), name="phase-list"),
    path("signals/<int:signal_id>/phases/<int:phase_id>/", PhaseDetailView.as_view(), name="phase-detail"),
    path("signals/<int:signal_id>/phases/<int:phase_id>/status/", PhaseStatusView.as_view(), name="phase-status"),

    # Traffic measurements (append-only)
    path("measurements/", MeasurementListView.as_view(), name="measurement-list"),
    path("measurements/<int:measurement_id>/", MeasurementDetailView.as_view(), name="measurement-detail"),

    # Traffic events (mutable)
    path("events/", EventListView.as_view(), name="event-list"),
    path("events/<int:event_id>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:event_id>/status/", EventStatusView.as_view(), name="event-status"),

    # Traffic incidents (mutable with lifecycle)
    path("incidents/", IncidentListView.as_view(), name="incident-list"),
    path("incidents/<int:incident_id>/", IncidentDetailView.as_view(), name="incident-detail"),
    path("incidents/<int:incident_id>/state/", IncidentStateView.as_view(), name="incident-state"),
    path("incidents/<int:incident_id>/status/", IncidentStatusView.as_view(), name="incident-status"),
]
