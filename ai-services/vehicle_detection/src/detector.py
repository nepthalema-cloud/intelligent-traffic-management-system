"""
YOLOv8 vehicle detector with ByteTrack-style tracking.

Uses ultralytics built-in tracking (BoT-SORT) to assign consistent track IDs
across frames. Vehicle classes from COCO dataset (YOLO default):
  car=2, motorcycle=3, bus=5, truck=7
"""

import logging
import numpy as np
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

VEHICLE_CLASS_IDS = {2, 3, 5, 7}   # car, motorcycle, bus, truck
VEHICLE_CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class Detection:
    track_id:   int
    class_name: str
    confidence: float
    bbox:       tuple[float, float, float, float]   # x1,y1,x2,y2 normalized 0–1
    frame_w:    int
    frame_h:    int


class VehicleDetector:
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.4):
        from ultralytics import YOLO
        logger.info("Loading YOLO model: %s", model_path)
        self.model = YOLO(model_path)
        self.conf  = conf_threshold
        logger.info("YOLO model loaded (device: %s)", self.model.device)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run detection + tracking on a single BGR frame.
        Returns a list of Detection objects for vehicle classes only.
        """
        h, w = frame.shape[:2]
        results = self.model.track(
            frame,
            conf=self.conf,
            classes=list(VEHICLE_CLASS_IDS),
            persist=True,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results or results[0].boxes is None:
            return detections

        boxes = results[0].boxes
        for box in boxes:
            cls_id = int(box.cls[0])
            if cls_id not in VEHICLE_CLASS_IDS:
                continue
            conf   = float(box.conf[0])
            track_id = int(box.id[0]) if box.id is not None else -1
            x1, y1, x2, y2 = box.xyxyn[0].tolist()   # normalized coords

            detections.append(Detection(
                track_id=track_id,
                class_name=VEHICLE_CLASS_NAMES.get(cls_id, "vehicle"),
                confidence=conf,
                bbox=(x1, y1, x2, y2),
                frame_w=w,
                frame_h=h,
            ))

        return detections
