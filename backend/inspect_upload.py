import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.cameras.models import TemporaryVideoAnalysis

for job_id in [16, 17]:
    try:
        job = TemporaryVideoAnalysis.objects.get(pk=job_id)
    except TemporaryVideoAnalysis.DoesNotExist:
        print(f'JOB {job_id} not found')
        continue
    print('\n=== JOB', job_id, '===')
    print('status=', job.status)
    print('original_filename=', job.original_filename)
    print('upload.name=', job.upload.name)
    try:
        print('upload.path=', job.upload.path)
    except Exception as exc:
        print('upload.path error=', exc)
    if job.upload and job.upload.path:
        print('exists=', os.path.exists(job.upload.path))
        if os.path.exists(job.upload.path):
            print('size=', os.path.getsize(job.upload.path))
            import cv2
            cap = cv2.VideoCapture(job.upload.path)
            print('cap.isOpened=', cap.isOpened())
            print('fps=', cap.get(cv2.CAP_PROP_FPS))
            print('width=', cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            print('height=', cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
    print('annotated_video=', job.annotated_video.name if job.annotated_video else None)
    print('result_json=', job.result_json)
