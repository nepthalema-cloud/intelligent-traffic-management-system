#!/usr/bin/env python3
"""
Simulate a browser webcam pipeline run for testing.
- Sets up Django
- Creates a BrowserWebcamSession for an existing user
- Sends a fake base64 JPEG to the module detection path (monkeypatched)
- Creates a TrafficMeasurement like the real consumer would
- Ends the session and verifies Camera table unchanged

Run from repo root:
    python tools/simulate_browser_webcam_pipeline.py
"""
import os
import sys
import base64
from io import BytesIO
from PIL import Image

# --- Django setup -------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
# Ensure `backend` package is importable as top-level `config` package
BACKEND_DIR = os.path.join(ROOT, 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.cameras.models import BrowserWebcamSession, Camera
from apps.traffic.models import TrafficMeasurement
import apps.cameras.webcam_consumer as wc
from django.utils import timezone

User = get_user_model()

print("Starting simulation of browser webcam pipeline...\n")

# Snapshot cameras count
cam_count_before = Camera.objects.count()
print(f"Cameras before: {cam_count_before}")

# Pick or create a test user
user = User.objects.filter(is_superuser=True).first()
if not user:
    user, _created = User.objects.get_or_create(username='testwebcam')
    if _created:
        user.set_password('test')
        user.save()
print(f"Using user: {user.username} (id={user.pk})")

# Create a BrowserWebcamSession (temporary)
session = BrowserWebcamSession.objects.create(user=user, device_label='Simulated Camera')
print(f"Created BrowserWebcamSession: id={session.pk} token={session.session_token} active={session.is_active}")

# Build a tiny test image and encode as base64 JPEG
img = Image.new('RGB', (320, 240), color=(73, 109, 137))
buf = BytesIO()
img.save(buf, format='JPEG')
buf.seek(0)
b64 = base64.b64encode(buf.read()).decode('ascii')

# Monkeypatch the module detection to avoid loading YOLO in this environment
class FakeDet:
    def __init__(self, track_id=1, class_name='car', confidence=0.9, bbox=(0.4,0.4,0.6,0.6), frame_w=320, frame_h=240):
        self.track_id = track_id
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox
        self.frame_w = frame_w
        self.frame_h = frame_h

def fake_run_detection(b64_data: str):
    print("[fake_run_detection] invoked with frame (len=%d)" % (len(b64_data)))
    # return one fake detection
    return [FakeDet()]

wc._run_detection = fake_run_detection
print('\nPatched webcam_consumer._run_detection to fake_run_detection.')

# Simulate detection call (as consumer would do)
detections = wc._run_detection(b64)
print(f"Detections returned: {len(detections)}")
for d in detections:
    print(f"  track_id={d.track_id} class={d.class_name} conf={d.confidence}")

# --- OCR simulation -------------------------------------------------
def fake_ocr(image_bytes: bytes) -> str:
    """Pretend to return an OCR'd plate string."""
    return "SIM-PLATE-123"

# If any detection looks like a plate, call OCR on the frame (simulated)
for d in detections:
    if getattr(d, 'class_name', '') in ('license_plate', 'plate'):
        print("Simulating OCR for detected plate...")
        plate = fake_ocr(b64.encode('ascii'))
        print(f"OCR result: {plate}")

# --- Speed estimation simulation -----------------------------------
# Create a temporary Camera + calibration and associate it to the session
# Use a unique temporary camera name to avoid collisions with existing cameras
from apps.cameras.models import Camera, CameraCalibration
import uuid
temp_cam_name = f"SIM-CAM-{uuid.uuid4().hex[:8]}"
cam, _created_cam = Camera.objects.get_or_create(name=temp_cam_name, defaults={'stream_url': ''})
cal = CameraCalibration.objects.create(camera=cam, meters_per_pixel=0.02, calibrated_by=user)
# Attach camera to session (demonstrating optional mapping)
BrowserWebcamSession.objects.filter(pk=session.pk).update(camera=cam)
session.refresh_from_db()
print(f"Attached Camera id={cam.pk} with meters_per_pixel={cal.meters_per_pixel}")

# Simulate two detections for same track at t0 and t1 to compute speed
import time as _time
t0 = _time.time()
# first detection centre x in pixels
cx1 = 50
_time.sleep(0.5)
t1 = _time.time()
cx2 = 150
pixel_distance = abs(cx2 - cx1)
frame_interval = t1 - t0 or 0.1
speed_ms = (pixel_distance * cal.meters_per_pixel) / frame_interval
speed_kmh = speed_ms * 3.6
print(f"Simulated pixel_distance={pixel_distance} px interval={frame_interval:.2f}s -> speed={speed_kmh:.1f} km/h")

# Create TrafficMeasurement including avg_speed_kmh
meas = TrafficMeasurement.objects.create(
    camera_id=session.camera_id,
    measured_at=timezone.now(),
    vehicle_count=len({d.track_id for d in detections if d.track_id >= 0}),
    avg_speed_kmh=round(speed_kmh, 1),
    occupancy_pct=None,
    data_source='ai',
)
print(f"Created TrafficMeasurement id={meas.pk} vehicle_count={meas.vehicle_count} camera_id={meas.camera_id} avg_speed_kmh={meas.avg_speed_kmh}")

# Update session running total and end session
BrowserWebcamSession.objects.filter(pk=session.pk).update(
    vehicle_count_total=session.vehicle_count_total + meas.vehicle_count,
    is_active=False,
    ended_at=timezone.now(),
)
session.refresh_from_db()
print(f"Session after end: is_active={session.is_active} ended_at={session.ended_at} total={session.vehicle_count_total}")

# Clean up temporary calibration and camera so we don't modify the permanent Camera table
try:
    CameraCalibration.objects.filter(pk=cal.pk).delete()
    if _created_cam:
        Camera.objects.filter(pk=cam.pk).delete()
        print(f"Cleaned up temporary Camera id={cam.pk} and its calibration.")
    else:
        print(f"Removed temporary calibration but left pre-existing Camera id={cam.pk}.")
except Exception as exc:
    print(f"Cleanup error: {exc}")

# Verify cameras unchanged
cam_count_after = Camera.objects.count()
print(f"Cameras after cleanup: {cam_count_after}")
if cam_count_before == cam_count_after:
    print("Camera table unchanged ✅")
else:
    print("Camera table changed — unexpected ❌")

print('\nSimulation complete.')
