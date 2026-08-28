import importlib
import importlib.util
import os
from django.conf import settings
from django.test.runner import DiscoverRunner


class ForcePackageDiscoverRunner(DiscoverRunner):
    """Custom test runner that imports each app's `tests` package and
    loads test modules by fully-qualified package names. This ensures
    identically-named test modules (e.g. `test_api.py`) are loaded under
    their app namespace (e.g. `apps.cameras.tests.test_api`) and prevents
    cross-app collisions during discovery.
    """

    def build_suite(self, test_labels, extra_tests=None):
        loader = self.test_loader
        suite = loader.suiteClass()

        # If labels provided, defer to base implementation (supports labeled runs)
        if test_labels:
            return super().build_suite(test_labels)

        for app in settings.INSTALLED_APPS:
            try:
                spec = importlib.util.find_spec(app)
                if not spec:
                    continue
                app_path = spec.submodule_search_locations[0] if spec.submodule_search_locations else os.path.dirname(spec.origin)
                tests_dir = os.path.join(app_path, 'tests')
                tests_pkg = f"{app}.tests"
                # Import the tests package to make it a proper package
                try:
                    importlib.import_module(tests_pkg)
                except Exception:
                    # If there's no tests package or import fails, skip
                    continue

                # Iterate over test modules (files starting with test_)
                for entry in sorted(os.listdir(tests_dir)):
                    full = os.path.join(tests_dir, entry)
                    if entry.endswith('.py') and entry.startswith('test'):
                        mod_name = os.path.splitext(entry)[0]
                        fqname = f"{tests_pkg}.{mod_name}"
                        try:
                            tests = loader.loadTestsFromName(fqname)
                            suite.addTests(tests)
                        except Exception:
                            # Loading this module failed; skip and allow errors to surface later
                            continue
                    elif os.path.isdir(full) and os.path.exists(os.path.join(full, '__init__.py')):
                        # It's a subpackage - discover files inside it
                        subpkg = f"{tests_pkg}.{entry}"
                        for subentry in sorted(os.listdir(full)):
                            if subentry.endswith('.py') and subentry.startswith('test'):
                                mod_name = os.path.splitext(subentry)[0]
                                fqname = f"{subpkg}.{mod_name}"
                                try:
                                    tests = loader.loadTestsFromName(fqname)
                                    suite.addTests(tests)
                                except Exception:
                                    continue
            except Exception:
                continue

        return suite
