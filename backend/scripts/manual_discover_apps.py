import os, sys, importlib.util
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import django
django.setup()
from django.conf import settings
import importlib
import unittest

loader = unittest.TestLoader()

for app in settings.INSTALLED_APPS:
    try:
        spec = importlib.util.find_spec(app)
        if spec is None:
            print(app, 'spec not found')
            continue
        path = None
        if spec.submodule_search_locations:
            path = spec.submodule_search_locations[0]
        else:
            # single file module
            path = os.path.dirname(spec.origin)
        tests_dir = os.path.join(path, 'tests')
        print('\nAPP:', app, 'path=', path, 'tests_dir=', tests_dir)
        if not os.path.exists(tests_dir):
            print('  tests_dir does not exist')
            continue
        suite = loader.discover(start_dir=tests_dir)
        print('  discovered tests:', suite.countTestCases())
    except Exception as e:
        print('  error discovering for app', app, e)
