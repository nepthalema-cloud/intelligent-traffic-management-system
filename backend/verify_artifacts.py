import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
try:
    django.setup()
except Exception as exc:
    print('DJANGO_SETUP_ERROR', repr(exc))
    sys.exit(1)

from apps.cameras.models import TemporaryVideoAnalysis
from django.conf import settings

job = TemporaryVideoAnalysis.objects.filter(status=TemporaryVideoAnalysis.STATUS_DONE).order_by('-updated_at').first()
if not job:
    print('NO_JOB_FOUND')
    sys.exit(1)

print('JOB_ID', job.pk)
print('STATUS', job.status)
print('ANNOTATED_REL', job.annotated_video.name if job.annotated_video else None)

artifacts = []
if job.annotated_video:
    artifacts.append(('annotated_video', job.annotated_video.name))
result = job.result_json or {}
for key in ['results_file', 'csv_file', 'pdf_file']:
    if result.get(key):
        artifacts.append((key, result[key]))

for key, rel in artifacts:
    rel_norm = rel.replace('\\', '/')
    path = os.path.join(settings.MEDIA_ROOT, rel_norm)
    print('KEY', key)
    print('REL', rel)
    print('ABS', os.path.abspath(path))
    print('EXISTS', os.path.exists(path))
    if os.path.exists(path):
        print('SIZE', os.path.getsize(path))
    else:
        print('SIZE', 'MISSING')
    print('---')

# OpenCV validation for annotated video
try:
    import cv2
    if job.annotated_video:
        video_path = os.path.join(settings.MEDIA_ROOT, job.annotated_video.name.replace('\\','/'))
        cap = cv2.VideoCapture(video_path)
        opened = cap.isOpened()
        print('OPENCV_OPENED', opened)
        if opened:
            print('OPENCV_FPS', cap.get(cv2.CAP_PROP_FPS))
            print('OPENCV_WIDTH', cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            print('OPENCV_HEIGHT', cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print('OPENCV_FRAME_COUNT', int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            cap.release()
except Exception as exc:
    print('OPENCV_ERROR', repr(exc))
