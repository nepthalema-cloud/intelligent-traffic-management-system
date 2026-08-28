import os
import django
import unittest

# Ensure Django settings are available for importing app modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

loader = unittest.TestLoader()
suite = loader.discover('apps')

# Count tests recursively
def count_tests(s):
    try:
        return s.countTestCases()
    except Exception:
        total = 0
        for subs in s:
            total += count_tests(subs)
        return total

print('Discovered tests (apps/):', count_tests(suite))
for test in suite:
    print(test)
