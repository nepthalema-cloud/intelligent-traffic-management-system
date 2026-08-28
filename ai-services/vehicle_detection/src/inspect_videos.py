"""
Inspect test traffic videos — run YOLO detection on one frame per video.
Reports what is realistically detectable from each video source.
NOT used in production — development/analysis tool only.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from ultralytics import YOLO
import cv2

VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

model = YOLO('yolov8n.pt')

FRAME_DIR = r'C:\Users\HI\AppData\Local\Temp\video_frames'
VIDEOS = {
    'V1 (27260-362770008_medium)':        '27260-362770008_medium_frame.jpg',
    'V2 (8355-208052034_medium)':          '8355-208052034_medium_frame.jpg',
    'V3 (istockphoto-476627368)':          'istockphoto-476627368-mp4-480x480-is_frame.jpg',
    'V4 (istockphoto-851692014)':          'istockphoto-851692014-640_adpp_is_frame.jpg',
}

print("=" * 60)
print("YOLO Vehicle Detection — Frame Analysis")
print("Model: YOLOv8n  |  Confidence threshold: 0.25")
print("=" * 60)

for label, fname in VIDEOS.items():
    path = os.path.join(FRAME_DIR, fname)
    frame = cv2.imread(path)
    if frame is None:
        print(f"\n{label}: FAILED to load frame at {path}")
        continue

    h, w = frame.shape[:2]
    results = model(frame, verbose=False, conf=0.25)[0]

    vehicle_dets = []
    all_dets = []

    for box in results.boxes:
        cls_id = int(box.cls[0])
        conf   = float(box.conf[0])
        name   = model.names[cls_id]
        x1, y1, x2, y2 = box.xyxyn[0].tolist()
        bbox_size = (x2 - x1) * (y2 - y1)  # fraction of frame
        all_dets.append({'class': name, 'conf': conf, 'size': bbox_size})
        if cls_id in VEHICLE_CLASSES:
            vehicle_dets.append({'class': VEHICLE_CLASSES[cls_id], 'conf': conf, 'size': bbox_size})

    # Sort by confidence
    vehicle_dets.sort(key=lambda x: x['conf'], reverse=True)
    all_dets.sort(key=lambda x: x['conf'], reverse=True)

    print(f"\n{label}")
    print(f"  Frame: {w}x{h}")
    print(f"  Vehicles detected: {len(vehicle_dets)}")
    if vehicle_dets:
        for d in vehicle_dets[:5]:
            print(f"    {d['class']:<12} conf={d['conf']:.3f}  bbox_area={d['size']*100:.1f}%")
    else:
        print("    (none at conf>=0.25)")
    print(f"  All objects (top 5):")
    for d in all_dets[:5]:
        print(f"    {d['class']:<12} conf={d['conf']:.3f}")

    # Qualitative assessment
    max_veh_conf = max((d['conf'] for d in vehicle_dets), default=0)
    min_bbox = min((d['size'] for d in vehicle_dets), default=1)
    print("  Assessment:")
    print(f"    Vehicle counting: {'GOOD' if len(vehicle_dets) >= 3 else 'LIMITED' if len(vehicle_dets) >= 1 else 'NONE'}")
    print(f"    Tracking viable: {'YES' if len(vehicle_dets) >= 2 else 'LIMITED'}")
    print(f"    Speed estimation: REQUIRES camera calibration (meters/pixel) — NOT YET AVAILABLE")
    plate_readable = min_bbox > 0.01 and max_veh_conf > 0.7
    print(f"    Plate recognition: {'POSSIBLE (large vehicles)' if plate_readable else 'UNLIKELY (vehicles too small/far)'}")

print("\n" + "=" * 60)
