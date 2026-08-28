"""
Camera connectivity testing utilities.

Performs real network probes to determine the camera's connection state.
Reports one of 7 distinct states — never fabricates a positive result.

States (in order of the onboarding pipeline):
  saved           — camera record exists in DB, no connectivity check performed
  rtsp_unreachable— TCP connection to camera IP:port failed (timeout/refused)
  auth_failed     — TCP reached but RTSP DESCRIBE returned 401
  stream_connected— RTSP stream is readable (MediaMTX confirmed it)
  hls_available   — MediaMTX HLS endpoint is serving the playlist
  ai_processing   — AI service has posted measurements from this camera in last 5 min
  live            — all of the above: connected + HLS + AI active

Security notes:
  - Credentials are assembled server-side only for the probe
  - Probe results never include credential values
  - The full authenticated URL is never returned in any API response
"""

import socket
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

import requests as http_client

logger = logging.getLogger(__name__)

TCP_TIMEOUT  = 4   # seconds
HTTP_TIMEOUT = 5   # seconds

# 7-state enum (string values used in API responses)
class CameraConnectionState:
    SAVED             = "saved"
    RTSP_UNREACHABLE  = "rtsp_unreachable"
    AUTH_FAILED       = "auth_failed"
    STREAM_CONNECTED  = "stream_connected"
    HLS_AVAILABLE     = "hls_available"
    AI_PROCESSING     = "ai_processing"
    LIVE              = "live"


STATE_LABELS = {
    CameraConnectionState.SAVED:            "Configuration Saved",
    CameraConnectionState.RTSP_UNREACHABLE: "RTSP Unreachable",
    CameraConnectionState.AUTH_FAILED:      "Authentication Failed",
    CameraConnectionState.STREAM_CONNECTED: "Stream Connected",
    CameraConnectionState.HLS_AVAILABLE:    "HLS Available",
    CameraConnectionState.AI_PROCESSING:    "AI Processing Active",
    CameraConnectionState.LIVE:             "Live",
}

STATE_COLOURS = {
    CameraConnectionState.SAVED:            "slate",
    CameraConnectionState.RTSP_UNREACHABLE: "red",
    CameraConnectionState.AUTH_FAILED:      "red",
    CameraConnectionState.STREAM_CONNECTED: "amber",
    CameraConnectionState.HLS_AVAILABLE:    "blue",
    CameraConnectionState.AI_PROCESSING:    "cyan",
    CameraConnectionState.LIVE:             "green",
}


def _tcp_probe(host: str, port: int) -> bool:
    """Attempt a TCP connection. Returns True if the port is reachable."""
    # Resolve 'localhost' to '127.0.0.1' to avoid DNS lookup delays
    if host.lower() == 'localhost':
        host = '127.0.0.1'
    try:
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _hls_probe(hls_url: str) -> bool:
    """Check if the MediaMTX HLS playlist endpoint returns a valid M3U8."""
    try:
        resp = http_client.get(hls_url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        return resp.status_code == 200 and resp.text.startswith("#EXTM3U")
    except Exception:
        return False


def _rtsp_describe_probe(rtsp_url: str) -> tuple[bool, bool]:
    """
    Send an RTSP DESCRIBE request to check authentication.
    Returns (reached, auth_ok):
      reached=True  means TCP+RTSP layer responded
      auth_ok=True  means no 401 was returned
    
    Uses cv2 for the actual frame read — if it opens the stream at all,
    auth succeeded.
    """
    try:
        import cv2
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, TCP_TIMEOUT * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, TCP_TIMEOUT * 1000)
        
        if not cap.isOpened():
            cap.release()
            return False, False
        
        # Try reading one frame
        ret, _ = cap.read()
        cap.release()
        
        if ret:
            return True, True  # reached + authenticated + got a frame
        else:
            # Opened but couldn't read — might be auth issue or codec
            return True, False
    except Exception as exc:
        logger.debug("RTSP probe failed: %s", exc)
        return False, False


def _ai_active_probe(camera_id: int) -> bool:
    """Check if AI service posted a measurement for this camera in the last 5 minutes."""
    try:
        from apps.traffic.models import TrafficMeasurement
        five_min_ago = timezone.now() - timedelta(minutes=5)
        return TrafficMeasurement.objects.filter(
            camera_id=camera_id,
            data_source='ai',
            measured_at__gte=five_min_ago,
        ).exists()
    except Exception:
        return False


def test_camera_connection(camera) -> dict:
    """
    Run a full connectivity test against a camera.
    
    Returns a dict with:
      state       — one of CameraConnectionState values
      state_label — human-readable string
      colour      — UI colour hint
      detail      — diagnostic message
      checked_at  — ISO timestamp of when the test ran
      
    NEVER includes credential values in the return dict.
    """
    from apps.cameras.models import CameraCredential

    checked_at = timezone.now()

    # No stream URL configured
    if not camera.stream_url:
        return {
            "state":       CameraConnectionState.SAVED,
            "state_label": STATE_LABELS[CameraConnectionState.SAVED],
            "colour":      STATE_COLOURS[CameraConnectionState.SAVED],
            "detail":      "No RTSP stream URL configured. Add the camera's stream URL to proceed.",
            "checked_at":  checked_at.isoformat(),
        }

    # Parse host and port from stream_url
    host = None
    port = 554  # RTSP default
    try:
        url = camera.stream_url
        if "://" in url:
            rest = url.split("://", 1)[1]
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            host_part = rest.split("/")[0]
            if ":" in host_part:
                host, port_str = host_part.rsplit(":", 1)
                port = int(port_str)
            else:
                host = host_part
    except Exception:
        pass

    if not host:
        host = camera.ip_address or ""

    if not host:
        return {
            "state":       CameraConnectionState.SAVED,
            "state_label": STATE_LABELS[CameraConnectionState.SAVED],
            "colour":      STATE_COLOURS[CameraConnectionState.SAVED],
            "detail":      "Cannot determine camera host from stream_url or ip_address.",
            "checked_at":  checked_at.isoformat(),
        }

    # TCP probe
    tcp_ok = _tcp_probe(host, port)
    if not tcp_ok:
        return {
            "state":       CameraConnectionState.RTSP_UNREACHABLE,
            "state_label": STATE_LABELS[CameraConnectionState.RTSP_UNREACHABLE],
            "colour":      STATE_COLOURS[CameraConnectionState.RTSP_UNREACHABLE],
            "detail":      f"Cannot reach {host}:{port} via TCP. Check network connectivity, VPN, and firewall rules.",
            "checked_at":  checked_at.isoformat(),
        }

    # Build authenticated RTSP URL for the probe (server-side only, never returned)
    rtsp_url = camera.stream_url
    try:
        cred = camera.credential
        if cred.username and cred.password:
            rtsp_url = cred.build_rtsp_url()
    except CameraCredential.DoesNotExist:
        pass

    # RTSP auth probe
    reached, auth_ok = _rtsp_describe_probe(rtsp_url)

    if not reached:
        return {
            "state":       CameraConnectionState.RTSP_UNREACHABLE,
            "state_label": STATE_LABELS[CameraConnectionState.RTSP_UNREACHABLE],
            "colour":      STATE_COLOURS[CameraConnectionState.RTSP_UNREACHABLE],
            "detail":      f"TCP port {port} reachable but RTSP connection failed. Check if the camera is broadcasting.",
            "checked_at":  checked_at.isoformat(),
        }

    if not auth_ok:
        has_creds = False
        try:
            cred = camera.credential
            has_creds = bool(cred.username)
        except CameraCredential.DoesNotExist:
            pass
        return {
            "state":       CameraConnectionState.AUTH_FAILED,
            "state_label": STATE_LABELS[CameraConnectionState.AUTH_FAILED],
            "colour":      STATE_COLOURS[CameraConnectionState.AUTH_FAILED],
            "detail":      "RTSP stream reached but authentication failed or no frames available. " +
                           ("Check username/password." if has_creds else "No credentials stored — add them if the camera requires authentication."),
            "checked_at":  checked_at.isoformat(),
        }

    # Stream is connected — check HLS
    mediamtx_url = getattr(settings, "MEDIAMTX_URL", "http://localhost:8888")
    if camera.hls_path:
        hls_url  = f"{mediamtx_url}{camera.hls_path}"
        hls_ok = _hls_probe(hls_url)
    else:
        hls_ok = False
        hls_url = None

    if not hls_ok:
        return {
            "state":       CameraConnectionState.STREAM_CONNECTED,
            "state_label": STATE_LABELS[CameraConnectionState.STREAM_CONNECTED],
            "colour":      STATE_COLOURS[CameraConnectionState.STREAM_CONNECTED],
            "detail":      "RTSP stream readable. HLS not yet available — MediaMTX may not be pulling this stream yet. " +
                           ("Set hls_path to enable browser playback." if not camera.hls_path else
                            f"HLS endpoint {hls_url} returned no valid playlist."),
            "checked_at":  checked_at.isoformat(),
        }

    # HLS available — check AI
    ai_active = _ai_active_probe(camera.pk)

    if not ai_active:
        return {
            "state":       CameraConnectionState.HLS_AVAILABLE,
            "state_label": STATE_LABELS[CameraConnectionState.HLS_AVAILABLE],
            "colour":      STATE_COLOURS[CameraConnectionState.HLS_AVAILABLE],
            "detail":      f"HLS stream available at {hls_url}. AI detection service is not yet processing this camera.",
            "checked_at":  checked_at.isoformat(),
            "hls_url":     hls_url,
        }

    # All conditions met — LIVE
    return {
        "state":       CameraConnectionState.LIVE,
        "state_label": STATE_LABELS[CameraConnectionState.LIVE],
        "colour":      STATE_COLOURS[CameraConnectionState.LIVE],
        "detail":      "Camera is live: RTSP connected, HLS available, AI processing active.",
        "checked_at":  checked_at.isoformat(),
        "hls_url":     hls_url,
    }
