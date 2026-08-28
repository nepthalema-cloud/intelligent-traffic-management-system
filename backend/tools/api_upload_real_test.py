import os
import time
import requests
from pathlib import Path

BASE = 'http://127.0.0.1:8000/api/v1'
TEST_VIDEO = Path(__file__).resolve().parents[2] / 'docker' / 'test_videos' / 'istockphoto-851692014-640_adpp_is.mp4'

if not TEST_VIDEO.exists():
    raise SystemExit(f'Test video not found: {TEST_VIDEO}')

creds = {'username': 'Admin', 'password': 'admin1234'}
print('Logging in...')
r = requests.post(f'{BASE}/auth/login/', json=creds, timeout=30)
print('login status', r.status_code)
print(r.text[:300])
if r.status_code != 200:
    raise SystemExit('Login failed')

access = r.json()['data']['access']
headers = {'Authorization': f'Bearer {access}'}

print('Uploading test video...')
with open(TEST_VIDEO, 'rb') as fh:
    files = {'file': (TEST_VIDEO.name, fh, 'video/mp4')}
    r = requests.post(f'{BASE}/cameras/upload-analysis/', headers=headers, files=files, timeout=120)
print('upload status', r.status_code)
print(r.text[:500])
if r.status_code != 201:
    raise SystemExit('Upload failed')
job_id = r.json()['data']['job_id']
print('job_id', job_id)

status = None
for attempt in range(1, 101):
    time.sleep(3)
    r = requests.get(f'{BASE}/cameras/upload-analysis/{job_id}/', headers=headers, timeout=30)
    if r.status_code != 200:
        print('status fetch failed', r.status_code, r.text[:300])
        continue
    data = r.json()['data']
    status = data['status']
    print(f'[{attempt}] status={status}, progress={data.get("result",{}).get("progress")}, stage={data.get("result",{}).get("stage")}')
    if status in ('done', 'failed'):
        break

if status != 'done':
    raise SystemExit(f'Job did not complete successfully, final status={status}')

print('Fetching download results...')
r = requests.get(f'{BASE}/cameras/upload-analysis/{job_id}/download/', headers=headers, timeout=60)
print('download status', r.status_code)
print(r.text[:1000])
if r.status_code != 200:
    raise SystemExit('Download fetch failed')

resp = r.json()['data']
print('annotated_video', resp.get('annotated_video'))
print('result keys', list(resp.get('result', {}).keys()))
full = resp.get('full_results')
print('full_results summary keys:', list(full.keys()) if isinstance(full, dict) else full)
print('snapshots', len(full.get('snapshots', [])) if isinstance(full, dict) else 'n/a')
print('vehicles', len(full.get('vehicles', [])) if isinstance(full, dict) else 'n/a')
print('violations', len(full.get('violations', [])) if isinstance(full, dict) else 'n/a')
