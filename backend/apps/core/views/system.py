"""
System status and camera stream views — Phase 5.

GET /api/v1/system/status/          Honest per-camera + aggregate system mode
GET /api/v1/cameras/{id}/stream/    Safe HLS URL (no RTSP credentials)
"""

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.responses import success_response


def _build_hls_url(request: Request, hls_path: str) -> str:
    """
    Build the HLS URL that is reachable from the requesting browser.

    In development the MediaMTX HLS port (8888) runs on the same host as
    the Django backend (8000).  We derive the hostname from the incoming
    HTTP request so that:

    - Same machine:  http://localhost:8888/<path>   ✓
    - LAN remote PC: http://192.168.x.x:8888/<path> ✓ (works for both)
    - Docker env:    falls back to MEDIAMTX_URL setting

    The MEDIAMTX_HLS_PORT setting (default 8888) can be overridden in
    development.py when MediaMTX runs on a different port or machine.
    """
    # Browser-facing HLS URL override for environments where MediaMTX is
    # reachable on a different public hostname than the backend container.
    browser_url = getattr(settings, "MEDIAMTX_BROWSER_URL", None)
    if browser_url:
        return f"{browser_url}{hls_path}"

    # Derive host from the incoming request so remote browsers on the LAN
    # can connect to the same host that requested the page.
    hls_port = getattr(settings, "MEDIAMTX_HLS_PORT", 8888)
    host = request.get_host().split(":")[0]   # strip Django port
    scheme = request.scheme or "http"
    return f"{scheme}://{host}:{hls_port}{hls_path}"


class SystemStatusView(APIView):
    """
    GET /api/v1/system/status/

    Returns honest, per-camera system state. Never fabricates Live status.

    Aggregate mode:
      "live"     — ≥1 camera: connected + HLS + AI measurement in last 5 min
      "degraded" — cameras exist but partial failure (some offline/AI stopped)
      "demo"     — no live cameras; data is seeded/demo only
      "offline"  — no cameras configured at all

    Per-camera entries show individual state for granular dashboard display.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.cameras.models import Camera, CameraHealth, ConnectivityStatus
        from apps.traffic.models import TrafficMeasurement

        now = timezone.now()
        five_min_ago = now - timedelta(minutes=5)

        cameras = list(
            Camera.objects.filter(is_active=True)
            .select_related("health")
            .order_by("name")
        )

        # Per-camera AI activity
        ai_recent = set(
            TrafficMeasurement.objects
            .filter(data_source='ai', measured_at__gte=five_min_ago)
            .values_list('camera_id', flat=True)
            .distinct()
        )

        per_camera = []
        total_connected = 0
        total_live      = 0

        for cam in cameras:
            health = getattr(cam, 'health', None)
            conn   = getattr(health, 'connectivity_status', 'unknown') if health else 'unknown'
            hs     = getattr(health, 'health_status',       'unknown') if health else 'unknown'
            ls     = getattr(health, 'last_seen',           None)      if health else None

            is_connected = (conn == ConnectivityStatus.CONNECTED)
            has_ai       = cam.pk in ai_recent
            has_hls      = bool(cam.hls_path)

            if is_connected:
                total_connected += 1

            # Determine this camera's individual mode
            desc = cam.description or ""
            if desc.startswith("TEST") or 'test-camera' in cam.stream_url:
                source_type = "test_video"
            elif desc.startswith("LIVE-WEBCAM") or "live-webcam" in cam.stream_url:
                source_type = "live_webcam"
            else:
                source_type = "cctv"

            if is_connected and has_hls and has_ai:
                cam_mode = "live"
                total_live += 1
            elif is_connected and has_hls:
                cam_mode = "hls_available"
            elif is_connected:
                cam_mode = "stream_connected"
            elif cam.stream_url:
                cam_mode = "offline"
            else:
                cam_mode = "saved"

            per_camera.append({
                "camera_id":           cam.pk,
                "camera_name":         cam.name,
                "mode":                cam_mode,
                "source_type":         source_type,
                "health_status":       hs,
                "connectivity_status": conn,
                "ai_processing_active":has_ai,
                "hls_available":       has_hls,
                "last_seen":           ls.isoformat() if ls else None,
            })

        total_cameras = len(cameras)

        # Last measurement overall
        last_meas = TrafficMeasurement.objects.order_by('-measured_at').first()

        # Aggregate mode
        if total_cameras == 0:
            mode = "offline"
        elif total_live > 0 and total_live == total_cameras:
            mode = "live"          # ALL cameras live
        elif total_live > 0:
            mode = "degraded"      # SOME cameras live, some not
        elif total_connected > 0:
            mode = "degraded"      # cameras connected but no AI
        else:
            mode = "demo"          # no live connectivity at all

        return success_response(data={
            "mode":                   mode,
            "cameras_total":          total_cameras,
            "cameras_connected":      total_connected,
            "cameras_live":           total_live,
            "ai_processing_active":   len(ai_recent) > 0,
            "cameras_with_ai":        len(ai_recent),
            "last_measurement_at":    last_meas.measured_at.isoformat() if last_meas else None,
            "last_measurement_source": last_meas.data_source if last_meas else None,
            "server_time":            now.isoformat(),
            "cameras":                per_camera,
        })


class CameraStreamView(APIView):
    """
    GET /api/v1/cameras/{camera_id}/stream/

    Returns the safe HLS URL for browser playback via MediaMTX.
    NEVER returns the RTSP URL or credentials.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, camera_id: int) -> Response:
        from apps.cameras.models import Camera
        from django.shortcuts import get_object_or_404

        camera = get_object_or_404(Camera, pk=camera_id, is_active=True)

        if not camera.hls_path:
            return success_response(data={
                "camera_id":     camera.pk,
                "camera_name":   camera.name,
                "available":     False,
                "hls_url":       None,
                "reason":        "No HLS stream configured for this camera.",
            })

        hls_url = _build_hls_url(request, camera.hls_path)

        desc = camera.description or ""
        if desc.startswith("LIVE-WEBCAM") or "live-webcam" in camera.stream_url:
            source_type  = "live_webcam"
            source_label = "LIVE WEBCAM"
        elif desc.startswith("TEST") or "test-camera" in camera.stream_url:
            source_type  = "test_video"
            source_label = "TEST SOURCE"
        else:
            source_type  = "cctv"
            source_label = "IP CAMERA"

        return success_response(data={
            "camera_id":      camera.pk,
            "camera_name":    camera.name,
            "available":      True,
            "hls_url":        hls_url,
            "source_type":    source_type,
            "source_label":   source_label,
            "is_test_source": source_type == "test_video",
        })
