"""
Core views — Phase 5 additions.

GET /api/v1/health/              Health check (already wired)
GET /api/v1/system/status/       System mode, camera state, AI state
GET /api/v1/cameras/{id}/stream/ Returns safe HLS URL for browser playback
"""

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.responses import success_response


class HealthView(APIView):
    permission_classes = []  # Public

    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "service": "traffic-management-backend"})


class SystemStatusView(APIView):
    """
    GET /api/v1/system/status/

    Returns honest system state so the frontend can display the correct status badge.

    mode:
      "live"     — ≥1 camera connected AND AI processing has produced a measurement
                   in the last 5 minutes
      "degraded" — cameras present but AI has not produced measurements recently
      "demo"     — no live cameras; all data is seeded/demo
      "offline"  — backend has no cameras configured

    Never returns "live" unless real camera+AI data is flowing.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.cameras.models import Camera, CameraHealth, ConnectivityStatus
        from apps.traffic.models import TrafficMeasurement

        now = timezone.now()
        five_min_ago = now - timedelta(minutes=5)

        total_cameras   = Camera.objects.filter(is_active=True).count()
        cameras_connected = (
            CameraHealth.objects
            .filter(connectivity_status=ConnectivityStatus.CONNECTED)
            .count()
        )

        # Has the AI service produced any measurements in the last 5 minutes?
        recent_ai = TrafficMeasurement.objects.filter(
            data_source="ai",
            measured_at__gte=five_min_ago,
        ).order_by("-measured_at").first()

        # Most recent measurement of any source
        last_measurement = (
            TrafficMeasurement.objects.order_by("-measured_at").first()
        )

        ai_active = recent_ai is not None

        if total_cameras == 0:
            mode = "offline"
        elif ai_active and cameras_connected > 0:
            mode = "live"
        elif cameras_connected > 0:
            mode = "degraded"
        else:
            mode = "demo"

        return success_response(data={
            "mode":                mode,
            "cameras_total":       total_cameras,
            "cameras_connected":   cameras_connected,
            "ai_processing_active": ai_active,
            "last_measurement_at": last_measurement.measured_at.isoformat() if last_measurement else None,
            "last_measurement_source": last_measurement.data_source if last_measurement else None,
            "server_time":         now.isoformat(),
        })


class CameraStreamView(APIView):
    """
    GET /api/v1/cameras/{camera_id}/stream/

    Returns the safe HLS URL for browser playback.
    NEVER returns the RTSP URL or credentials.

    The HLS URL points to the MediaMTX gateway:
      http://localhost:8888/{hls_path}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, camera_id: int) -> Response:
        from apps.cameras.models import Camera
        from django.shortcuts import get_object_or_404

        camera = get_object_or_404(Camera, pk=camera_id, is_active=True)

        if not camera.hls_path:
            return success_response(data={
                "camera_id":   camera.pk,
                "camera_name": camera.name,
                "available":   False,
                "hls_url":     None,
                "reason":      "No HLS stream configured for this camera.",
            })

        mediamtx_url = getattr(settings, "MEDIAMTX_URL", "http://localhost:8888")
        hls_url = f"{mediamtx_url}{camera.hls_path}"

        return success_response(data={
            "camera_id":   camera.pk,
            "camera_name": camera.name,
            "available":   True,
            "hls_url":     hls_url,
            "is_test_source": camera.description.lower().startswith("test") if camera.description else False,
        })
