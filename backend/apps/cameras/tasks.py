"""
Celery tasks for camera health monitoring — Phase 5.

check_camera_connectivity:
  Probes each active camera via TCP socket to ip_address:port.
  Updates CameraHealth and pushes WebSocket event.
  Runs every 60 seconds per real-time-architecture.md recommendation.
"""

import logging
import socket
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_RTSP_PORT = 554
TCP_TIMEOUT_S     = 3


def _probe_camera(camera) -> tuple[str, str]:
    """
    Attempt a TCP connection to camera.ip_address on the RTSP port.
    Returns (health_status, connectivity_status).
    """
    from apps.cameras.models import HealthStatus, ConnectivityStatus

    if not camera.ip_address:
        return HealthStatus.UNKNOWN, ConnectivityStatus.UNKNOWN

    # Parse port from stream_url if present, otherwise default 554
    port = DEFAULT_RTSP_PORT
    url = camera.stream_url or ""
    if "://" in url:
        try:
            rest = url.split("://", 1)[1]
            # strip credentials if present
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            host_port = rest.split("/")[0]
            if ":" in host_port:
                port = int(host_port.split(":")[1])
        except (ValueError, IndexError):
            pass

    try:
        with socket.create_connection((str(camera.ip_address), port), timeout=TCP_TIMEOUT_S):
            return HealthStatus.HEALTHY, ConnectivityStatus.CONNECTED
    except (socket.timeout, ConnectionRefusedError, OSError):
        return HealthStatus.OFFLINE, ConnectivityStatus.DISCONNECTED


@shared_task(name="apps.cameras.tasks.check_camera_connectivity", bind=True, max_retries=0)
def check_camera_connectivity(self):
    """
    Probe all active cameras and update CameraHealth records.
    Runs every 60 seconds via CELERY_BEAT_SCHEDULE.
    """
    from apps.cameras.models import Camera, CameraHealth, HealthStatus, ConnectivityStatus
    from apps.core.push import push_camera_health

    cameras = list(Camera.objects.filter(is_active=True).select_related("health"))
    updated = 0

    for camera in cameras:
        health_status, connectivity_status = _probe_camera(camera)
        now = timezone.now()

        health, _ = CameraHealth.objects.update_or_create(
            camera=camera,
            defaults={
                "health_status":       health_status,
                "connectivity_status": connectivity_status,
                "last_seen":           now if connectivity_status == ConnectivityStatus.CONNECTED else None,
                "checked_at":          now,
            },
        )

        # Push update to WebSocket clients
        push_camera_health({
            "camera_id":           camera.pk,
            "camera_name":         camera.name,
            "health_status":       health_status,
            "connectivity_status": connectivity_status,
            "checked_at":          now.isoformat(),
        })
        updated += 1

    logger.info("camera_health_check: probed %d cameras", updated)
    return {"probed": updated}
