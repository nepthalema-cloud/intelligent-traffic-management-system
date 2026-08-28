import os,sys,importlib,importlib.util
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import django
django.setup()
from django.conf import settings
print('TEST_RUNNER:', getattr(settings,'TEST_RUNNER',None))
print('TEST_DISCOVER_TOP_LEVEL:', getattr(settings,'TEST_DISCOVER_TOP_LEVEL',None))
print('TEST_DISCOVER_PATTERN:', getattr(settings,'TEST_DISCOVER_PATTERN',None))
print('INSTALLED_APPS count:', len(settings.INSTALLED_APPS))

from django.test.runner import DiscoverRunner
runner = DiscoverRunner(verbosity=1)
loader = runner.test_loader
print('runner.loader type:', type(loader))

for app in settings.INSTALLED_APPS:
    try:
        spec = importlib.util.find_spec(app)
        if spec is None:
            print(app, 'spec None')
            continue
        if spec.submodule_search_locations:
            path = spec.submodule_search_locations[0]
        else:
            path = os.path.dirname(spec.origin)
        tests_dir = os.path.join(path,'tests')
        if not os.path.exists(tests_dir):
            print(app, 'no tests_dir')
            continue
        print('Attempt discover in',tests_dir)
        try:
            suite = loader.discover(start_dir=tests_dir)
            print('  discovered',suite.countTestCases())
        except Exception as e:
            print('  loader.discover error:', type(e), e)
    except Exception as e:
        print('  error inspecting app', app, type(e), e)
