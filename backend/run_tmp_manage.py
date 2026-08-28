import os
import sys

# Ensure backend package is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

import django
django.setup()

# Execute processing helper
exec(open(os.path.join(os.path.dirname(__file__), 'tmp_run_process.py')).read())
