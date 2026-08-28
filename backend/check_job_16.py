import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.cameras.models import TemporaryVideoAnalysis

job = TemporaryVideoAnalysis.objects.get(pk=16)
print('JOB', job.pk, 'status=', job.status)
print('annotated', job.annotated_video.name if job.annotated_video else None)
print('result_json:', job.result_json)
print('result keys', list((job.result_json or {}).keys()))
print('csv', job.result_json.get('csv_file'))
print('pdf', job.result_json.get('pdf_file'))
print('results', job.result_json.get('results_file'))
print('exists annotated', os.path.exists(os.path.join(settings.MEDIA_ROOT, job.annotated_video.name)) if job.annotated_video else False)
for key in ['csv_file', 'pdf_file', 'results_file']:
    val = job.result_json.get(key)
    if val:
        path = os.path.join(settings.MEDIA_ROOT, val)
        print(key, 'path=', path, 'exists=', os.path.exists(path))
