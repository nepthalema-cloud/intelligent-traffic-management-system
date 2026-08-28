import os, sys, importlib.util
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import django
django.setup()
from django.conf import settings
import importlib

for app in settings.INSTALLED_APPS:
    spec = importlib.util.find_spec(app)
    if spec is None:
        continue
    path = spec.submodule_search_locations[0] if spec.submodule_search_locations else os.path.dirname(spec.origin)
    tests_dir = os.path.join(path, 'tests')
    if os.path.exists(tests_dir):
        init_file = os.path.join(tests_dir, '__init__.py')
        print(app, 'tests_dir exists, __init__.py:', os.path.exists(init_file))
    else:
        print(app, 'no tests_dir')
