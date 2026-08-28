"""
Views for the violations app.

Phase 4D.1 endpoints (Vehicle — unchanged)
------------------------------------------
GET    /api/v1/violations/vehicles/
POST   /api/v1/violations/vehicles/
GET    /api/v1/violations/vehicles/{id}/
PATCH  /api/v1/violations/vehicles/{id}/
PATCH  /api/v1/violations/vehicles/{id}/status/

Phase 4D.2 endpoints
---------------------
GET    /api/v1/violations/                           List violations (paginated)
POST   /api/v1/violations/                           Create violation
GET    /api/v1/violations/{id}/                      Violation detail
PATCH  /api/v1/violations/{id}/status/               Deactivate/reactivate (Admin only)

GET    /api/v1/violations/{id}/evidence/             List evidence for a violation
POST   /api/v1/violations/{id}/evidence/             Attach evidence

GET    /api/v1/violations/citations/                 List citations (paginated)
POST   /api/v1/violations/citations/                 Issue a new citation
GET    /api/v1/violations/citations/{id}/            Citation detail
PATCH  /api/v1/violations/citations/{id}/state/      Lifecycle transition

RBAC (from rbac-matrix.md)
---------------------------
TrafficViolation:
  Admin: CRUD + status    Law Enf: CRUD (C=create, R=read, D=deactivate)
  Analyst: R (list/detail — no create, no status)
  Pay/Fines: R
  All other roles: 403

ViolationEvidence:
  Admin: CRUD    Law Enf: CR
  All other roles: 403

Citation:
  Admin: CRUD    Law Enf: CRUD    Pay/Fines: R
  All other roles: 403

PII policy
----------
TrafficViolationSerializer deliberately does NOT expose plate_number.
The vehicle FK id is exposed; authorised users must make a separate vehicle
detail request to retrieve plate_number.  This ensures the audit trail
captures vehicle-detail access separately.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.violations.models import Citation, TrafficViolation, Vehicle, ViolationEvidence
from apps.violations.serializers import (
    CitationSerializer,
    CitationStateSerializer,
    CitationWriteSerializer,
    TrafficViolationSerializer,
    TrafficViolationWriteSerializer,
    VehicleSerializer,
    VehicleWriteSerializer,
    ViolationEvidenceSerializer,
    ViolationEvidenceWriteSerializer,
)
from apps.violations.services import (
    CitationService,
    EvidenceService,
    InvalidCitationTransitionError,
    VehicleService,
    ViolationService,
)

# ---------------------------------------------------------------------------
# Role name constants
# ---------------------------------------------------------------------------

_ADMIN       = "System Administrator"
_LAW         = "Law Enforcement / Authorized Officer"
_ANALYST     = "Traffic Analyst"
_PAY_FINES   = "Payment/Fines Officer"

# ---------------------------------------------------------------------------
# Reusable permission helpers
# ---------------------------------------------------------------------------

def _in_groups(user, *groups: str) -> bool:
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=groups).exists()


# ---------------------------------------------------------------------------
# Vehicle permission classes (Phase 4D.1 — unchanged)
# ---------------------------------------------------------------------------

class _VehicleReadPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW, _PAY_FINES
        )


class _VehicleWritePermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


class _VehicleStatusPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


class _VehicleListWritePermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return _in_groups(request.user, _ADMIN, _LAW, _PAY_FINES)
        return _in_groups(request.user, _ADMIN, _LAW)


# ---------------------------------------------------------------------------
# Violation permission classes (Phase 4D.2)
# ---------------------------------------------------------------------------

class _ViolationReadPermission(IsAuthenticated):
    """Read: Admin, Law Enforcement, Analyst, Pay/Fines."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW, _ANALYST, _PAY_FINES
        )


class _ViolationWritePermission(IsAuthenticated):
    """Create: Admin, Law Enforcement."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


class _ViolationStatusPermission(IsAuthenticated):
    """Deactivate/reactivate: Admin only."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN
        )


class _ViolationListPermission(IsAuthenticated):
    """List + Create combined: read=Admin+Law+Analyst+PayFines, write=Admin+Law."""
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return _in_groups(request.user, _ADMIN, _LAW, _ANALYST, _PAY_FINES)
        return _in_groups(request.user, _ADMIN, _LAW)


# ---------------------------------------------------------------------------
# Evidence permission classes (Phase 4D.2)
# ---------------------------------------------------------------------------

class _EvidenceReadPermission(IsAuthenticated):
    """Read evidence: Admin, Law Enforcement."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


class _EvidenceListPermission(IsAuthenticated):
    """List + Create evidence: Admin+Law for both."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


# ---------------------------------------------------------------------------
# Citation permission classes (Phase 4D.2)
# ---------------------------------------------------------------------------

class _CitationReadPermission(IsAuthenticated):
    """Read: Admin, Law Enforcement, Pay/Fines."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW, _PAY_FINES
        )


class _CitationWritePermission(IsAuthenticated):
    """Create / transition: Admin, Law Enforcement."""
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and _in_groups(
            request.user, _ADMIN, _LAW
        )


class _CitationListPermission(IsAuthenticated):
    """List + Create citations: read=Admin+Law+PayFines, write=Admin+Law."""
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return _in_groups(request.user, _ADMIN, _LAW, _PAY_FINES)
        return _in_groups(request.user, _ADMIN, _LAW)


# ===========================================================================
# Vehicle views (Phase 4D.1 — unchanged)
# ===========================================================================

class VehicleListView(APIView):
    permission_classes = [_VehicleListWritePermission]

    def get(self, request: Request) -> Response:
        qs = Vehicle.objects.order_by("-created_at")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if vt := request.query_params.get("vehicle_type"):
            qs = qs.filter(vehicle_type=vt)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(VehicleSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = VehicleWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        vehicle = VehicleService.create(
            actor=request.user,
            plate_number=ser.validated_data["plate_number"],
            vehicle_type=ser.validated_data.get("vehicle_type", "other"),
            registration_country=ser.validated_data.get("registration_country", ""),
            color=ser.validated_data.get("color", ""),
            make=ser.validated_data.get("make", ""),
            model=ser.validated_data.get("model", ""),
            year=ser.validated_data.get("year"),
            request=request,
        )
        return created_response(
            data=VehicleSerializer(vehicle).data,
            message="Vehicle created successfully.",
        )


class VehicleDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [_VehicleReadPermission()]
        return [_VehicleWritePermission()]

    def _get(self, vehicle_id: int) -> Vehicle:
        return get_object_or_404(Vehicle, pk=vehicle_id)

    def get(self, request: Request, vehicle_id: int) -> Response:
        return success_response(data=VehicleSerializer(self._get(vehicle_id)).data)

    def patch(self, request: Request, vehicle_id: int) -> Response:
        vehicle = self._get(vehicle_id)
        ser = VehicleWriteSerializer(vehicle, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        vehicle = VehicleService.update(
            actor=request.user, vehicle=vehicle, request=request, **ser.validated_data,
        )
        return success_response(
            data=VehicleSerializer(vehicle).data,
            message="Vehicle updated successfully.",
        )


class VehicleStatusView(APIView):
    permission_classes = [_VehicleStatusPermission]

    def patch(self, request: Request, vehicle_id: int) -> Response:
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        vehicle = VehicleService.set_active(
            actor=request.user, vehicle=vehicle, is_active=is_active, request=request
        )
        action = "activated" if is_active else "deactivated"
        return success_response(
            data=VehicleSerializer(vehicle).data,
            message=f"Vehicle {action}.",
        )


# ===========================================================================
# TrafficViolation views (Phase 4D.2)
# ===========================================================================

class ViolationListView(APIView):
    """
    GET  /api/v1/violations/         List violations (paginated)
    POST /api/v1/violations/         Create violation (Admin, Law Enforcement)
    """
    permission_classes = [_ViolationListPermission]

    def get(self, request: Request) -> Response:
        qs = (
            TrafficViolation.objects
            .select_related("vehicle", "segment", "intersection", "camera", "reported_by")
            .order_by("-occurred_at")
        )
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if vt := request.query_params.get("violation_type"):
            qs = qs.filter(violation_type=vt)
        if vid := request.query_params.get("vehicle"):
            qs = qs.filter(vehicle_id=vid)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            TrafficViolationSerializer(page, many=True).data
        )

    def post(self, request: Request) -> Response:
        ser = TrafficViolationWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        vd = ser.validated_data
        violation = ViolationService.create(
            actor=request.user,
            violation_type=vd["violation_type"],
            occurred_at=vd["occurred_at"],
            vehicle=vd["vehicle"],
            description=vd.get("description", ""),
            segment=vd.get("segment"),
            intersection=vd.get("intersection"),
            camera=vd.get("camera"),
            reported_by=request.user,
            request=request,
        )
        return created_response(
            data=TrafficViolationSerializer(violation).data,
            message="Violation recorded.",
        )


class ViolationDetailView(APIView):
    """
    GET  /api/v1/violations/{id}/   Retrieve violation
    """
    permission_classes = [_ViolationReadPermission]

    def _get(self, violation_id: int) -> TrafficViolation:
        return get_object_or_404(
            TrafficViolation.objects.select_related(
                "vehicle", "segment", "intersection", "camera", "reported_by"
            ),
            pk=violation_id,
        )

    def get(self, request: Request, violation_id: int) -> Response:
        return success_response(
            data=TrafficViolationSerializer(self._get(violation_id)).data
        )


class ViolationStatusView(APIView):
    """
    PATCH /api/v1/violations/{id}/status/   Deactivate/reactivate (Admin only)
    """
    permission_classes = [_ViolationStatusPermission]

    def patch(self, request: Request, violation_id: int) -> Response:
        violation = get_object_or_404(TrafficViolation, pk=violation_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        if not is_active:
            violation = ViolationService.deactivate(
                actor=request.user, violation=violation, request=request
            )
        else:
            # Reactivation: direct QuerySet update (bypasses append-only save)
            TrafficViolation.objects.filter(pk=violation.pk).update(is_active=True)
            violation.refresh_from_db()
        action = "activated" if is_active else "deactivated"
        return success_response(
            data=TrafficViolationSerializer(violation).data,
            message=f"Violation {action}.",
        )


# ===========================================================================
# ViolationEvidence views (Phase 4D.2)
# ===========================================================================

class ViolationEvidenceListView(APIView):
    """
    GET  /api/v1/violations/{id}/evidence/   List evidence for a violation
    POST /api/v1/violations/{id}/evidence/   Attach evidence
    """
    permission_classes = [_EvidenceListPermission]

    def _violation(self, violation_id: int) -> TrafficViolation:
        return get_object_or_404(TrafficViolation, pk=violation_id)

    def get(self, request: Request, violation_id: int) -> Response:
        self._violation(violation_id)  # 404 if not found
        qs = ViolationEvidence.objects.filter(violation_id=violation_id).order_by("created_at")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            ViolationEvidenceSerializer(page, many=True).data
        )

    def post(self, request: Request, violation_id: int) -> Response:
        violation = self._violation(violation_id)
        # Inject the violation pk into the request data
        data = {**request.data, "violation": violation.pk}
        ser = ViolationEvidenceWriteSerializer(data=data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        evidence = EvidenceService.create(
            actor=request.user,
            violation=violation,
            evidence_type=ser.validated_data["evidence_type"],
            evidence_url=ser.validated_data["evidence_url"],
            description=ser.validated_data.get("description", ""),
            request=request,
        )
        return created_response(
            data=ViolationEvidenceSerializer(evidence).data,
            message="Evidence attached.",
        )


# ===========================================================================
# Citation views (Phase 4D.2)
# ===========================================================================

class CitationListView(APIView):
    """
    GET  /api/v1/violations/citations/   List citations (paginated)
    POST /api/v1/violations/citations/   Issue a citation
    """
    permission_classes = [_CitationListPermission]

    def get(self, request: Request) -> Response:
        qs = (
            Citation.objects
            .select_related("violation", "violation__vehicle", "issued_by")
            .order_by("-issued_at")
        )
        if state := request.query_params.get("state"):
            qs = qs.filter(state=state)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            CitationSerializer(page, many=True).data
        )

    def post(self, request: Request) -> Response:
        ser = CitationWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            citation = CitationService.issue(
                actor=request.user,
                violation=ser.validated_data["violation"],
                issued_at=ser.validated_data["issued_at"],
                issued_by=request.user,
                notes=ser.validated_data.get("notes", ""),
                request=request,
            )
        except Exception as exc:
            return error_response(str(exc),
                                  status_code=status.HTTP_400_BAD_REQUEST)
        return created_response(
            data=CitationSerializer(citation).data,
            message="Citation issued.",
        )


class CitationDetailView(APIView):
    """
    GET  /api/v1/violations/citations/{id}/   Citation detail
    """
    permission_classes = [_CitationReadPermission]

    def _get(self, citation_id: int) -> Citation:
        return get_object_or_404(
            Citation.objects.select_related(
                "violation", "violation__vehicle", "issued_by"
            ),
            pk=citation_id,
        )

    def get(self, request: Request, citation_id: int) -> Response:
        return success_response(data=CitationSerializer(self._get(citation_id)).data)


class CitationStateView(APIView):
    """
    PATCH /api/v1/violations/citations/{id}/state/   Lifecycle transition
    """
    permission_classes = [_CitationWritePermission]

    def patch(self, request: Request, citation_id: int) -> Response:
        citation = get_object_or_404(Citation, pk=citation_id)
        ser = CitationStateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            citation = CitationService.transition(
                actor=request.user,
                citation=citation,
                new_state=ser.validated_data["state"],
                notes=ser.validated_data.get("notes", ""),
                request=request,
            )
        except InvalidCitationTransitionError as exc:
            return error_response(str(exc),
                                  status_code=status.HTTP_400_BAD_REQUEST)
        return success_response(
            data=CitationSerializer(citation).data,
            message=f"Citation moved to '{citation.state}'.",
        )
