"""
Views for the traffic app — Phase 4C.1.

Endpoints
---------
GET    /api/v1/traffic/signals/
POST   /api/v1/traffic/signals/
GET    /api/v1/traffic/signals/{id}/
PATCH  /api/v1/traffic/signals/{id}/
PATCH  /api/v1/traffic/signals/{id}/status/

GET    /api/v1/traffic/signals/{signal_id}/phases/
POST   /api/v1/traffic/signals/{signal_id}/phases/
GET    /api/v1/traffic/signals/{signal_id}/phases/{id}/
PATCH  /api/v1/traffic/signals/{signal_id}/phases/{id}/
PATCH  /api/v1/traffic/signals/{signal_id}/phases/{id}/status/

RBAC (from rbac-matrix.md)
----
- System Administrator:     full CRUD + status
- Traffic Control Officer:  full CRUD + status  (TCO has config authority)
- Traffic Analyst:          read-only
- All other roles:          403
- Unauthenticated:          401
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.traffic.models import SignalPhase, TrafficSignal
from apps.traffic.serializers import (
    SignalPhaseSerializer,
    SignalPhaseWriteSerializer,
    TrafficSignalSerializer,
    TrafficSignalWriteSerializer,
)
from apps.traffic.services import (
    DuplicatePhaseNumberError,
    DuplicateSignalNameError,
    InactiveSignalError,
    SignalPhaseService,
    TrafficSignalService,
)

_READ_ROLES  = [
    "System Administrator",
    "Traffic Control Officer",
    "Traffic Analyst",
]
_WRITE_ROLES = [
    "System Administrator",
    "Traffic Control Officer",
]


class _TrafficPermission(IsAuthenticated):
    """
    Read: Admin, TCO, Analyst
    Write (POST/PATCH/PUT/DELETE): Admin, TCO
    Other roles: 403
    Unauthenticated: 401
    """

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=_READ_ROLES).exists()
        return request.user.groups.filter(name__in=_WRITE_ROLES).exists()


# ---------------------------------------------------------------------------
# TrafficSignal — list / create
# ---------------------------------------------------------------------------

class SignalListView(APIView):
    permission_classes = [_TrafficPermission]

    def get(self, request: Request) -> Response:
        qs = TrafficSignal.objects.select_related("intersection").order_by("name")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if int_id := request.query_params.get("intersection"):
            qs = qs.filter(intersection_id=int_id)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TrafficSignalSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = TrafficSignalWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            signal = TrafficSignalService.create(
                actor=request.user,
                name=ser.validated_data["name"],
                intersection=ser.validated_data["intersection"],
                controller_type=ser.validated_data.get("controller_type", ""),
                controller_identifier=ser.validated_data.get("controller_identifier", ""),
                request=request,
            )
        except DuplicateSignalNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        signal = TrafficSignal.objects.select_related("intersection").get(pk=signal.pk)
        return created_response(
            data=TrafficSignalSerializer(signal).data,
            message="Traffic signal created successfully.",
        )


# ---------------------------------------------------------------------------
# TrafficSignal — detail / update
# ---------------------------------------------------------------------------

class SignalDetailView(APIView):
    permission_classes = [_TrafficPermission]

    def _get(self, pk: int) -> TrafficSignal:
        return get_object_or_404(
            TrafficSignal.objects.select_related("intersection"), pk=pk
        )

    def get(self, request: Request, signal_id: int) -> Response:
        return success_response(data=TrafficSignalSerializer(self._get(signal_id)).data)

    def patch(self, request: Request, signal_id: int) -> Response:
        signal = self._get(signal_id)
        ser = TrafficSignalWriteSerializer(signal, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        # intersection reassignment is intentionally allowed (configuration change)
        try:
            signal = TrafficSignalService.update(
                actor=request.user, signal=signal, request=request, **fields
            )
        except DuplicateSignalNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        signal = TrafficSignal.objects.select_related("intersection").get(pk=signal.pk)
        return success_response(
            data=TrafficSignalSerializer(signal).data,
            message="Traffic signal updated successfully.",
        )


# ---------------------------------------------------------------------------
# TrafficSignal — status (activate / deactivate)
# ---------------------------------------------------------------------------

class SignalStatusView(APIView):
    permission_classes = [_TrafficPermission]

    def patch(self, request: Request, signal_id: int) -> Response:
        signal = get_object_or_404(TrafficSignal, pk=signal_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response(
                "'is_active' must be a boolean.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        signal = TrafficSignalService.set_active(
            actor=request.user, signal=signal, is_active=is_active, request=request
        )
        action = "activated" if is_active else "deactivated"
        signal = TrafficSignal.objects.select_related("intersection").get(pk=signal.pk)
        return success_response(
            data=TrafficSignalSerializer(signal).data,
            message=f"Traffic signal '{signal.name}' {action}.",
        )


# ---------------------------------------------------------------------------
# SignalPhase — list / create  (nested under signal)
# ---------------------------------------------------------------------------

class PhaseListView(APIView):
    permission_classes = [_TrafficPermission]

    def _get_signal(self, signal_id: int) -> TrafficSignal:
        return get_object_or_404(TrafficSignal, pk=signal_id)

    def get(self, request: Request, signal_id: int) -> Response:
        signal = self._get_signal(signal_id)
        qs = (
            SignalPhase.objects.filter(signal=signal)
            .select_related("signal")
            .order_by("phase_number")
        )
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(SignalPhaseSerializer(page, many=True).data)

    def post(self, request: Request, signal_id: int) -> Response:
        signal = self._get_signal(signal_id)
        ser = SignalPhaseWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            phase = SignalPhaseService.create(
                actor=request.user,
                signal=signal,
                phase_number=ser.validated_data["phase_number"],
                name=ser.validated_data["name"],
                minimum_green_seconds=ser.validated_data["minimum_green_seconds"],
                maximum_green_seconds=ser.validated_data["maximum_green_seconds"],
                yellow_seconds=ser.validated_data["yellow_seconds"],
                all_red_seconds=ser.validated_data["all_red_seconds"],
                movement=ser.validated_data.get("movement", ""),
                request=request,
            )
        except InactiveSignalError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except DuplicatePhaseNumberError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        phase = SignalPhase.objects.select_related("signal").get(pk=phase.pk)
        return created_response(
            data=SignalPhaseSerializer(phase).data,
            message="Signal phase created successfully.",
        )


# ---------------------------------------------------------------------------
# SignalPhase — detail / update  (nested under signal)
# ---------------------------------------------------------------------------

class PhaseDetailView(APIView):
    permission_classes = [_TrafficPermission]

    def _get(self, signal_id: int, phase_id: int) -> SignalPhase:
        return get_object_or_404(
            SignalPhase.objects.select_related("signal"),
            pk=phase_id,
            signal_id=signal_id,
        )

    def get(self, request: Request, signal_id: int, phase_id: int) -> Response:
        return success_response(
            data=SignalPhaseSerializer(self._get(signal_id, phase_id)).data
        )

    def patch(self, request: Request, signal_id: int, phase_id: int) -> Response:
        phase = self._get(signal_id, phase_id)
        ser = SignalPhaseWriteSerializer(phase, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        fields.pop("phase_number", None)  # phase_number cannot be changed after creation
        phase = SignalPhaseService.update(
            actor=request.user, phase=phase, request=request, **fields
        )
        phase = SignalPhase.objects.select_related("signal").get(pk=phase.pk)
        return success_response(
            data=SignalPhaseSerializer(phase).data,
            message="Signal phase updated successfully.",
        )


# ---------------------------------------------------------------------------
# SignalPhase — status  (nested under signal)
# ---------------------------------------------------------------------------

class PhaseStatusView(APIView):
    permission_classes = [_TrafficPermission]

    def patch(self, request: Request, signal_id: int, phase_id: int) -> Response:
        phase = get_object_or_404(SignalPhase, pk=phase_id, signal_id=signal_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response(
                "'is_active' must be a boolean.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        phase = SignalPhaseService.set_active(
            actor=request.user, phase=phase, is_active=is_active, request=request
        )
        action = "activated" if is_active else "deactivated"
        phase = SignalPhase.objects.select_related("signal").get(pk=phase.pk)
        return success_response(
            data=SignalPhaseSerializer(phase).data,
            message=f"Phase {phase.phase_number} {action}.",
        )


# ---------------------------------------------------------------------------
# TrafficMeasurement — Phase 4C.2
# ---------------------------------------------------------------------------
# Import here to avoid circular import with services that also import models
from apps.traffic.models import TrafficMeasurement
from apps.traffic.serializers import (
    TrafficMeasurementSerializer,
    TrafficMeasurementWriteSerializer,
)
from apps.traffic.services import InvalidMeasurementSourceError, MeasurementService

# RBAC for measurements (from rbac-matrix.md):
#   Write (ingest): System Administrator only
#   Read:           Admin, TCO, Analyst, Camera/Sensor Technician
_MEAS_READ_ROLES  = [
    "System Administrator",
    "Traffic Control Officer",
    "Traffic Analyst",
    "Camera/Sensor Technician",
]
_MEAS_WRITE_ROLES = ["System Administrator"]


class _MeasurementPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=_MEAS_READ_ROLES).exists()
        return request.user.groups.filter(name__in=_MEAS_WRITE_ROLES).exists()


class MeasurementListView(APIView):
    """
    GET  /api/v1/traffic/measurements/   List measurements (paginated, filtered)
    POST /api/v1/traffic/measurements/   Ingest a single measurement

    Filters
    -------
    ?segment={id}                   Filter by road segment PK
    ?camera={id}                    Filter by camera PK
    ?sensor={id}                    Filter by sensor PK
    ?measured_after=<ISO datetime>  Records with measured_at >= value
    ?measured_before=<ISO datetime> Records with measured_at <= value

    Append-only
    -----------
    No PATCH/PUT/DELETE endpoints exist.
    Measurements are immutable after creation.

    Audit
    -----
    Individual measurement inserts are NOT audited per architecture docs
    (domain-model.md: "No (volume too high)").
    """

    permission_classes = [_MeasurementPermission]

    def get(self, request: Request) -> Response:
        qs = (
            TrafficMeasurement.objects.select_related(
                "segment__road", "camera", "sensor"
            )
            .order_by("-measured_at")
        )
        if seg_id := request.query_params.get("segment"):
            qs = qs.filter(segment_id=seg_id)
        if cam_id := request.query_params.get("camera"):
            qs = qs.filter(camera_id=cam_id)
        if sen_id := request.query_params.get("sensor"):
            qs = qs.filter(sensor_id=sen_id)
        if after := request.query_params.get("measured_after"):
            qs = qs.filter(measured_at__gte=after)
        if before := request.query_params.get("measured_before"):
            qs = qs.filter(measured_at__lte=before)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            TrafficMeasurementSerializer(page, many=True).data
        )

    def post(self, request: Request) -> Response:
        ser = TrafficMeasurementWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response(
                "Invalid data.", errors=ser.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            measurement = MeasurementService.create(
                segment=ser.validated_data.get("segment"),
                measured_at=ser.validated_data["measured_at"],
                camera=ser.validated_data.get("camera"),
                sensor=ser.validated_data.get("sensor"),
                vehicle_count=ser.validated_data.get("vehicle_count"),
                avg_speed_kmh=ser.validated_data.get("avg_speed_kmh"),
                occupancy_pct=ser.validated_data.get("occupancy_pct"),
                data_source=ser.validated_data.get("data_source", "demo"),
            )
        except InvalidMeasurementSourceError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        measurement = TrafficMeasurement.objects.select_related(
            "segment__road", "camera", "sensor"
        ).get(pk=measurement.pk)
        return created_response(
            data=TrafficMeasurementSerializer(measurement).data,
            message="Traffic measurement recorded successfully.",
        )


class MeasurementDetailView(APIView):
    """
    GET /api/v1/traffic/measurements/{id}/

    Retrieve a single measurement record by primary key.
    No PATCH/PUT/DELETE — measurements are append-only.
    """

    permission_classes = [_MeasurementPermission]

    def get(self, request: Request, measurement_id: int) -> Response:
        from django.shortcuts import get_object_or_404
        m = get_object_or_404(
            TrafficMeasurement.objects.select_related(
                "segment__road", "camera", "sensor"
            ),
            pk=measurement_id,
        )
        return success_response(data=TrafficMeasurementSerializer(m).data)


# ---------------------------------------------------------------------------
# TrafficEvent — Phase 4C.3
# ---------------------------------------------------------------------------
from apps.traffic.models import TrafficEvent
from apps.traffic.serializers import TrafficEventSerializer, TrafficEventWriteSerializer
from apps.traffic.services import TrafficEventService

# RBAC for events (from rbac-matrix.md):
#   Admin:  CRUD
#   TCO:    CRU  (Create, Read, Update — but not Deactivate/Delete)
#   Analyst: R
#   Law:    R
#   Others: 403
#   Public: 403 (Public "R selected" deferred — not implemented this phase)
_EVENT_READ_ROLES  = [
    "System Administrator",
    "Traffic Control Officer",
    "Traffic Analyst",
    "Law Enforcement / Authorized Officer",
]
_EVENT_WRITE_ROLES = [
    "System Administrator",
    "Traffic Control Officer",
]
_EVENT_ADMIN_ROLES = ["System Administrator"]  # for status/deactivate


class _EventPermission(IsAuthenticated):
    """
    Read:                Admin, TCO, Analyst, Law Enforcement
    Create/Update:       Admin, TCO
    Status (activate/deactivate): Admin only
    Other roles: 403   Unauthenticated: 401
    """
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=_EVENT_READ_ROLES).exists()
        return request.user.groups.filter(name__in=_EVENT_WRITE_ROLES).exists()


class _EventStatusPermission(IsAuthenticated):
    """PATCH /events/{id}/status/ — Admin only."""
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name__in=_EVENT_ADMIN_ROLES).exists()


class EventListView(APIView):
    """
    GET  /api/v1/traffic/events/   List events (paginated, filtered)
    POST /api/v1/traffic/events/   Create a new event
    """
    permission_classes = [_EventPermission]

    def get(self, request: Request) -> Response:
        qs = (
            TrafficEvent.objects
            .select_related("segment__road", "intersection", "created_by")
            .order_by("-occurred_at")
        )
        if et := request.query_params.get("event_type"):
            qs = qs.filter(event_type=et)
        if seg_id := request.query_params.get("segment"):
            qs = qs.filter(segment_id=seg_id)
        if int_id := request.query_params.get("intersection"):
            qs = qs.filter(intersection_id=int_id)
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if after := request.query_params.get("occurred_after"):
            qs = qs.filter(occurred_at__gte=after)
        if before := request.query_params.get("occurred_before"):
            qs = qs.filter(occurred_at__lte=before)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TrafficEventSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = TrafficEventWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        event = TrafficEventService.create(
            actor=request.user,
            event_type=ser.validated_data.get("event_type", "other"),
            description=ser.validated_data["description"],
            occurred_at=ser.validated_data["occurred_at"],
            segment=ser.validated_data.get("segment"),
            intersection=ser.validated_data.get("intersection"),
            request=request,
        )
        event = TrafficEvent.objects.select_related(
            "segment__road", "intersection", "created_by"
        ).get(pk=event.pk)
        return created_response(
            data=TrafficEventSerializer(event).data,
            message="Traffic event created successfully.",
        )


class EventDetailView(APIView):
    """
    GET   /api/v1/traffic/events/{id}/   Retrieve a single event
    PATCH /api/v1/traffic/events/{id}/   Update event (Admin, TCO)
    """
    permission_classes = [_EventPermission]

    def _get(self, event_id: int) -> TrafficEvent:
        from django.shortcuts import get_object_or_404
        return get_object_or_404(
            TrafficEvent.objects.select_related("segment__road", "intersection", "created_by"),
            pk=event_id,
        )

    def get(self, request: Request, event_id: int) -> Response:
        return success_response(data=TrafficEventSerializer(self._get(event_id)).data)

    def patch(self, request: Request, event_id: int) -> Response:
        event = self._get(event_id)
        ser = TrafficEventWriteSerializer(event, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        event = TrafficEventService.update(
            actor=request.user, event=event, request=request,
            **ser.validated_data,
        )
        event = TrafficEvent.objects.select_related(
            "segment__road", "intersection", "created_by"
        ).get(pk=event.pk)
        return success_response(
            data=TrafficEventSerializer(event).data,
            message="Traffic event updated successfully.",
        )


class EventStatusView(APIView):
    """
    PATCH /api/v1/traffic/events/{id}/status/   Activate / deactivate (Admin only)
    """
    permission_classes = [_EventStatusPermission]

    def patch(self, request: Request, event_id: int) -> Response:
        from django.shortcuts import get_object_or_404
        event = get_object_or_404(TrafficEvent, pk=event_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        event = TrafficEventService.set_active(
            actor=request.user, event=event, is_active=is_active, request=request
        )
        action = "activated" if is_active else "deactivated"
        event = TrafficEvent.objects.select_related(
            "segment__road", "intersection", "created_by"
        ).get(pk=event.pk)
        return success_response(
            data=TrafficEventSerializer(event).data,
            message=f"Traffic event {action}.",
        )


# ---------------------------------------------------------------------------
# TrafficIncident — Phase 4C.4
# ---------------------------------------------------------------------------
from apps.traffic.models import TrafficIncident
from apps.traffic.serializers import (
    TrafficIncidentSerializer,
    TrafficIncidentStateSerializer,
    TrafficIncidentWriteSerializer,
)
from apps.traffic.services import (
    InvalidStateTransitionError,
    TrafficIncidentService,
)

# RBAC for incidents (from rbac-matrix.md):
#   Admin:  CRUD
#   TCO:    CRUD  (full CRUD — different from TrafficEvent where TCO=CRU)
#   Analyst: R
#   Law:    R
#   Others: 403
_INC_READ_ROLES  = [
    "System Administrator",
    "Traffic Control Officer",
    "Traffic Analyst",
    "Law Enforcement / Authorized Officer",
]
_INC_WRITE_ROLES = [
    "System Administrator",
    "Traffic Control Officer",
]


class _IncidentPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=_INC_READ_ROLES).exists()
        return request.user.groups.filter(name__in=_INC_WRITE_ROLES).exists()


class IncidentListView(APIView):
    """
    GET  /api/v1/traffic/incidents/   List incidents (paginated, filtered)
    POST /api/v1/traffic/incidents/   Create a new incident
    """
    permission_classes = [_IncidentPermission]

    def get(self, request: Request) -> Response:
        qs = (
            TrafficIncident.objects
            .prefetch_related("segments")
            .select_related("intersection", "created_by")
            .order_by("-occurred_at")
        )
        if st := request.query_params.get("state"):
            qs = qs.filter(state=st)
        if it := request.query_params.get("incident_type"):
            qs = qs.filter(incident_type=it)
        if int_id := request.query_params.get("intersection"):
            qs = qs.filter(intersection_id=int_id)
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if after := request.query_params.get("occurred_after"):
            qs = qs.filter(occurred_at__gte=after)
        if before := request.query_params.get("occurred_before"):
            qs = qs.filter(occurred_at__lte=before)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TrafficIncidentSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = TrafficIncidentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        incident = TrafficIncidentService.create(
            actor=request.user,
            title=ser.validated_data["title"],
            description=ser.validated_data["description"],
            incident_type=ser.validated_data.get("incident_type", "other"),
            occurred_at=ser.validated_data["occurred_at"],
            intersection=ser.validated_data.get("intersection"),
            segment_ids=ser.validated_data.get("segment_ids", []),
            request=request,
        )
        incident = TrafficIncident.objects.prefetch_related("segments").select_related(
            "intersection", "created_by"
        ).get(pk=incident.pk)
        return created_response(
            data=TrafficIncidentSerializer(incident).data,
            message="Traffic incident created successfully.",
        )


class IncidentDetailView(APIView):
    """
    GET   /api/v1/traffic/incidents/{id}/   Retrieve
    PATCH /api/v1/traffic/incidents/{id}/   Update (Admin, TCO)
    """
    permission_classes = [_IncidentPermission]

    def _get(self, incident_id: int) -> TrafficIncident:
        from django.shortcuts import get_object_or_404
        return get_object_or_404(
            TrafficIncident.objects.prefetch_related("segments").select_related(
                "intersection", "created_by"
            ),
            pk=incident_id,
        )

    def get(self, request: Request, incident_id: int) -> Response:
        return success_response(data=TrafficIncidentSerializer(self._get(incident_id)).data)

    def patch(self, request: Request, incident_id: int) -> Response:
        incident = self._get(incident_id)
        ser = TrafficIncidentWriteSerializer(incident, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        segment_ids = fields.pop("segment_ids", None)
        incident = TrafficIncidentService.update(
            actor=request.user, incident=incident,
            request=request, segment_ids=segment_ids, **fields,
        )
        incident = TrafficIncident.objects.prefetch_related("segments").select_related(
            "intersection", "created_by"
        ).get(pk=incident.pk)
        return success_response(
            data=TrafficIncidentSerializer(incident).data,
            message="Traffic incident updated successfully.",
        )


class IncidentStateView(APIView):
    """
    PATCH /api/v1/traffic/incidents/{id}/state/   Lifecycle transition (Admin, TCO)

    Request body: { "state": "<new_state>" }
    """
    permission_classes = [_IncidentPermission]

    def patch(self, request: Request, incident_id: int) -> Response:
        from django.shortcuts import get_object_or_404
        incident = get_object_or_404(TrafficIncident, pk=incident_id)
        ser = TrafficIncidentStateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        new_state = ser.validated_data["state"]
        try:
            incident = TrafficIncidentService.transition_state(
                actor=request.user, incident=incident, new_state=new_state, request=request
            )
        except InvalidStateTransitionError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        incident = TrafficIncident.objects.prefetch_related("segments").select_related(
            "intersection", "created_by"
        ).get(pk=incident.pk)
        return success_response(
            data=TrafficIncidentSerializer(incident).data,
            message=f"Incident state changed to '{new_state}'.",
        )


class IncidentStatusView(APIView):
    """
    PATCH /api/v1/traffic/incidents/{id}/status/   Activate/deactivate (Admin, TCO)
    """
    permission_classes = [_IncidentPermission]

    def patch(self, request: Request, incident_id: int) -> Response:
        from django.shortcuts import get_object_or_404
        incident = get_object_or_404(TrafficIncident, pk=incident_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        incident = TrafficIncidentService.set_active(
            actor=request.user, incident=incident, is_active=is_active, request=request
        )
        action = "activated" if is_active else "deactivated"
        incident = TrafficIncident.objects.prefetch_related("segments").select_related(
            "intersection", "created_by"
        ).get(pk=incident.pk)
        return success_response(
            data=TrafficIncidentSerializer(incident).data,
            message=f"Traffic incident {action}.",
        )
