"""
Tests verifying the health endpoint is unaffected by auth architecture changes.

The health endpoint must remain accessible without authentication even
after JWT is set as the default authentication class.
"""

from django.test import TestCase
from django.urls import resolve, reverse


class TestHealthEndpointUnchanged(TestCase):
    """Regression guard: health endpoint must remain at /api/v1/health/."""

    def test_health_url_resolves(self):
        """resolve('/api/v1/health/') must return the health_check view."""
        match = resolve("/api/v1/health/")
        self.assertEqual(match.url_name, "health_check")
        self.assertEqual(match.namespace, "core")

    def test_health_url_reverses(self):
        """reverse('core:health_check') must return /api/v1/health/."""
        url = reverse("core:health_check")
        self.assertEqual(url, "/api/v1/health/")

    def test_health_endpoint_returns_200(self):
        """GET /api/v1/health/ must return HTTP 200 without authentication."""
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_response_body(self):
        """Health endpoint response body must match expected JSON."""
        response = self.client.get("/api/v1/health/")
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "traffic-management-backend")

    def test_auth_url_namespace_exists(self):
        """The accounts URL namespace must be wired and resolvable."""
        # Importing the URL conf should not raise
        from django.urls import get_resolver
        resolver = get_resolver()
        # Verify api/v1/auth/ is in the URL tree
        namespaces = [
            ns
            for ns, _ in resolver.namespace_dict.items()
        ]
        # The top-level resolver may not expose nested namespaces directly;
        # verify by attempting a simple inclusion lookup without errors
        from django.urls import get_urlconf
        import importlib
        urlconf = importlib.import_module("config.api")
        patterns = urlconf.urlpatterns
        pattern_strs = [str(p.pattern) for p in patterns]
        self.assertTrue(
            any("auth" in s for s in pattern_strs),
            "auth/ route not found in config.api urlpatterns",
        )
