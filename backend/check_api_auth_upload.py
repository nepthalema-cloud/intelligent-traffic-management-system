import requests
import sys

base = 'http://127.0.0.1:8000/api/v1'

try:
    r = requests.get(base, timeout=10)
    print('GET /api/v1', r.status_code)
except Exception as exc:
    print('GET /api/v1 failed', repr(exc))
    sys.exit(1)

creds = {'username': 'Admin', 'password': 'admin1234'}

try:
    r = requests.post(base + '/auth/login/', json=creds, timeout=15)
    print('login', r.status_code, r.text[:200])
    if r.status_code != 200:
        sys.exit(1)
    tok = r.json().get('data', {}).get('access')
    if not tok:
        print('Missing access token')
        sys.exit(1)
    headers = {'Authorization': f'Bearer {tok}'}
    r2 = requests.get(base + '/auth/me/', headers=headers, timeout=15)
    print('auth/me', r2.status_code, r2.text[:200])
    r3 = requests.post(base + '/cameras/upload-analysis/', headers=headers, files={'file': ('test.mp4', b'0123', 'video/mp4')}, timeout=30)
    print('upload-analysis post', r3.status_code, r3.text[:200])
except Exception as exc:
    print('auth/upload failed', repr(exc))
    sys.exit(1)
