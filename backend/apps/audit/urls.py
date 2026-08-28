"""URL configuration for the audit app."""

from django.urls import path
from apps.audit.views import AuditEventDetailView, AuditEventListView

app_name = "audit"

urlpatterns = [
    path("events/", AuditEventListView.as_view(), name="event-list"),
    path("events/<str:event_id>/", AuditEventDetailView.as_view(), name="event-detail"),
]
