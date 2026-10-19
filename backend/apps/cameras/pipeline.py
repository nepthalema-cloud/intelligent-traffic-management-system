"""
Shared video/webcam AI pipeline helpers: reuse detection, OCR, overlay rendering,
and event generation logic used by Video Analysis and Browser Webcam.

Functions:
 - analyze_frame(detections, frame, frame_time, meters_per_pixel, state)
    processes Detection objects, updates tracking state, returns frame_dets,
    per_frame_events, annotated_frame, and updated state.

State is a dict that may contain 'last_pos', 'last_time', 'tracks', 'violations'.
"""
from typing import Tuple, List, Dict, Any
import math
import cv2
from PIL import Image
import logging

logger = logging.getLogger(__name__)


def _try_ocr_crop(pil_img):
    try:
        import pytesseract
        text = pytesseract.image_to_string(pil_img)
        return text.strip() or None
    except Exception:
        return None


def _resolve_plate_registry(plate_text: str) -> Dict[str, Any]:
    """
    Resolve a detected plate to the Vehicle/Driver registry.
    Uses PlateResolutionService when Django is available.
    Falls back to direct parameterized SQLite query against /shared_db/db.sqlite3
    so the AI worker container can resolve plates without installing Django.
    """
    if not plate_text or not isinstance(plate_text, str):
        return {"plate": "", "vehicle": None, "driver": None, "message": "Invalid plate", "matched": False}

    raw_cleaned = plate_text.strip().upper()
    try:
        from apps.violations.services import PlateResolutionService
        res = PlateResolutionService.resolve_plate(raw_cleaned)
        if isinstance(res, dict):
            res["matched"] = bool(res.get("vehicle"))
            return res
    except Exception as django_exc:
        logger.debug("Django PlateResolutionService unavailable (%s); using direct SQLite lookup.", django_exc)

    # Direct SQLite query fallback
    try:
        import sqlite3
        import re

        compact = re.sub(r'[^A-Z0-9]', '', raw_cleaned)
        if not compact:
            return {"plate": raw_cleaned, "vehicle": None, "driver": None, "message": "Invalid plate format", "matched": False}

        db_path = os.environ.get('SHARED_DB_PATH', '/shared_db/db.sqlite3')
        if not os.path.exists(db_path):
            alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'db.sqlite3')
            if os.path.exists(alt_path):
                db_path = alt_path

        conn = sqlite3.connect(db_path, timeout=10.0)
        cur = conn.cursor()
        query = """
            SELECT
                v.id, v.plate_number, v.vehicle_type, v.color, v.make, v.model, v.year, v.is_active,
                d.id, d.first_name, d.last_name, d.license_number
            FROM violations_vehicle v
            LEFT JOIN drivers_driver d ON v.driver_id = d.id
            WHERE UPPER(REPLACE(REPLACE(v.plate_number, '-', ''), ' ', '')) = ?
            LIMIT 1
        """
        cur.execute(query, (compact,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {
                "plate": raw_cleaned,
                "vehicle": None,
                "driver": None,
                "message": "Vehicle not registered",
                "matched": False
            }

        (v_id, v_plate, v_type, v_color, v_make, v_model, v_year, v_active,
         d_id, d_first, d_last, d_license) = row

        vehicle_data = {
            "id": v_id,
            "plate_number": v_plate,
            "vehicle_type": v_type,
            "color": v_color,
            "make": v_make,
            "model": v_model,
            "year": v_year,
            "is_active": bool(v_active),
        }

        driver_data = None
        if d_id:
            driver_name = f"{d_first or ''} {d_last or ''}".strip()
            driver_data = {
                "id": d_id,
                "full_name": driver_name,
                "license_number": d_license,
            }

        return {
            "plate": raw_cleaned,
            "vehicle": vehicle_data,
            "driver": driver_data,
            "message": "Vehicle and driver found" if driver_data else "Vehicle found but no registered driver",
            "matched": True
        }
    except Exception as exc:
        logger.warning("Failed direct SQLite plate lookup for '%s': %s", raw_cleaned, exc)
        return {
            "plate": raw_cleaned,
            "vehicle": None,
            "driver": None,
            "message": "Registry lookup failed",
            "matched": False
        }


def analyze_frame(detections: list, frame: Any, frame_time: float, meters_per_pixel: float | None, state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Any, Dict[str, Any]]:
    """Analyze detections for a single frame.

    - detections: list of Detection-like objects with attributes: bbox (normalized), class_name, confidence, track_id
    - frame: BGR numpy array (OpenCV)
    - frame_time: float timestamp in seconds
    - meters_per_pixel: float or None for speed estimation
    - state: mutable dict to hold last_pos, last_time, tracks, violations

    Returns (frame_dets, per_frame_events, annotated_frame, state)
    """
    h, w = frame.shape[:2]
    last_pos = state.setdefault('last_pos', {})
    last_time = state.setdefault('last_time', {})
    tracks = state.setdefault('tracks', {})
    violations = state.setdefault('violations', [])

    frame_dets = []
    per_frame_events = []

    for det in detections:
        try:
            x1 = int(det.bbox[0] * w)
            y1 = int(det.bbox[1] * h)
            x2 = int(det.bbox[2] * w)
            y2 = int(det.bbox[3] * h)
        except Exception:
            continue

        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (14, 125, 255), 2)

        label_parts = [det.class_name.capitalize()]

        speed_kmh = None
        if meters_per_pixel:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            tid = det.track_id
            if tid in last_pos:
                dx = cx - last_pos[tid][0]
                dy = cy - last_pos[tid][1]
                pixel_dist = math.hypot(dx, dy)
                dt = frame_time - last_time.get(tid, frame_time)
                if dt > 0:
                    speed_ms = (pixel_dist * meters_per_pixel) / dt
                    speed_kmh = speed_ms * 3.6
                    label_parts.append(f"{speed_kmh:.0f} km/h")
            last_pos[det.track_id] = (cx, cy)
            last_time[det.track_id] = frame_time

        plate_text = None
        registry_resolution = None
        try:
            crop = frame[y1:y2, x1:x2]
            pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            plate_text = _try_ocr_crop(pil)
            if plate_text:
                label_parts.append(plate_text)
                # Resolve plate to Vehicle/Driver registry
                registry_resolution = _resolve_plate_registry(plate_text)
                per_frame_events.append({
                    'type': 'plate',
                    'track_id': det.track_id,
                    'plate': plate_text,
                    'time': frame_time,
                    'vehicle': registry_resolution.get('vehicle'),
                    'driver': registry_resolution.get('driver'),
                })
        except Exception:
            plate_text = None

        label = ' | '.join(label_parts)
        cv2.putText(frame, label, (x1, max(y1 - 6, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        det_record = {
            'track_id': str(det.track_id),
            'class': det.class_name,
            'confidence': float(det.confidence) if hasattr(det, 'confidence') else None,
            'bbox': [float(det.bbox[0]), float(det.bbox[1]), float(det.bbox[2]), float(det.bbox[3])],
            'speed_kmh': float(speed_kmh) if speed_kmh is not None else None,
            'plate': plate_text,
            'vehicle': registry_resolution.get('vehicle') if registry_resolution else None,
            'driver': registry_resolution.get('driver') if registry_resolution else None,
            'violation': False,
        }

        track_id = str(det.track_id)
        if track_id not in tracks:
            tracks[track_id] = {
                'track_id': track_id,
                'vehicle_type': det.class_name,
                'first_seen': frame_time,
                'last_seen': frame_time,
                'frames': [],
                'confidence_history': [],
                'speed_history': [],
                'bboxes': [],
                'plate': plate_text,
                'plate_confidence': float(det.confidence) if hasattr(det, 'confidence') else None,
                'max_speed': speed_kmh,
                'avg_speed': None,
                'thumbnail': None,
                'violation': False,
                'violation_reasons': [],
            }
            try:
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    # For webcam we don't persist snapshots here; caller may choose to
                    # extract thumbnails if desired. Keep placeholder None.
                    tracks[track_id]['thumbnail'] = None
            except Exception:
                pass

        track = tracks[track_id]
        track['last_seen'] = frame_time
        track['frames'].append(frame_time)
        track['confidence_history'].append(float(det.confidence) if hasattr(det, 'confidence') else None)
        track['bboxes'].append([float(det.bbox[0]), float(det.bbox[1]), float(det.bbox[2]), float(det.bbox[3])])
        if speed_kmh is not None:
            track['speed_history'].append(speed_kmh)
            if track['max_speed'] is None or speed_kmh > track['max_speed']:
                track['max_speed'] = speed_kmh
        if track['plate'] is None and plate_text:
            track['plate'] = plate_text
            track['plate_confidence'] = float(det.confidence) if hasattr(det, 'confidence') else None
        # Add registry resolution to track if available
        if registry_resolution:
            track['vehicle'] = registry_resolution.get('vehicle')
            track['driver'] = registry_resolution.get('driver')

        # simple violation rule: speed threshold
        if speed_kmh is not None and speed_kmh > 80:
            violation_desc = 'Speed exceeded 80 km/h'
            track['violation'] = True
            if violation_desc not in track['violation_reasons']:
                track['violation_reasons'].append(violation_desc)
            det_record['violation'] = True
            violations.append({
                'track_id': track_id,
                'time': frame_time,
                'plate': plate_text,
                'speed_kmh': speed_kmh,
                'rule': violation_desc,
                'confidence': float(det.confidence) if hasattr(det, 'confidence') else None,
            })

        frame_dets.append(det_record)

    state['last_pos'] = last_pos
    state['last_time'] = last_time
    state['tracks'] = tracks
    state['violations'] = violations

    return frame_dets, per_frame_events, frame, state
