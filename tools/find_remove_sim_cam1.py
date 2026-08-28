#!/usr/bin/env python3
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(ROOT, 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from apps.cameras.models import Camera

name = 'SIM-CAM-1'
cam = Camera.objects.filter(name=name).first()
if cam:
    print(f"Found Camera: id={cam.pk} name={cam.name} stream_url={cam.stream_url}")
    try:
        cam.delete()
        print('Deleted SIM-CAM-1')
    except Exception as e:
        print('Error deleting:', e)
else:
    print('SIM-CAM-1 not found')
