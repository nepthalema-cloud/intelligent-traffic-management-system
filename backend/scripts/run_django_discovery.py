import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
# ensure project path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import django
django.setup()

from django.test.runner import DiscoverRunner

runner = DiscoverRunner(verbosity=2)
print('Running DiscoverRunner.build_suite()...')
suite = runner.build_suite([])
print('Suite type:', type(suite))
try:
    print('Total tests in suite:', suite.countTestCases())
except Exception as e:
    print('Error counting tests:', e)

# Optionally print names
for t in suite:
    try:
        print(t)
    except Exception:
        pass
