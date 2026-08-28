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
cams = Camera.objects.all()
print('Total cameras:', cams.count())
for c in cams:
    print(f' - id={c.pk} name={c.name} type={c.camera_type} stream={c.stream_url} active={c.is_active}')
