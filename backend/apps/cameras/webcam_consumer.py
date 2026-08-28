"""
WebcamDetectionConsumer — Phase 5C

WS endpoint: ws/webcam-detection/

Accepts JPEG frames from the browser's getUserMedia() stream, runs YOLOv8
vehicle detection in an async thread pool, posts measurements to Django, and
broadcasts results back to the connecting browser AND to the dashboard
WebSocket group (so the live Dashboard also updates).

Frame protocol (JSON envelope):
  Browser → Server:
    { "type": "frame", "data": "<base64-JPEG>", "device_label": "..." }
    { "type": "start", "device_label": "..." }
    { "type": "stop" }

  Server → Browser:
    { "type": "session_started", "session_id": "<uuid>", "camera_id": <int> }
    { "type": "detection", "vehicle_count": <int>, "avg_speed_kmh": null,
      "measurement_id": <int>|null, "interval_seconds": <float> }
    { "type": "error", "message": "..." }
    { "type": "session_ended" }

Architecture:
  Browser (getUserMedia + canvas.toBlob) → WS → this consumer
    → asyncio.run_in_executor(YOLO) → measurement POST → WS push

Security:
  - JWT auth via existing JwtAuthMiddleware (same as dashboard WS)
  - Session token generated server-side; browser never supplies its own ID
  - No RTSP credentials, no camera IP addresses
  - device_label stored for display only, never used for auth

Multi-user:
  Each connection gets its own BrowserWebcamSession with a unique session_token.
  Multiple users can connect simultaneously — sessions don't share state.
"""

import asyncio
import base64
import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)

# Shared thread-pool for YOLO (CPU-bound); max 2 workers to avoid OOM
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yolo-webcam")

# Minimum seconds between measurement posts (avoid flooding)
MEASURE_INTERVAL = 10.0


from apps.cameras.detector_loader import get_vehicle_detector
from apps.cameras.pipeline import analyze_frame

# Module-level detector cache — constructed on first use
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        try:
            _detector = get_vehicle_detector(conf_threshold=0.4)
        except Exception:
            logger.exception('Failed to initialize VehicleDetector for webcam consumer')
            _detector = None
    return _detector


def _decode_jpeg(b64_data: str):
    """Decode base64 JPEG → numpy BGR array (for OpenCV/YOLO)."""
    try:
        # Strip optional data-URL prefix
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
        raw = base64.b64decode(b64_data)
        import cv2
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except Exception as exc:
        logger.debug("JPEG decode failed: %s", exc)
        return None


def _run_detection(b64_data: str) -> list:
    """Run YOLO detection on a single frame. Returns list of Detection objects."""
    det = _get_detector()
    if det is None:
        return []
    frame = _decode_jpeg(b64_data)
    if frame is None:
        return []
    try:
        return det.detect(frame)
    except Exception as exc:
        logger.debug("Detection error: %s", exc)
        return []


class WebcamDetectionConsumer(AsyncWebsocketConsumer):
    """
    One instance per browser WebSocket connection.
    Lifecycle: connect → [start] → [frame × N] → [stop | disconnect]
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self._user = user
        self._session = None
        self._window_start = None
        self._window_vehicles: set = set()
        self._active = False

        await self.accept()
        logger.info("WebcamDetection WS connected: user=%s", user.username)

    async def disconnect(self, close_code):
        await self._end_session()
        logger.info("WebcamDetection WS disconnected: user=%s code=%s",
                    getattr(self, "_user", "?"), close_code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            return

        mtype = msg.get("type", "")

        if mtype == "start":
            await self._handle_start(msg)
        elif mtype == "frame":
            if self._active:
                await self._handle_frame(msg)
        elif mtype == "stop":
            await self._end_session()
            await self.send(text_data=json.dumps({"type": "session_ended"}))

    # ── Message handlers ──────────────────────────────────────────────

    async def _handle_start(self, msg: dict):
        """Create a BrowserWebcamSession and confirm to the browser."""
        device_label = str(msg.get("device_label", ""))[:255]
        session = await self._create_session(device_label)
        if session is None:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Could not create webcam session.",
            }))
            return

        self._session = session
        self._window_start = time.monotonic()
        self._window_vehicles = set()
        self._active = True

        await self.send(text_data=json.dumps({
            "type":       "session_started",
            "session_id": str(session.session_token),
            "source_type": "browser_webcam",
            "label":      "LIVE WEBCAM — Browser Camera (TEST SOURCE, NOT CCTV)",
        }))
        logger.info("WebcamSession started: user=%s token=%s",
                    self._user.username, session.session_token)

    async def _handle_frame(self, msg: dict):
        """Offload YOLO to thread pool, collect detections, post measurement."""
        b64_data = msg.get("data", "")
        if not b64_data:
            return

        loop = asyncio.get_event_loop()
        # Use the shared detector via thread pool
        detections = await loop.run_in_executor(_EXECUTOR, _run_detection, b64_data)

        # Use shared pipeline analyze_frame to render overlays and generate events
        frame_time = time.monotonic()
        frame_state = getattr(self, '_frame_state', None) or {}
        # Decode frame synchronously here since analyze_frame expects numpy frame
        frame = _decode_jpeg(b64_data)
        if frame is None:
            return

        # meters_per_pixel is None for browser webcam (no calibration by default)
        frame_dets, per_frame_events, annotated_frame, frame_state = analyze_frame(
            detections, frame, frame_time, None, frame_state
        )
        self._frame_state = frame_state

        # Send live detection overlays and metadata back to browser
        try:
            # Encode annotated frame to JPEG base64
            import cv2, base64
            ret, jpeg = cv2.imencode('.jpg', annotated_frame)
            if ret:
                b64_out = base64.b64encode(jpeg.tobytes()).decode('ascii')
            else:
                b64_out = ''
        except Exception:
            b64_out = ''

        await self.send(text_data=json.dumps({
            "type": "frame_update",
            "frame": b64_out,
            "detections": frame_dets,
            "events": per_frame_events,
        }))

        # Accumulate unique track IDs for periodic measurements
        for d in frame_dets:
            try:
                tid = int(d.get('track_id', -1))
            except Exception:
                tid = -1
            if tid >= 0:
                self._window_vehicles.add(tid)

        now = time.monotonic()
        elapsed = now - (self._window_start or now)

        if elapsed >= MEASURE_INTERVAL:
            vehicle_count = len(self._window_vehicles)
            measurement_id = await self._post_measurement(vehicle_count, elapsed)

            # Reset window
            self._window_vehicles.clear()
            self._window_start = time.monotonic()

            # Send result to browser
            await self.send(text_data=json.dumps({
                "type":             "detection",
                "vehicle_count":    vehicle_count,
                "avg_speed_kmh":    None,   # no calibration for browser webcam
                "measurement_id":   measurement_id,
                "interval_seconds": round(elapsed, 1),
            }))

            # Also broadcast to the dashboard group so live Dashboard updates
            if measurement_id and vehicle_count > 0:
                await self.channel_layer.group_send(
                    "dashboard",
                    {
                        "type":    "measurement_created",
                        "payload": {
                            "id":           measurement_id,
                            "vehicle_count": vehicle_count,
                            "avg_speed_kmh": None,
                            "source":       "browser_webcam",
                        },
                    },
                )

    # ── Database helpers (sync → async) ──────────────────────────────

    async def _create_session(self, device_label: str):
        from asgiref.sync import sync_to_async
        return await sync_to_async(self._sync_create_session)(device_label)

    def _sync_create_session(self, device_label: str):
        from apps.cameras.models import BrowserWebcamSession
        # End any stale active sessions for this user
        BrowserWebcamSession.objects.filter(
            user=self._user, is_active=True
        ).update(is_active=False, ended_at=timezone.now())

        return BrowserWebcamSession.objects.create(
            user=self._user,
            device_label=device_label,
        )

    async def _post_measurement(self, vehicle_count: int, elapsed: float) -> int | None:
        from asgiref.sync import sync_to_async
        return await sync_to_async(self._sync_post_measurement)(vehicle_count, elapsed)

    def _sync_post_measurement(self, vehicle_count: int, elapsed: float) -> int | None:
        if self._session is None:
            return None
        from apps.traffic.models import TrafficMeasurement
        m = TrafficMeasurement.objects.create(
            camera_id=self._session.camera_id,
            measured_at=timezone.now(),
            vehicle_count=vehicle_count,
            avg_speed_kmh=None,   # never fabricated — no calibration
            occupancy_pct=None,
            data_source="ai",
        )
        # Update running total
        BrowserWebcamSession = self._session.__class__
        BrowserWebcamSession.objects.filter(pk=self._session.pk).update(
            vehicle_count_total=self._session.vehicle_count_total + vehicle_count
        )
        logger.info(
            "BrowserWebcam measurement: user=%s vehicles=%d interval=%.0fs id=%d",
            self._user.username, vehicle_count, elapsed, m.pk,
        )
        return m.pk

    async def _end_session(self):
        if self._session is None:
            return
        from asgiref.sync import sync_to_async
        await sync_to_async(self._sync_end_session)()
        self._session = None
        self._active = False

    def _sync_end_session(self):
        from apps.cameras.models import BrowserWebcamSession
        # Delete ephemeral browser webcam session on end to avoid leaving temporary records
        try:
            BrowserWebcamSession.objects.filter(pk=self._session.pk).delete()
        except Exception:
            # Fallback: mark as ended if delete fails for any reason
            BrowserWebcamSession.objects.filter(pk=self._session.pk).update(
                is_active=False,
                ended_at=timezone.now(),
            )
