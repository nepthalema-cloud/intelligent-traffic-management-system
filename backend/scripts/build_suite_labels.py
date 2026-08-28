import os,sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.test.runner import DiscoverRunner
runner = DiscoverRunner(verbosity=1)
labels = ['apps.accounts','apps.audit','apps.roads','apps.cameras','apps.organizations','apps.drivers','apps.fines','apps.notifications']
for label in labels:
    try:
        suite = runner.build_suite([label])
        print(label, '->', suite.countTestCases())
    except Exception as e:
        print('error building',label,e)
