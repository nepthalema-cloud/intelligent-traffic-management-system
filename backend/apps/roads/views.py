"""
Views for the roads app.

Endpoints
---------
GET    /api/v1/roads/                       List roads (paginated)
POST   /api/v1/roads/                       Create road (admin only)
GET    /api/v1/roads/{id}/                  Road detail
PATCH  /api/v1/roads/{id}/                  Update road (admin only)
PATCH  /api/v1/roads/{id}/status/           Activate/deactivate road (admin only)

GET    /api/v1/roads/intersections/         List intersections (paginated)
POST   /api/v1/roads/intersections/         Create intersection (admin only)
GET    /api/v1/roads/intersections/{id}/    Intersection detail
PATCH  /api/v1/roads/intersections/{id}/    Update intersection (admin only)
PATCH  /api/v1/roads/intersections/{id}/status/  Activate/deactivate

GET    /api/v1/roads/segments/              List segments (paginated)
POST   /api/v1/roads/segments/              Create segment (admin only)
GET    /api/v1/roads/segments/{id}/         Segment detail
PATCH  /api/v1/roads/segments/{id}/         Update segment (admin only)
PATCH  /api/v1/roads/segments/{id}/status/  Activate/deactivate

GET    /api/v1/roads/lanes/                 List lanes (paginated)
POST   /api/v1/roads/lanes/                 Create lane (admin only)
GET    /api/v1/roads/lanes/{id}/            Lane detail
PATCH  /api/v1/roads/lanes/{id}/            Update lane (admin only)
PATCH  /api/v1/roads/lanes/{id}/status/     Activate/deactivate

RBAC
----
- System Administrator: full CRUD + activate/deactivate
- Traffic Control Officer: read-only
- Traffic Analyst: read-only
- All other roles: no access
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin, IsTrafficAnalyst, IsTrafficControlOfficer
from apps.common.pagination import StandardResultsPagination
from apps.common.responses import (
    created_response,
    error_response,
    success_response,
)
from apps.roads.models import Intersection, Lane, Road, RoadSegment
from apps.roads.serializers import (
    IntersectionSerializer,
    IntersectionWriteSerializer,
    LaneSerializer,
    LaneWriteSerializer,
    RoadSegmentSerializer,
    RoadSegmentWriteSerializer,
    RoadSerializer,
    RoadWriteSerializer,
)
from apps.roads.services import (
    DuplicateRoadNameError,
    InvalidLaneNumberError,
    RoadService,
)


class _ReadOrAdminPermission(IsAuthenticated):
    """
    Combined permission:
    - GET/HEAD/OPTIONS → IsAuthenticated + (IsSystemAdmin OR IsTrafficControlOfficer OR IsTrafficAnalyst)
    - Write methods → IsAuthenticated + IsSystemAdmin

    Implemented as a single class to keep view code clean.
    """

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            # Read access: Admin, TCO, Analyst
            return (
                request.user.groups.filter(
                    name__in=[
                        "System Administrator",
                        "Traffic Control Officer",
                        "Traffic Analyst",
                    ]
                ).exists()
            )
        # Write access: Admin only
        return request.user.groups.filter(name="System Administrator").exists()


# ---------------------------------------------------------------------------
# Road views
# ---------------------------------------------------------------------------

class RoadListView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def get(self, request: Request) -> Response:
        qs = Road.objects.order_by("name")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(RoadSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        if not (request.user.is_superuser or
                request.user.groups.filter(name="System Administrator").exists()):
            return error_response("Only System Administrators may create roads.",
                                  status_code=status.HTTP_403_FORBIDDEN)
        ser = RoadWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            road = RoadService.create_road(
                actor=request.user,
                name=ser.validated_data["name"],
                road_type=ser.validated_data.get("road_type", "other"),
                description=ser.validated_data.get("description", ""),
                request=request,
            )
        except DuplicateRoadNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        return created_response(data=RoadSerializer(road).data,
                                message="Road created successfully.")


class RoadDetailView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def _get_road(self, road_id: int):
        return get_object_or_404(Road, pk=road_id)

    def get(self, request: Request, road_id: int) -> Response:
        return success_response(data=RoadSerializer(self._get_road(road_id)).data)

    def patch(self, request: Request, road_id: int) -> Response:
        road = self._get_road(road_id)
        ser = RoadWriteSerializer(road, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            road = RoadService.update_road(
                actor=request.user, road=road, request=request,
                **ser.validated_data,
            )
        except DuplicateRoadNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        return success_response(data=RoadSerializer(road).data,
                                message="Road updated successfully.")


class RoadStatusView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def patch(self, request: Request, road_id: int) -> Response:
        road = get_object_or_404(Road, pk=road_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        road = RoadService.set_road_active(
            actor=request.user, road=road, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(data=RoadSerializer(road).data,
                                message=f"Road '{road.name}' {action}.")


# ---------------------------------------------------------------------------
# Intersection views
# ---------------------------------------------------------------------------

class IntersectionListView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def get(self, request: Request) -> Response:
        qs = Intersection.objects.order_by("name")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(IntersectionSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = IntersectionWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        intersection = RoadService.create_intersection(
            actor=request.user, request=request,
            **ser.validated_data,
        )
        return created_response(data=IntersectionSerializer(intersection).data,
                                message="Intersection created successfully.")


class IntersectionDetailView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def _get(self, pk: int):
        return get_object_or_404(Intersection, pk=pk)

    def get(self, request: Request, intersection_id: int) -> Response:
        return success_response(data=IntersectionSerializer(self._get(intersection_id)).data)

    def patch(self, request: Request, intersection_id: int) -> Response:
        obj = self._get(intersection_id)
        ser = IntersectionWriteSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        obj = RoadService.update_intersection(
            actor=request.user, intersection=obj, request=request, **ser.validated_data,
        )
        return success_response(data=IntersectionSerializer(obj).data,
                                message="Intersection updated successfully.")


class IntersectionStatusView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def patch(self, request: Request, intersection_id: int) -> Response:
        obj = get_object_or_404(Intersection, pk=intersection_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        obj = RoadService.set_intersection_active(
            actor=request.user, intersection=obj, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(data=IntersectionSerializer(obj).data,
                                message=f"Intersection '{obj.name}' {action}.")


# ---------------------------------------------------------------------------
# RoadSegment views
# ---------------------------------------------------------------------------

class SegmentListView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def get(self, request: Request) -> Response:
        qs = RoadSegment.objects.select_related(
            "road", "start_intersection", "end_intersection"
        ).order_by("road", "id")
        road_id = request.query_params.get("road")
        if road_id:
            qs = qs.filter(road_id=road_id)
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(RoadSegmentSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = RoadSegmentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        road = ser.validated_data.pop("road")
        segment = RoadService.create_segment(
            actor=request.user, road=road, request=request, **ser.validated_data,
        )
        segment = RoadSegment.objects.select_related(
            "road", "start_intersection", "end_intersection"
        ).get(pk=segment.pk)
        return created_response(data=RoadSegmentSerializer(segment).data,
                                message="Road segment created successfully.")


class SegmentDetailView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def _get(self, pk: int):
        return get_object_or_404(
            RoadSegment.objects.select_related(
                "road", "start_intersection", "end_intersection"
            ),
            pk=pk,
        )

    def get(self, request: Request, segment_id: int) -> Response:
        return success_response(data=RoadSegmentSerializer(self._get(segment_id)).data)

    def patch(self, request: Request, segment_id: int) -> Response:
        obj = self._get(segment_id)
        ser = RoadSegmentWriteSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        fields.pop("road", None)  # road cannot be changed after creation
        obj = RoadService.update_segment(
            actor=request.user, segment=obj, request=request, **fields,
        )
        obj = RoadSegment.objects.select_related(
            "road", "start_intersection", "end_intersection"
        ).get(pk=obj.pk)
        return success_response(data=RoadSegmentSerializer(obj).data,
                                message="Road segment updated successfully.")


class SegmentStatusView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def patch(self, request: Request, segment_id: int) -> Response:
        obj = get_object_or_404(RoadSegment, pk=segment_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        obj = RoadService.set_segment_active(
            actor=request.user, segment=obj, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(data=RoadSegmentSerializer(
            RoadSegment.objects.select_related("road").get(pk=obj.pk)
        ).data, message=f"Segment {action}.")


# ---------------------------------------------------------------------------
# Lane views
# ---------------------------------------------------------------------------

class LaneListView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def get(self, request: Request) -> Response:
        qs = Lane.objects.select_related("segment__road").order_by("segment", "lane_number")
        segment_id = request.query_params.get("segment")
        if segment_id:
            qs = qs.filter(segment_id=segment_id)
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(LaneSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = LaneWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            lane = RoadService.create_lane(
                actor=request.user,
                segment=ser.validated_data["segment"],
                lane_number=ser.validated_data["lane_number"],
                lane_type=ser.validated_data.get("lane_type", "travel"),
                description=ser.validated_data.get("description", ""),
                request=request,
            )
        except InvalidLaneNumberError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        lane = Lane.objects.select_related("segment__road").get(pk=lane.pk)
        return created_response(data=LaneSerializer(lane).data,
                                message="Lane created successfully.")


class LaneDetailView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def _get(self, pk: int):
        return get_object_or_404(
            Lane.objects.select_related("segment__road"), pk=pk
        )

    def get(self, request: Request, lane_id: int) -> Response:
        return success_response(data=LaneSerializer(self._get(lane_id)).data)

    def patch(self, request: Request, lane_id: int) -> Response:
        obj = self._get(lane_id)
        ser = LaneWriteSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        fields.pop("segment", None)  # segment cannot be changed after creation
        obj = RoadService.update_lane(
            actor=request.user, lane=obj, request=request, **fields,
        )
        obj = Lane.objects.select_related("segment__road").get(pk=obj.pk)
        return success_response(data=LaneSerializer(obj).data,
                                message="Lane updated successfully.")


class LaneStatusView(APIView):
    permission_classes = [_ReadOrAdminPermission]

    def patch(self, request: Request, lane_id: int) -> Response:
        obj = get_object_or_404(Lane, pk=lane_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        obj = RoadService.set_lane_active(
            actor=request.user, lane=obj, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(data=LaneSerializer(
            Lane.objects.select_related("segment__road").get(pk=obj.pk)
        ).data, message=f"Lane {action}.")
