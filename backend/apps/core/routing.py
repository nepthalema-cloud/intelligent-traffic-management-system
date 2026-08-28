"""WebSocket URL routing for the traffic management system."""

from django.urls import re_path
from apps.core import consumers
from apps.cameras.webcam_consumer import WebcamDetectionConsumer

websocket_urlpatterns = [
    re_path(r"^ws/dashboard/$",          consumers.DashboardConsumer.as_asgi()),
    re_path(r"^ws/cameras/$",            consumers.CameraConsumer.as_asgi()),
    re_path(r"^ws/webcam-detection/$",   WebcamDetectionConsumer.as_asgi()),
]
