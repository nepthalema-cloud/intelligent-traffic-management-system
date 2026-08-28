from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.notifications.models import Notification, NotificationTemplate
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationTemplateSerializer,
    NotificationTemplateWriteSerializer,
    NotificationWriteSerializer,
)


class _NotificationPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name__in=["System Administrator", "Traffic Control Officer", "Traffic Analyst", "Law Enforcement / Authorized Officer", "Payment/Fines Officer"]).exists()


class NotificationTemplateListView(APIView):
    permission_classes = [_NotificationPermission]

    def get(self, request):
        qs = NotificationTemplate.objects.all().order_by("code")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(NotificationTemplateSerializer(page, many=True).data)

    def post(self, request):
        ser = NotificationTemplateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        template = ser.save()
        return created_response(data=NotificationTemplateSerializer(template).data, message="Notification template created successfully.")


class NotificationTemplateDetailView(APIView):
    permission_classes = [_NotificationPermission]

    def get(self, request, template_id):
        template = get_object_or_404(NotificationTemplate, pk=template_id)
        return success_response(data=NotificationTemplateSerializer(template).data)


class NotificationListView(APIView):
    permission_classes = [_NotificationPermission]

    def get(self, request):
        qs = Notification.objects.select_related("recipient").filter(recipient=request.user).order_by("-created_at")
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)

    def post(self, request):
        ser = NotificationWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors, status_code=status.HTTP_400_BAD_REQUEST)
        notification = ser.save()
        return created_response(data=NotificationSerializer(notification).data, message="Notification created successfully.")


class NotificationDetailView(APIView):
    permission_classes = [_NotificationPermission]

    def get(self, request, notification_id):
        notification = get_object_or_404(Notification.objects.select_related("recipient"), pk=notification_id)
        return success_response(data=NotificationSerializer(notification).data)

    def patch(self, request, notification_id):
        notification = get_object_or_404(Notification.objects.select_related("recipient"), pk=notification_id)
        if notification.recipient_id != request.user.id:
            return error_response("You can only update your own notifications.", status_code=status.HTTP_403_FORBIDDEN)
        notification.mark_as_read()
        return success_response(data=NotificationSerializer(notification).data, message="Notification marked as read.")
