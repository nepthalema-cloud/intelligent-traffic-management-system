import os,sys,importlib,importlib.util
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner

print('cwd=', os.getcwd())
print('sys.path[0:5]=', sys.path[:5])
print('INSTALLED_APPS count=', len(settings.INSTALLED_APPS))

runner = DiscoverRunner(verbosity=1)
loader = runner.test_loader

for app in settings.INSTALLED_APPS:
    try:
        spec = importlib.util.find_spec(app)
        if spec is None:
            print('\nAPP:', app, 'spec not found')
            continue
        if spec.submodule_search_locations:
            path = spec.submodule_search_locations[0]
        else:
            path = os.path.dirname(spec.origin)
        tests_dir = os.path.join(path, 'tests')
        print('\nAPP:', app)
        print('  app path:', path)
        print('  tests_dir:', tests_dir, 'exists?', os.path.exists(tests_dir))
        if not os.path.exists(tests_dir):
            continue
        # list test files
        files = [f for f in sorted(os.listdir(tests_dir)) if f.endswith('.py') or os.path.isdir(os.path.join(tests_dir,f))]
        print('  test files:', files[:30])
        # attempt discovery and capture sys.modules snapshot
        before = set(sys.modules.keys())
        try:
            suite = loader.discover(start_dir=tests_dir)
            print('  discovered:', suite.countTestCases())
        except Exception as e:
            print('  discover error:', type(e), e)
            # inspect modules loaded that match test filenames
            after = set(sys.modules.keys())
            newmods = after - before
            print('  new modules loaded count:', len(newmods))
            test_mod_names = [os.path.splitext(f)[0] for f in files if f.endswith('.py')]
            collisions = []
            for nm in test_mod_names:
                if nm in sys.modules:
                    m = sys.modules[nm]
                    collisions.append((nm, getattr(m,'__file__',None), getattr(m,'__package__',None)))
            if collisions:
                print('  possible collisions (module_name, __file__, __package__):')
                for c in collisions:
                    print('   -', c)
            else:
                print('  no direct simple-name collisions')
    except Exception as e:
        print('  error inspecting app', app, e)
