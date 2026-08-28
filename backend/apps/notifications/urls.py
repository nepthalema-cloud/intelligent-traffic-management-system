from django.urls import path

from apps.notifications.views import (
    NotificationDetailView,
    NotificationListView,
    NotificationTemplateDetailView,
    NotificationTemplateListView,
)

app_name = "notifications"

urlpatterns = [
    path("templates/", NotificationTemplateListView.as_view(), name="notification-template-list"),
    path("templates/<int:template_id>/", NotificationTemplateDetailView.as_view(), name="notification-template-detail"),
    path("", NotificationListView.as_view(), name="notification-list"),
    path("<int:notification_id>/", NotificationDetailView.as_view(), name="notification-detail"),
]
