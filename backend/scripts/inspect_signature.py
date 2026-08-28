import inspect
from django.test.runner import DiscoverRunner
print('DiscoverRunner.build_suite signature:', inspect.signature(DiscoverRunner.build_suite))
print('DiscoverRunner.build_suite doc:', DiscoverRunner.build_suite.__doc__)
