from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.organizations.models import City, Region, TrafficControlCenter
from apps.organizations.serializers import (
    CitySerializer,
    CityWriteSerializer,
    RegionSerializer,
    RegionWriteSerializer,
    TrafficControlCenterSerializer,
    TrafficControlCenterWriteSerializer,
)


def _user_scope_allowed_ids(user):
    """Return allowed ids for region/city/control_center based on the user's UserScope.

    Returns a tuple of three sets: (region_ids, city_ids, center_ids).
    None for a set means no restriction (superuser or admin).
    """
    if getattr(user, "is_superuser", False):
        return None, None, None
    try:
        if user.groups.filter(name="System Administrator").exists():
            return None, None, None
    except Exception:
        pass

    scope = getattr(user, "scope_assignment", None)
    if not scope:
        return None, None, None

    region_ids = set()
    city_ids = set()
    center_ids = set()

    if getattr(scope, "region_id", None):
        region_ids.add(scope.region_id)
    if getattr(scope, "city_id", None):
        city_ids.add(scope.city_id)
        try:
            if scope.city and getattr(scope.city, "region_id", None):
                region_ids.add(scope.city.region_id)
        except Exception:
            pass
    if getattr(scope, "control_center_id", None):
        center_ids.add(scope.control_center_id)
        try:
            cc = scope.control_center
            if cc:
                if getattr(cc, "city_id", None):
                    city_ids.add(cc.city_id)
                if getattr(cc, "region_id", None):
                    region_ids.add(cc.region_id)
                else:
                    if getattr(cc, "city", None) and getattr(cc.city, "region_id", None):
                        region_ids.add(cc.city.region_id)
        except Exception:
            pass

    return (region_ids or set()), (city_ids or set()), (center_ids or set())


class _RegionalAccessPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name__in=["System Administrator", "Traffic Control Officer", "Traffic Analyst"]).exists()


class RegionListView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request):
        qs = Region.objects.all().order_by("name")
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if region_ids is not None:
            qs = qs.filter(id__in=region_ids)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(RegionSerializer(page, many=True).data)

    def post(self, request):
        ser = RegionWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        region = ser.save()
        return created_response(data=RegionSerializer(region).data, message="Region created successfully.")


class RegionDetailView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request, region_id):
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if region_ids is not None:
            region = get_object_or_404(Region.objects.filter(id__in=region_ids), pk=region_id)
        else:
            region = get_object_or_404(Region, pk=region_id)
        return success_response(data=RegionSerializer(region).data)


class CityListView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request):
        qs = City.objects.select_related("region").all().order_by("name")
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
        if city_ids is not None and city_ids:
            qs = qs.filter(id__in=city_ids)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(CitySerializer(page, many=True).data)

    def post(self, request):
        ser = CityWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        city = ser.save()
        return created_response(data=CitySerializer(city).data, message="City created successfully.")


class CityDetailView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request, city_id):
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if city_ids is not None:
            city = get_object_or_404(City.objects.select_related("region").filter(id__in=city_ids), pk=city_id)
        elif region_ids is not None:
            city = get_object_or_404(City.objects.select_related("region").filter(region_id__in=region_ids), pk=city_id)
        else:
            city = get_object_or_404(City.objects.select_related("region"), pk=city_id)
        return success_response(data=CitySerializer(city).data)


class TrafficControlCenterListView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request):
        qs = TrafficControlCenter.objects.select_related("region", "city").all().order_by("name")
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
        if city_ids is not None and city_ids:
            qs = qs.filter(city_id__in=city_ids)
        if center_ids is not None and center_ids:
            qs = qs.filter(id__in=center_ids)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TrafficControlCenterSerializer(page, many=True).data)

    def post(self, request):
        ser = TrafficControlCenterWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        center = ser.save()
        return created_response(data=TrafficControlCenterSerializer(center).data, message="Traffic control center created successfully.")


class TrafficControlCenterDetailView(APIView):
    permission_classes = [_RegionalAccessPermission]

    def get(self, request, center_id):
        region_ids, city_ids, center_ids = _user_scope_allowed_ids(request.user)
        if center_ids is not None:
            center = get_object_or_404(TrafficControlCenter.objects.select_related("region", "city").filter(id__in=center_ids), pk=center_id)
        elif city_ids is not None:
            center = get_object_or_404(TrafficControlCenter.objects.select_related("region", "city").filter(city_id__in=city_ids), pk=center_id)
        elif region_ids is not None:
            center = get_object_or_404(TrafficControlCenter.objects.select_related("region", "city").filter(region_id__in=region_ids), pk=center_id)
        else:
            center = get_object_or_404(TrafficControlCenter.objects.select_related("region", "city"), pk=center_id)
        return success_response(data=TrafficControlCenterSerializer(center).data)
