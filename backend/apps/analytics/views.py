"""
Analytics API views — Phase 4E.

All endpoints are READ-ONLY. Analytics records are append-only and are
written exclusively by background Celery tasks, never via the API.
(data-flow.md: "Analytics: Written by cron/Celery tasks, never by web requests.")

RBAC (rbac-matrix.md):
  Traffic Flow Summary : Admin R, TCO R, Analyst R, Public R (deferred to Phase 5)
  Incident Report      : Admin R, TCO R, Analyst R, Law Enf R
  Violation Summary    : Admin R, Analyst R, Law Enf R, Pay/Fines R

All endpoints require authentication in Phase 4E.
Public unauthenticated access is deferred to Phase 5 per real-time-architecture.md.

No audit events are emitted — architecture says "Audit: No" for analytics.
"""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.models import IncidentReport, TrafficFlowSummary, ViolationSummary
from apps.analytics.serializers import (
    IncidentReportSerializer,
    TrafficFlowSummarySerializer,
    ViolationSummarySerializer,
)
from apps.common.pagination import StandardResultsPagination
from apps.common.responses import success_response

# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------
_ADMIN   = "System Administrator"
_TCO     = "Traffic Control Officer"
_ANALYST = "Traffic Analyst"
_LAW     = "Law Enforcement / Authorized Officer"
_PAY     = "Payment/Fines Officer"


def _in_groups(user, *groups: str) -> bool:
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=groups).exists()


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class _FlowReadPermission(IsAuthenticated):
    """Traffic Flow Summary: Admin, TCO, Analyst."""
    def has_permission(self, request, view) -> bool:
        return (super().has_permission(request, view) and
                _in_groups(request.user, _ADMIN, _TCO, _ANALYST))


class _IncidentReadPermission(IsAuthenticated):
    """Incident Report: Admin, TCO, Analyst, Law Enforcement."""
    def has_permission(self, request, view) -> bool:
        return (super().has_permission(request, view) and
                _in_groups(request.user, _ADMIN, _TCO, _ANALYST, _LAW))


class _ViolationSummaryReadPermission(IsAuthenticated):
    """Violation Summary: Admin, Analyst, Law Enforcement, Pay/Fines."""
    def has_permission(self, request, view) -> bool:
        return (super().has_permission(request, view) and
                _in_groups(request.user, _ADMIN, _ANALYST, _LAW, _PAY))


# ---------------------------------------------------------------------------
# Shared filter helper
# ---------------------------------------------------------------------------

def _apply_common_filters(qs, params):
    """Apply segment and period filters from query params."""
    if seg := params.get("segment"):
        qs = qs.filter(segment_id=seg)
    if pt := params.get("period_type"):
        qs = qs.filter(period_type=pt)
    if ps := params.get("period_start"):
        qs = qs.filter(period_start__gte=ps)
    if pe := params.get("period_end"):
        qs = qs.filter(period_end__lte=pe)
    return qs


# ---------------------------------------------------------------------------
# Traffic Flow Summary
# ---------------------------------------------------------------------------

class TrafficFlowSummaryListView(APIView):
    """GET /api/v1/analytics/flow/"""
    permission_classes = [_FlowReadPermission]

    def get(self, request: Request) -> Response:
        qs = _apply_common_filters(
            TrafficFlowSummary.objects.select_related("segment").order_by("-period_start"),
            request.query_params,
        )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            TrafficFlowSummarySerializer(page, many=True).data
        )


class TrafficFlowSummaryDetailView(APIView):
    """GET /api/v1/analytics/flow/{id}/"""
    permission_classes = [_FlowReadPermission]

    def get(self, request: Request, pk: int) -> Response:
        obj = get_object_or_404(TrafficFlowSummary.objects.select_related("segment"), pk=pk)
        return success_response(data=TrafficFlowSummarySerializer(obj).data)


# ---------------------------------------------------------------------------
# Incident Report
# ---------------------------------------------------------------------------

class IncidentReportListView(APIView):
    """GET /api/v1/analytics/incidents/"""
    permission_classes = [_IncidentReadPermission]

    def get(self, request: Request) -> Response:
        qs = _apply_common_filters(
            IncidentReport.objects.select_related("segment").order_by("-period_start"),
            request.query_params,
        )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            IncidentReportSerializer(page, many=True).data
        )


class IncidentReportDetailView(APIView):
    """GET /api/v1/analytics/incidents/{id}/"""
    permission_classes = [_IncidentReadPermission]

    def get(self, request: Request, pk: int) -> Response:
        obj = get_object_or_404(IncidentReport.objects.select_related("segment"), pk=pk)
        return success_response(data=IncidentReportSerializer(obj).data)


# ---------------------------------------------------------------------------
# Violation Summary
# ---------------------------------------------------------------------------

class ViolationSummaryListView(APIView):
    """GET /api/v1/analytics/violations/"""
    permission_classes = [_ViolationSummaryReadPermission]

    def get(self, request: Request) -> Response:
        qs = _apply_common_filters(
            ViolationSummary.objects.select_related("segment").order_by("-period_start"),
            request.query_params,
        )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            ViolationSummarySerializer(page, many=True).data
        )


class ViolationSummaryDetailView(APIView):
    """GET /api/v1/analytics/violations/{id}/"""
    permission_classes = [_ViolationSummaryReadPermission]

    def get(self, request: Request, pk: int) -> Response:
        obj = get_object_or_404(ViolationSummary.objects.select_related("segment"), pk=pk)
        return success_response(data=ViolationSummarySerializer(obj).data)
