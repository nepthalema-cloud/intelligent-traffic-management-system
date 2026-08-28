"""
Camera health worker — Phase 5.

Runs as a background thread inside the Daphne/Django process.
Bypasses the Celery 5.6/Python 3.14 fast_trace_task compatibility issue
by calling the probe logic directly in a daemon thread every 60 seconds.

This is the production-resilient fallback for camera health monitoring
until the Celery/Python 3.14 incompatibility is resolved.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

_INTERVAL = 60  # seconds
_thread: threading.Thread | None = None


def _probe_loop():
    """Probe camera connectivity every INTERVAL seconds indefinitely."""
    logger.info("Camera health worker started (interval=%ds)", _INTERVAL)
    while True:
        try:
            _run_probe()
        except Exception as exc:
            logger.error("Camera health probe failed: %s", exc, exc_info=True)
        time.sleep(_INTERVAL)


def _run_probe():
    """Run the actual connectivity probe (same logic as cameras.tasks)."""
    import socket
    from django.utils import timezone
    from apps.cameras.models import Camera, CameraHealth, HealthStatus, ConnectivityStatus
    from apps.core.push import push_camera_health

    cameras = list(Camera.objects.filter(is_active=True))
    for camera in cameras:
        # TCP probe
        host = None
        port = 554
        url = camera.stream_url or ""
        try:
            if "://" in url:
                rest = url.split("://", 1)[1]
                if "@" in rest:
                    rest = rest.split("@", 1)[1]
                hp = rest.split("/")[0]
                if ":" in hp:
                    host, port_s = hp.rsplit(":", 1)
                    port = int(port_s)
                else:
                    host = hp
        except Exception:
            pass

        if not host:
            host = str(camera.ip_address) if camera.ip_address else ""

        if host:
            if host.lower() == "localhost":
                host = "127.0.0.1"
            try:
                with socket.create_connection((host, port), timeout=3):
                    hs, cs = HealthStatus.HEALTHY, ConnectivityStatus.CONNECTED
            except (socket.timeout, ConnectionRefusedError, OSError):
                hs, cs = HealthStatus.OFFLINE, ConnectivityStatus.DISCONNECTED
        else:
            hs, cs = HealthStatus.UNKNOWN, ConnectivityStatus.UNKNOWN

        now = timezone.now()
        CameraHealth.objects.update_or_create(
            camera=camera,
            defaults={
                "health_status":       hs,
                "connectivity_status": cs,
                "last_seen":           now if cs == ConnectivityStatus.CONNECTED else None,
                "checked_at":          now,
            },
        )
        push_camera_health({
            "camera_id":           camera.pk,
            "camera_name":         camera.name,
            "health_status":       hs,
            "connectivity_status": cs,
            "checked_at":          now.isoformat(),
        })


def start():
    """Start the background health probe thread. Idempotent."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_probe_loop, daemon=True, name="CameraHealthWorker")
    _thread.start()
    logger.info("Camera health worker thread started.")
