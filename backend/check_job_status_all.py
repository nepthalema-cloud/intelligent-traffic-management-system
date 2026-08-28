import os
from django.conf import settings
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.cameras.models import TemporaryVideoAnalysis

for job in TemporaryVideoAnalysis.objects.all().order_by('-pk')[:10]:
    print('JOB', job.pk, 'status=', job.status)
    print('  filename=', job.original_filename)
    print('  annotated=', job.annotated_video.name)
    print('  result keys=', list((job.result_json or {}).keys()))
    print('  result stage=', (job.result_json or {}).get('stage'))
    print('  result progress=', (job.result_json or {}).get('progress'))
    print('  has pdf=', bool((job.result_json or {}).get('pdf_file')))
    print('  has csv=', bool((job.result_json or {}).get('csv_file')))
    print('  has results=', bool((job.result_json or {}).get('results_file')))
    print()
