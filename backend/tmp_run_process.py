import os
import shutil
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

from django.conf import settings
import django

django.setup()

from django.contrib.auth import get_user_model
from apps.cameras.models import TemporaryVideoAnalysis
from apps.cameras.video_processor import process_video_job

src = r'C:\Internship\AI-Powered Smart Traffic Management System - stagging\docker\test_videos\istockphoto-851692014-640_adpp_is.mp4'
print('SRC', src, 'exists', os.path.exists(src))
if not os.path.exists(src):
    raise SystemExit('Source video not found')

# prepare destination
dst_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'tmp_videos', datetime.datetime.utcnow().strftime('%Y'), datetime.datetime.utcnow().strftime('%m'), datetime.datetime.utcnow().strftime('%d'))
os.makedirs(dst_dir, exist_ok=True)
dst_path = os.path.join(dst_dir, os.path.basename(src))
shutil.copy(src, dst_path)
rel = os.path.relpath(dst_path, settings.MEDIA_ROOT)

User = get_user_model()
if not User.objects.exists():
    User.objects.create_user('testuser', 'test@example.com', 'password123')
u = User.objects.first()
print('USER', u)

job = TemporaryVideoAnalysis.objects.create(user=u, original_filename=os.path.basename(src), upload=rel, status=TemporaryVideoAnalysis.STATUS_PENDING)
print('CREATED JOB', job.pk)

# Run processing (synchronous)
process_video_job(job, None)

print('DONE STATUS', job.status)
print('RESULT KEYS', list((job.result_json or {}).keys()))
print('ANNOTATED', job.annotated_video.name if job.annotated_video else None)
