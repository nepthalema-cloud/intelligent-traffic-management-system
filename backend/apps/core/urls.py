from django.urls import path
from .views.health import health_check
from .views.system import SystemStatusView, CameraStreamView

app_name = "core"

urlpatterns = [
    path("health/",                          health_check,                    name="health_check"),
    path("system/status/",                   SystemStatusView.as_view(),      name="system-status"),
    path("cameras/<int:camera_id>/stream/",  CameraStreamView.as_view(),      name="camera-stream"),
]
