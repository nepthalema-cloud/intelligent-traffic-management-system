"""
Tests for GET /api/v1/auth/me/

Covers:
- Unauthenticated access → 401
- Authenticated access → 200 with correct profile fields
- Password fields never present in response
- Roles reflected correctly from group membership
- URL routing correctness
- Response envelope shape matches common.responses.success_response
"""

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES, SYSTEM_ADMIN, TRAFFIC_ANALYST


def _jwt_client(user) -> APIClient:
    """Return an APIClient with a valid JWT Bearer token for *user*."""
    token = AccessToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestMeUrlRouting(TestCase):
    """Verify the me endpoint is wired at the expected URL."""

    def test_me_url_resolves(self):
        """resolve('/api/v1/auth/me/') must hit the MeView."""
        match = resolve("/api/v1/auth/me/")
        self.assertEqual(match.url_name, "me")
        self.assertEqual(match.namespace, "accounts")

    def test_me_url_reverses(self):
        """reverse('accounts:me') must return /api/v1/auth/me/."""
        self.assertEqual(reverse("accounts:me"), "/api/v1/auth/me/")


class TestMeUnauthenticated(TestCase):
    """Unauthenticated requests must be rejected."""

    def test_no_token_returns_401(self):
        """GET /api/v1/auth/me/ without a token must return HTTP 401."""
        client = APIClient()
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_returns_401(self):
        """GET /api/v1/auth/me/ with a malformed token must return HTTP 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not.a.real.token")
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_session_without_login_returns_401(self):
        """Bare unauthenticated client must receive HTTP 401."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)


class TestMeAuthenticated(TestCase):
    """Authenticated users receive their profile."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password="AlicePass123!",
        )
        self.client = _jwt_client(self.user)

    def test_authenticated_returns_200(self):
        """Authenticated request must return HTTP 200."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)

    def test_response_envelope_shape(self):
        """Response must follow the standard success_response envelope."""
        response = self.client.get("/api/v1/auth/me/")
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("message", data)
        self.assertIn("data", data)
        self.assertTrue(data["success"])

    def test_profile_fields_present(self):
        """Response data must include all expected profile fields."""
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        for field in ("id", "username", "email", "first_name", "last_name",
                      "is_active", "date_joined", "roles"):
            with self.subTest(field=field):
                self.assertIn(field, profile)

    def test_profile_values_correct(self):
        """Profile values must match the authenticated user's data."""
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        self.assertEqual(profile["username"], "alice")
        self.assertEqual(profile["email"], "alice@example.com")
        self.assertEqual(profile["first_name"], "Alice")
        self.assertEqual(profile["last_name"], "Smith")
        self.assertTrue(profile["is_active"])
        self.assertEqual(profile["id"], self.user.id)

    def test_password_never_in_response(self):
        """Password hash must never appear anywhere in the response."""
        response = self.client.get("/api/v1/auth/me/")
        response_text = response.content.decode()
        self.assertNotIn("password", response_text)
        self.assertNotIn("pbkdf2", response_text)

    def test_is_superuser_not_in_response(self):
        """is_superuser must not be exposed in the profile response."""
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        self.assertNotIn("is_superuser", profile)

    def test_is_staff_not_in_response(self):
        """is_staff must not be exposed in the profile response."""
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        self.assertNotIn("is_staff", profile)

    def test_roles_empty_for_user_with_no_groups(self):
        """User with no group membership must have an empty roles list."""
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        self.assertEqual(profile["roles"], [])

    def test_roles_reflect_group_membership(self):
        """Roles list must contain the names of the user's groups."""
        group, _ = Group.objects.get_or_create(name=TRAFFIC_ANALYST)
        self.user.groups.add(group)
        response = self.client.get("/api/v1/auth/me/")
        profile = response.json()["data"]
        self.assertIn(TRAFFIC_ANALYST, profile["roles"])

    def test_multiple_roles_returned(self):
        """Users with multiple group memberships must see all roles."""
        for role in [TRAFFIC_ANALYST, SYSTEM_ADMIN]:
            group, _ = Group.objects.get_or_create(name=role)
            self.user.groups.add(group)
        response = self.client.get("/api/v1/auth/me/")
        roles = response.json()["data"]["roles"]
        self.assertIn(TRAFFIC_ANALYST, roles)
        self.assertIn(SYSTEM_ADMIN, roles)
        self.assertEqual(len(roles), 2)

    def test_post_not_allowed(self):
        """POST to /api/v1/auth/me/ must return HTTP 405 Method Not Allowed."""
        response = self.client.post("/api/v1/auth/me/", data={})
        self.assertEqual(response.status_code, 405)

    def test_put_not_allowed(self):
        """PUT to /api/v1/auth/me/ must return HTTP 405 Method Not Allowed."""
        response = self.client.put("/api/v1/auth/me/", data={})
        self.assertEqual(response.status_code, 405)

    def test_patch_not_allowed(self):
        """PATCH to /api/v1/auth/me/ must return HTTP 405."""
        response = self.client.patch("/api/v1/auth/me/", data={})
        self.assertEqual(response.status_code, 405)

    def test_delete_not_allowed(self):
        """DELETE to /api/v1/auth/me/ must return HTTP 405."""
        response = self.client.delete("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 405)

    def test_superuser_can_access_me(self):
        """Superusers must also be able to access /api/v1/auth/me/."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        su = User.objects.create_superuser(
            username="superadmin", password="SuperPass123!"
        )
        client = _jwt_client(su)
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "superadmin")

    def test_each_user_sees_only_their_own_profile(self):
        """Two different users must each receive their own profile."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="BobPass123!"
        )
        bob_client = _jwt_client(bob)
        alice_response = self.client.get("/api/v1/auth/me/")
        bob_response = bob_client.get("/api/v1/auth/me/")
        self.assertEqual(alice_response.json()["data"]["username"], "alice")
        self.assertEqual(bob_response.json()["data"]["username"], "bob")
