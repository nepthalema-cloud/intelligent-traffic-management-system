from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.fines.models import Fine, Payment
from apps.fines.serializers import FineSerializer, FineWriteSerializer, PaymentSerializer, PaymentWriteSerializer


class _FinePermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=["System Administrator", "Traffic Control Officer", "Payment/Fines Officer", "Law Enforcement / Authorized Officer"]).exists()
        return request.user.groups.filter(name__in=["System Administrator", "Payment/Fines Officer"]).exists()


class FineListView(APIView):
    permission_classes = [_FinePermission]

    def get(self, request):
        qs = Fine.objects.select_related("violation").all().order_by("-issued_at")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(FineSerializer(page, many=True).data)

    def post(self, request):
        ser = FineWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        fine = ser.save()
        return created_response(data=FineSerializer(fine).data, message="Fine created successfully.")


class FineDetailView(APIView):
    permission_classes = [_FinePermission]

    def get(self, request, fine_id):
        fine = get_object_or_404(Fine.objects.select_related("violation"), pk=fine_id)
        return success_response(data=FineSerializer(fine).data)

    def patch(self, request, fine_id):
        fine = get_object_or_404(Fine.objects.select_related("violation"), pk=fine_id)
        ser = FineWriteSerializer(fine, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        fine = ser.save()
        return success_response(data=FineSerializer(fine).data, message="Fine updated successfully.")


class PaymentListView(APIView):
    permission_classes = [_FinePermission]

    def get(self, request):
        qs = Payment.objects.select_related("fine").all().order_by("-created_at")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(PaymentSerializer(page, many=True).data)

    def post(self, request):
        ser = PaymentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        payment = ser.save()
        return created_response(data=PaymentSerializer(payment).data, message="Payment created successfully.")


class PaymentDetailView(APIView):
    permission_classes = [_FinePermission]

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment.objects.select_related("fine"), pk=payment_id)
        return success_response(data=PaymentSerializer(payment).data)
