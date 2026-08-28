import os
from django.conf import settings
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.cameras.models import TemporaryVideoAnalysis

job_id = 15
try:
    job = TemporaryVideoAnalysis.objects.get(pk=job_id)
    print('JOB', job.pk, 'status=', job.status)
    print('RESULT KEYS', list((job.result_json or {}).keys()))
    print('ANNOTATED NAME', job.annotated_video.name)
    base = os.path.abspath('.')
    media = os.path.join(base, 'media')
    for filename in [
        os.path.join('uploads', 'tmp_videos', '2026', '08', '05', 'annotated', f'annotated_{job_id}.mp4'),
        os.path.join('uploads', 'tmp_videos', '2026', '08', '05', f'results_{job_id}.json'),
        os.path.join('uploads', 'tmp_videos', '2026', '08', '05', f'results_{job_id}.csv'),
        os.path.join('uploads', 'tmp_videos', '2026', '08', '05', f'report_{job_id}.pdf'),
    ]:
        path = os.path.join(media, filename)
        print(filename, 'exists=', os.path.exists(path), 'size=', os.path.getsize(path) if os.path.exists(path) else 'N/A')
except Exception as exc:
    print('ERROR', exc)
