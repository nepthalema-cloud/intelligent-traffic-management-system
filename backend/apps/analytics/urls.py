"""URL configuration for the analytics app — Phase 4E."""

from django.urls import path
from apps.analytics.views import (
    IncidentReportDetailView,
    IncidentReportListView,
    TrafficFlowSummaryDetailView,
    TrafficFlowSummaryListView,
    ViolationSummaryDetailView,
    ViolationSummaryListView,
)

app_name = "analytics"

urlpatterns = [
    path("flow/",               TrafficFlowSummaryListView.as_view(),   name="flow-list"),
    path("flow/<int:pk>/",      TrafficFlowSummaryDetailView.as_view(), name="flow-detail"),
    path("incidents/",          IncidentReportListView.as_view(),       name="incident-list"),
    path("incidents/<int:pk>/", IncidentReportDetailView.as_view(),     name="incident-detail"),
    path("violations/",         ViolationSummaryListView.as_view(),     name="violation-list"),
    path("violations/<int:pk>/",ViolationSummaryDetailView.as_view(),   name="violation-detail"),
]
