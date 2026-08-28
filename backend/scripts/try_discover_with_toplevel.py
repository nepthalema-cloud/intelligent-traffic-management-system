import os,sys,importlib,importlib.util
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner
runner = DiscoverRunner()
loader = runner.test_loader
BASE_DIR = settings.BASE_DIR
apps = ['apps.cameras','apps.traffic','apps.violations','apps.analytics','apps.organizations','apps.drivers','apps.fines','apps.notifications']
for app in apps:
    spec = importlib.util.find_spec(app)
    if not spec:
        print(app,'spec missing')
        continue
    path = spec.submodule_search_locations[0] if spec.submodule_search_locations else os.path.dirname(spec.origin)
    tests_dir = os.path.join(path,'tests')
    print('\nAPP',app,'tests_dir',tests_dir)
    for top in [None,str(BASE_DIR), os.path.dirname(tests_dir)]:
        try:
            if top:
                suite = loader.discover(start_dir=tests_dir, top_level_dir=top)
            else:
                suite = loader.discover(start_dir=tests_dir)
            print(' top_level=', top, '-> discovered', suite.countTestCases())
        except Exception as e:
            print(' top_level=', top, '-> error', type(e), e)
