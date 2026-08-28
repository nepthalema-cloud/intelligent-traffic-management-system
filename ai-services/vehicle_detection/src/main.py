"""
AI Vehicle Detection Service — Phase 5 (production-resilient).

Real pipeline:
  RTSP → frame capture → YOLOv8 detection → track → count
  → speed (if calibrated) → POST measurement
  → wrong-way detection → POST violation + evidence frame

Production resilience:
  - Never exits after stream failures — infinite exponential backoff reconnect
  - Reports camera health to Django on connect/disconnect
  - Fetches calibration from Django API on startup and periodically
  - Violation detection from real tracking observations only (no fabrication)

Violation rules (rule-based from available data, no fabrication):
  WRONG_WAY  — vehicle tracked moving in wrong direction reliably detectable
               from bounding box centroid vertical movement in a fixed-camera
               downward-facing view. Only triggers when confidence > threshold.
               NOTE: This is a demonstration rule. For reliable production
               violation detection, camera angle, lane markings, and calibration
               are required. Until then, this rule fires conservatively.

Speed estimation:
  Requires valid CameraCalibration record with meters_per_pixel.
  Without calibration, avg_speed_kmh is stored as NULL (never invented).
"""

import logging
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "common" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vehicle_detection")

import cv2
import numpy as np

from ingest   import DjangoIngestClient
from detector import VehicleDetector
from rtsp_reader import RTSPReader

# ── Config ────────────────────────────────────────────────────────────────

CAMERA_ID            = int(os.getenv("CAMERA_ID", "1"))
RTSP_URL_OVERRIDE    = os.getenv("RTSP_URL", "")
YOLO_MODEL           = os.getenv("YOLO_MODEL", "yolov8n.pt")
DET_CONF             = float(os.getenv("DETECTION_CONFIDENCE", "0.4"))
MEASURE_INTERVAL     = int(os.getenv("MEASUREMENT_INTERVAL_SECONDS", "30"))
SPEED_LIMIT_KMH      = float(os.getenv("SPEED_LIMIT_KMH", "60"))
VIOL_CONF_THRESHOLD  = float(os.getenv("VIOLATION_CONFIDENCE_THRESHOLD", "0.70"))
CALIBRATION_REFRESH  = 300  # re-fetch calibration from Django every 5 min

# Reconnect: exponential backoff starting at INITIAL_DELAY, max MAX_DELAY
INITIAL_DELAY = float(os.getenv("RECONNECT_DELAY_SECONDS", "5"))
MAX_DELAY     = 120.0

MODEL_NAME    = "YOLOv8n"
MODEL_VERSION = "8.0"


# ── Violation detection ───────────────────────────────────────────────────

class ViolationDetector:
    """
    Rule-based violation detector using tracked vehicle observations.

    Rules implemented:
      1. WRONG_WAY — conservative direction-reversal detection.
         Fires only when a vehicle has been tracked for multiple frames
         and its net vertical movement is consistently opposite to the
         dominant flow direction. Requires at least 30 frames of history.

    Rules NOT implemented (require additional sensor/calibration data):
      - SPEEDING:        requires valid meters_per_pixel calibration
      - RED_LIGHT:       requires traffic signal state integration
      - ILLEGAL_PARKING: requires zone/region annotation
      - ILLEGAL_TURN:    requires lane marking detection

    Every violation must be from real tracking data, never from timers
    or random number generators.
    """

    # Minimum frames before declaring wrong-way
    MIN_TRACK_FRAMES    = 30
    # Fraction of frames that must show upward movement to trigger wrong-way
    WRONG_WAY_THRESHOLD = 0.7

    def __init__(self):
        # track_id → list of (cy_normalized, timestamp)
        self._track_history: dict[int, list[tuple[float, float]]] = defaultdict(list)
        self._fired_wrongs:  set[int] = set()   # track IDs that already triggered

    def update(self, detections, frame_time: float) -> list[dict]:
        """
        Update tracker history and return list of new violations.
        Each violation: {type, confidence, track_id, description}
        """
        violations = []

        for det in detections:
            tid = det.track_id
            if tid < 0:
                continue

            cy = (det.bbox[1] + det.bbox[3]) / 2   # normalized vertical centre

            history = self._track_history[tid]
            history.append((cy, frame_time))

            # Keep only last 90 frames of history
            if len(history) > 90:
                history.pop(0)

            if len(history) < self.MIN_TRACK_FRAMES:
                continue
            if tid in self._fired_wrongs:
                continue

            # Check wrong-way: count frames where vehicle moved upward (decreasing cy)
            # In a standard top-down or perspective camera, normal traffic flows
            # downward (increasing cy). Upward = wrong direction.
            up_count   = sum(1 for i in range(1, len(history)) if history[i][0] < history[i-1][0])
            down_count = sum(1 for i in range(1, len(history)) if history[i][0] > history[i-1][0])
            total      = up_count + down_count

            if total == 0:
                continue

            up_fraction = up_count / total

            # Dominant flow is downward — if mostly upward, flag wrong-way
            if up_fraction >= self.WRONG_WAY_THRESHOLD and down_count > 2:
                # Confidence: proportional to consistency of wrong-way movement
                confidence = min(up_fraction * det.confidence, 0.92)
                if confidence >= VIOL_CONF_THRESHOLD:
                    violations.append({
                        "type":        "wrong_way",
                        "confidence":  confidence,
                        "track_id":    tid,
                        "description": (
                            f"Vehicle (track_id={tid}, class={det.class_name}) "
                            f"detected moving against traffic flow. "
                            f"Wrong-way fraction={up_fraction:.2f} over {len(history)} frames. "
                            f"Confidence={confidence:.3f}."
                        ),
                    })
                    self._fired_wrongs.add(tid)
                    logger.warning(
                        "WRONG-WAY detected: track_id=%d confidence=%.3f",
                        tid, confidence,
                    )

        return violations

    def cleanup_stale(self, active_track_ids: set[int]):
        """Remove history for tracks no longer visible."""
        stale = [tid for tid in list(self._track_history) if tid not in active_track_ids]
        for tid in stale:
            del self._track_history[tid]
            self._fired_wrongs.discard(tid)


# ── Evidence frame saving ─────────────────────────────────────────────────

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence_frames"
EVIDENCE_DIR.mkdir(exist_ok=True)


def save_evidence_frame(frame: np.ndarray, camera_id: int, track_id: int) -> str | None:
    """
    Save a frame to local disk and return a reference URL.

    In production this would upload to S3/object storage.
    In development, saves to ai-services/vehicle_detection/evidence_frames/
    and returns a file:// URL.

    Returns None if save fails — violation is still recorded without evidence.
    """
    try:
        ts  = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        fname = f"cam{camera_id}_track{track_id}_{ts}.jpg"
        path  = EVIDENCE_DIR / fname
        cv2.imwrite(str(path), frame)
        # In production: upload to S3 and return https:// URL
        # In development: return absolute file path as reference
        return f"file://{path.as_posix()}"
    except Exception as exc:
        logger.warning("Failed to save evidence frame: %s", exc)
        return None


# ── Main loop ─────────────────────────────────────────────────────────────

def get_rtsp_url(client: DjangoIngestClient) -> str | None:
    if RTSP_URL_OVERRIDE:
        logger.info("RTSP URL from env override.")
        return RTSP_URL_OVERRIDE
    camera = client.get_camera(CAMERA_ID)
    if not camera:
        logger.error("Cannot fetch camera %d from Django.", CAMERA_ID)
        return None
    url = camera.get("stream_url", "")
    if not url:
        logger.error("Camera %d has no stream_url.", CAMERA_ID)
        return None
    return url


def run():
    logger.info("=== AI Vehicle Detection Service starting (production-resilient) ===")
    logger.info("Camera %d | Model: %s | Interval: %ds", CAMERA_ID, YOLO_MODEL, MEASURE_INTERVAL)

    client = DjangoIngestClient()
    # Retry login indefinitely
    while not client.login():
        logger.warning("Login failed, retrying in 10s…")
        time.sleep(10)

    rtsp_url = get_rtsp_url(client)
    while not rtsp_url:
        logger.warning("No RTSP URL, retrying in 15s…")
        time.sleep(15)
        rtsp_url = get_rtsp_url(client)

    detector    = VehicleDetector(model_path=YOLO_MODEL, conf_threshold=DET_CONF)
    viol_detect = ViolationDetector()

    # Fetch calibration from Django
    calibration = client.get_calibration(CAMERA_ID)
    mpp = calibration["meters_per_pixel"] if calibration else None
    last_cal_fetch = time.time()

    if mpp:
        logger.info("Speed estimation ENABLED: %.6f m/px", mpp)
    else:
        logger.info("Speed estimation DISABLED (no calibration — speed will be NULL)")

    # Exponential backoff state
    delay = INITIAL_DELAY

    reader = RTSPReader(rtsp_url=rtsp_url, camera_id=CAMERA_ID)

    while True:
        connected = reader._connect()
        if connected:
            delay = INITIAL_DELAY  # reset backoff on success
            client.report_camera_health(CAMERA_ID, True, "RTSP stream connected")
            logger.info("Pipeline active: camera=%d AI=%s speed=%s",
                        CAMERA_ID, YOLO_MODEL,
                        f"enabled ({mpp:.6f} m/px)" if mpp else "disabled (no calibration)")

            window_start    = time.time()
            window_vehicles: set[int] = set()
            window_speeds:   list[float] = []
            prev_centroids:  dict[int, tuple[float, float]] = {}
            prev_time        = time.time()

            try:
                while True:
                    # Periodically refresh calibration
                    if time.time() - last_cal_fetch > CALIBRATION_REFRESH:
                        calibration = client.get_calibration(CAMERA_ID)
                        mpp = calibration["meters_per_pixel"] if calibration else None
                        last_cal_fetch = time.time()
                        if mpp:
                            logger.info("Calibration refreshed: %.6f m/px", mpp)

                    frame, frame_num = reader.read_frame()

                    if frame is None:
                        logger.warning("Stream lost: camera=%d", CAMERA_ID)
                        client.report_camera_health(CAMERA_ID, False, "RTSP stream lost mid-session")
                        break  # exit inner loop → reconnect

                    now = time.time()
                    detections = detector.detect(frame)
                    active_ids = {d.track_id for d in detections if d.track_id >= 0}

                    # ── Violation detection (real observations only) ──────
                    new_violations = viol_detect.update(detections, now)
                    for v in new_violations:
                        viol_result = client.post_violation(
                            camera_id=CAMERA_ID,
                            violation_type=v["type"],
                            confidence=v["confidence"],
                            occurred_at=datetime.now(tz=timezone.utc),
                            description=v["description"],
                        )
                        if viol_result:
                            viol_id = viol_result.get("data", {}).get("id")
                            if viol_id:
                                # Save evidence frame from actual video
                                ev_url = save_evidence_frame(frame, CAMERA_ID, v["track_id"])
                                if ev_url:
                                    client.post_evidence(
                                        violation_id=viol_id,
                                        evidence_url=ev_url,
                                        confidence=v["confidence"],
                                        description=f"Frame captured at detection event. {v['description']}",
                                    )

                    viol_detect.cleanup_stale(active_ids)

                    # ── Measurements window ───────────────────────────────
                    for det in detections:
                        tid = det.track_id
                        if tid < 0:
                            continue
                        window_vehicles.add(tid)

                        if mpp and mpp > 0:
                            cx = (det.bbox[0] + det.bbox[2]) / 2 * det.frame_w
                            cy = (det.bbox[1] + det.bbox[3]) / 2 * det.frame_h
                            if tid in prev_centroids:
                                px, py = prev_centroids[tid]
                                dt = now - prev_time
                                if dt > 0:
                                    pixel_dist = math.sqrt((cx-px)**2 + (cy-py)**2)
                                    speed_ms   = (pixel_dist * mpp) / dt
                                    speed_kmh  = speed_ms * 3.6
                                    if 0 < speed_kmh < 200:
                                        window_speeds.append(speed_kmh)
                            prev_centroids[tid] = (cx, cy)

                    prev_time = now

                    elapsed = now - window_start
                    if elapsed >= MEASURE_INTERVAL:
                        vehicle_count = len(window_vehicles)
                        avg_speed     = (sum(window_speeds) / len(window_speeds)) if window_speeds else None

                        result = client.post_measurement(
                            camera_id=CAMERA_ID,
                            vehicle_count=vehicle_count,
                            measured_at=datetime.now(tz=timezone.utc),
                            avg_speed_kmh=round(avg_speed, 1) if avg_speed else None,
                            occupancy_pct=None,
                        )
                        if result:
                            logger.info(
                                "Measurement ✓ vehicles=%d speed=%s interval=%.0fs",
                                vehicle_count,
                                f"{avg_speed:.1f} km/h" if avg_speed else "NULL (uncalibrated)",
                                elapsed,
                            )
                        else:
                            logger.warning("Measurement POST failed — next interval will retry")

                        window_vehicles.clear()
                        window_speeds.clear()
                        window_start = time.time()

            except KeyboardInterrupt:
                logger.info("Service stopped by user.")
                reader.release()
                return

        else:
            client.report_camera_health(CAMERA_ID, False,
                f"RTSP connection failed, retrying in {delay:.0f}s")

        # Exponential backoff — NEVER exits permanently
        logger.warning("Reconnecting in %.0fs (backoff)…", delay)
        time.sleep(delay)
        delay = min(delay * 2, MAX_DELAY)


if __name__ == "__main__":
    run()
