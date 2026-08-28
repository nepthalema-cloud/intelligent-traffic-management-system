from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.drivers.models import Driver


def _jwt_client(user) -> APIClient:
    token = AccessToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestDriverSearch(TestCase):
    def setUp(self):
        User = get_user_model()
        # ensure role exists
        Group.objects.get_or_create(name="System Administrator")
        self.user = User.objects.create_user(username="admin", password="pass")
        self.user.groups.add(Group.objects.get(name="System Administrator"))
        self.client = _jwt_client(self.user)

        Driver.objects.create(first_name="Alice", last_name="Smith", license_number="ABC123", license_status="active", license_issue_date="2000-01-01", license_expiry_date="2030-01-01")
        Driver.objects.create(first_name="Bob", last_name="Jones", license_number="XYZ789", license_status="active", license_issue_date="2000-01-01", license_expiry_date="2030-01-01")

    def test_search_by_license_number_exact(self):
        resp = self.client.get("/api/v1/drivers/?license_number=abc123")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("results"))
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["license_number"], "ABC123")

    def test_search_by_query_matches_name(self):
        resp = self.client.get("/api/v1/drivers/?q=alice")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["first_name"], "Alice")
