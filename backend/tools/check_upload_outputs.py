"""Verify Video Analysis upload outputs for the latest TemporaryVideoAnalysis job."""
import os
import sys

BACKEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from apps.cameras.models import TemporaryVideoAnalysis

job = TemporaryVideoAnalysis.objects.order_by('-pk').first()
if job is None:
    print('No TemporaryVideoAnalysis jobs found')
    sys.exit(1)

print('job_id:', job.pk)
print('status:', job.status)
print('result_json keys:', list((job.result_json or {}).keys()))

if job.annotated_video:
    print('annotated_video path:', job.annotated_video.path)
else:
    print('annotated_video: None')

out_dir = None
if job.annotated_video:
    out_dir = os.path.dirname(job.annotated_video.path)

files = {}
if out_dir:
    files['annotated_video'] = os.path.exists(job.annotated_video.path)
    files['json'] = os.path.exists(os.path.join(out_dir, f'results_{job.pk}.json'))
    files['csv'] = os.path.exists(os.path.join(out_dir, f'results_{job.pk}.csv'))
    files['pdf'] = os.path.exists(os.path.join(out_dir, f'report_{job.pk}.pdf'))
else:
    files['annotated_video'] = False
    files['json'] = False
    files['csv'] = False
    files['pdf'] = False

for name, exists in files.items():
    print(f'{name}:', exists)

if out_dir:
    print('out_dir:', out_dir)
    print('dir listing:')
    for name in sorted(os.listdir(out_dir)):
        print(' ', name)
