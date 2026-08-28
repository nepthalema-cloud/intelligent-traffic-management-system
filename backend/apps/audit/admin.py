"""
Read-only Django admin view for audit events.

Per the architecture document: "Admin UI for audit records must be read-only."
No add, change, or delete permissions are granted.
"""

from django.contrib import admin
from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only admin for AuditEvent records."""

    list_display = (
        "timestamp", "action", "outcome", "actor_username",
        "target_type", "target_id", "ip_address",
    )
    list_filter = ("outcome", "action")
    search_fields = ("actor_username", "action", "target_id", "ip_address")
    readonly_fields = (
        "id", "timestamp", "actor_id", "actor_username", "action",
        "target_type", "target_id", "ip_address", "user_agent",
        "outcome", "detail",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
