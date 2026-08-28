"""Centralized detector loader that returns the ai-services VehicleDetector.

This ensures a single loading path is used by both the video worker and
the websocket consumer, avoiding duplicated loader code and inconsistent
behaviour across the project.
"""
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)


def get_vehicle_detector(conf_threshold: float = 0.35):
    """Locate ai-services/vehicle_detection, add its src to sys.path,
    import `detector.VehicleDetector` and return a constructed instance.

    Raises FileNotFoundError or ImportError on failure to help callers
    capture full tracebacks.
    """
    base = Path(__file__).resolve().parent
    ai_src = None
    model_path = None

    cur = base
    for _ in range(12):
        candidate = cur / 'ai-services' / 'vehicle_detection' / 'src'
        candidate_model = cur / 'ai-services' / 'vehicle_detection' / 'yolov8n.pt'
        if candidate.exists():
            ai_src = str(candidate)
            model_path = str(candidate_model)
            break
        if cur.parent == cur:
            break
        cur = cur.parent

    if not ai_src:
        msg = f'Could not locate ai-services vehicle_detection/src relative to {base}; searched parents'
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not Path(model_path).exists():
        msg = f'YOLO model not found at expected path: {model_path}'
        logger.error(msg)
        raise FileNotFoundError(msg)

    # Insert ai_src at front so its detector module is used
    if ai_src not in sys.path:
        sys.path.insert(0, ai_src)

    try:
        from detector import VehicleDetector
    except Exception as exc:
        logger.exception('Failed to import VehicleDetector from %s', ai_src)
        raise

    try:
        return VehicleDetector(model_path=model_path, conf_threshold=conf_threshold)
    except Exception:
        logger.exception('Failed to initialize VehicleDetector with model %s', model_path)
        raise
