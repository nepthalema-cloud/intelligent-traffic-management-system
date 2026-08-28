import os,sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.test.utils import get_runner
from django.conf import settings
Runner = get_runner(settings)
runner = Runner()
suite = runner.build_suite([])
print('Discovered test count:', suite.countTestCases())
