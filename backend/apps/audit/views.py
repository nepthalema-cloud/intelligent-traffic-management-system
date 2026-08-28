"""
Audit API views.

GET /api/v1/audit/events/     System Admin only — paginated audit event list
GET /api/v1/audit/events/{id}/ System Admin only — single audit event detail
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer
from apps.common.pagination import StandardResultsPagination
from apps.common.responses import not_found_response, success_response


class AuditEventListView(APIView):
    """
    GET /api/v1/audit/events/

    Return a paginated list of audit events, newest first.

    Access
    ------
    System Administrator or superuser only.
    Unauthenticated → 401.
    Non-admin → 403.

    Query parameters
    ----------------
    page      : page number (default 1)
    page_size : results per page (default 20, max 100)
    action    : filter by action code (optional)
    outcome   : filter by outcome (optional)
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get(self, request: Request) -> Response:
        qs = AuditEvent.objects.all()

        action_filter = request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)

        outcome_filter = request.query_params.get("outcome")
        if outcome_filter:
            qs = qs.filter(outcome=outcome_filter)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = AuditEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AuditEventDetailView(APIView):
    """
    GET /api/v1/audit/events/{id}/

    Return a single audit event by UUID primary key.

    Access
    ------
    System Administrator or superuser only.
    Non-existent record → 404.
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get(self, request: Request, event_id: str) -> Response:
        try:
            event = AuditEvent.objects.get(pk=event_id)
        except (AuditEvent.DoesNotExist, Exception):
            return not_found_response("Audit event not found.")
        serializer = AuditEventSerializer(event)
        return success_response(data=serializer.data)
