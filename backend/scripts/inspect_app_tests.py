import importlib
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
# Ensure project path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import django
django.setup()

from django.conf import settings

print('INSTALLED_APPS count:', len(settings.INSTALLED_APPS))

failures = []
for app in settings.INSTALLED_APPS:
    mod_name = f"{app}.tests"
    try:
        m = importlib.import_module(mod_name)
        print(f"OK: imported {mod_name} -> {getattr(m, '__file__', None)}")
    except Exception as e:
        print(f"FAIL: importing {mod_name} -> {e.__class__.__name__}: {e}")
        failures.append((mod_name, e))

print('\nTotal failures:', len(failures))
if failures:
    for mod, err in failures:
        print(mod, 'error type', type(err))
