import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from apps.cameras.models import TemporaryVideoAnalysis

User = get_user_model()
user = User.objects.filter(username='Admin').first() or User.objects.filter(username='admin').first()
print('auth_user:', repr(user))
if not user:
    raise SystemExit('No admin user found')

job = TemporaryVideoAnalysis.objects.filter(pk=20).first()
print('job20:', job)
if job:
    print('job20 owner:', job.user.username, 'status:', job.status)

client = Client()
client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')
resp = client.get('/api/v1/cameras/upload-analysis/20/download/')
print('resp_status:', resp.status_code)
print('resp_content:', resp.content.decode('utf-8'))
print('resp_headers:', resp.items())

if resp.status_code == 200:
    import json
    print('parsed_json:', json.loads(resp.content.decode('utf-8')))
