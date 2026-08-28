from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import models

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.drivers.models import Driver
from apps.drivers.serializers import DriverSerializer, DriverWriteSerializer
from apps.violations.models import TrafficViolation


class _DriverPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=["System Administrator", "Law Enforcement / Authorized Officer", "Payment/Fines Officer"]).exists()
        return request.user.groups.filter(name__in=["System Administrator", "Law Enforcement / Authorized Officer"]).exists()


class DriverListView(APIView):
    permission_classes = [_DriverPermission]

    def get(self, request):
        qs = Driver.objects.all().order_by("last_name", "first_name")
        q = request.GET.get("q")
        license_number = request.GET.get("license_number")
        if license_number:
            qs = qs.filter(license_number__iexact=license_number)
        elif q:
            qs = qs.filter(
                models.Q(license_number__icontains=q) |
                models.Q(first_name__icontains=q) |
                models.Q(last_name__icontains=q) |
                models.Q(driver_identifier__icontains=q) |
                models.Q(email__icontains=q)
            )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(DriverSerializer(page, many=True).data)

    def post(self, request):
        ser = DriverWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        driver = ser.save()
        return created_response(data=DriverSerializer(driver).data, message="Driver created successfully.")


class DriverDetailView(APIView):
    permission_classes = [_DriverPermission]

    def get(self, request, driver_id):
        driver = get_object_or_404(Driver, pk=driver_id)
        return success_response(data=DriverSerializer(driver).data)

    def patch(self, request, driver_id):
        driver = get_object_or_404(Driver, pk=driver_id)
        ser = DriverWriteSerializer(driver, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        driver = ser.save()
        return success_response(data=DriverSerializer(driver).data, message="Driver updated successfully.")


class DriverViolationsView(APIView):
    permission_classes = [_DriverPermission]

    def get(self, request, driver_id):
        driver = get_object_or_404(Driver, pk=driver_id)
        qs = TrafficViolation.objects.filter(vehicle__driver=driver).order_by("-occurred_at")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response({"driver": driver_id, "violations": [
            {"id": v.id, "violation_type": v.violation_type, "occurred_at": v.occurred_at, "vehicle_id": v.vehicle_id}
            for v in page
        ]})
