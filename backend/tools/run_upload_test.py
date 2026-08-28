"""Run a programmatic upload test: create TemporaryVideoAnalysis from a test video
and run the `process_video_job` to exercise the shared detector loader end-to-end.

Usage: run from repo root with PYTHONPATH including project root and
DJANGO_SETTINGS_MODULE=config.settings set.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Ensure backend (where `config` package lives) is on sys.path first
BACKEND_PATH = PROJECT_ROOT
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)
# Also ensure repo root is available for other imports
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.files import File
from django.conf import settings
from apps.cameras.models import TemporaryVideoAnalysis
from apps.cameras.video_processor import process_video_job

TEST_VIDEO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docker', 'test_videos', 'istockphoto-851692014-640_adpp_is.mp4')

def main():
    if not os.path.exists(TEST_VIDEO):
        print('Test video not found:', TEST_VIDEO)
        return

    # Ensure a valid user exists to own the upload
    from apps.accounts.models import User
    user = User.objects.first()
    if user is None:
        user = User.objects.create_user(username='upload_test_user', email='test@example.com', password='testpass')

    with open(TEST_VIDEO, 'rb') as fh:
        django_file = File(fh, name=os.path.basename(TEST_VIDEO))
        job = TemporaryVideoAnalysis.objects.create(
            user=user,
            original_filename=os.path.basename(TEST_VIDEO),
            upload=django_file,
            status=TemporaryVideoAnalysis.STATUS_PENDING,
        )

    print('Created TemporaryVideoAnalysis job id=', job.pk)
    try:
        process_video_job(job, meters_per_pixel=None)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print('Processing failed:', exc)
        return

    job.refresh_from_db()
    print('Processing finished. status=', job.status)
    print('Result JSON keys:', list((job.result_json or {}).keys()))
    if job.annotated_video:
        print('Annotated video saved at:', job.annotated_video.path)

if __name__ == '__main__':
    main()
