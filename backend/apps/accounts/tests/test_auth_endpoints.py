"""
Comprehensive tests for Phase 3D JWT authentication endpoints.

Endpoints under test
--------------------
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/

Also covers:
- Complete login → me → refresh → logout lifecycle
- Integration with existing /me/ and admin endpoints
- Regression: /api/v1/health/, routing, migrations, system check
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.roles import ALL_ROLES, TRAFFIC_ANALYST

User = get_user_model()

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ensure_groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _make_user(username, password="TestPass123!", active=True, **kwargs):
    user = User.objects.create_user(
        username=username, password=password, **kwargs
    )
    if not active:
        user.is_active = False
        user.save()
    return user


def _bearer(client: APIClient, token: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _login(username, password="TestPass123!") -> dict:
    """Perform login and return parsed JSON body."""
    c = APIClient()
    resp = c.post(LOGIN_URL, {"username": username, "password": password}, format="json")
    return resp


# ---------------------------------------------------------------------------
# 1. URL routing
# ---------------------------------------------------------------------------

class TestAuthUrlRouting(TestCase):
    def test_login_resolves(self):
        m = resolve(LOGIN_URL)
        self.assertEqual(m.url_name, "login")
        self.assertEqual(m.namespace, "accounts")

    def test_login_reverses(self):
        self.assertEqual(reverse("accounts:login"), LOGIN_URL)

    def test_refresh_resolves(self):
        m = resolve(REFRESH_URL)
        self.assertEqual(m.url_name, "refresh")

    def test_refresh_reverses(self):
        self.assertEqual(reverse("accounts:refresh"), REFRESH_URL)

    def test_logout_resolves(self):
        m = resolve(LOGOUT_URL)
        self.assertEqual(m.url_name, "logout")

    def test_logout_reverses(self):
        self.assertEqual(reverse("accounts:logout"), LOGOUT_URL)


# ---------------------------------------------------------------------------
# 2. Login — success cases
# ---------------------------------------------------------------------------

class TestLoginSuccess(TestCase):
    def setUp(self):
        self.user = _make_user("loginuser", email="login@example.com",
                               first_name="Login", last_name="User")

    def test_valid_credentials_return_200(self):
        resp = _login("loginuser")
        self.assertEqual(resp.status_code, 200)

    def test_response_envelope_shape(self):
        body = _login("loginuser").json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)
        self.assertIn("message", body)

    def test_access_token_present(self):
        data = _login("loginuser").json()["data"]
        self.assertIn("access", data)
        self.assertTrue(data["access"])

    def test_refresh_token_present(self):
        data = _login("loginuser").json()["data"]
        self.assertIn("refresh", data)
        self.assertTrue(data["refresh"])

    def test_password_not_in_response(self):
        content = _login("loginuser").content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)
        self.assertNotIn("argon2", content)

    def test_secret_key_not_in_response(self):
        from django.conf import settings as djsettings
        resp_content = _login("loginuser").content.decode()
        # SECRET_KEY must never appear in any response
        self.assertNotIn(djsettings.SECRET_KEY, resp_content)

    def test_access_token_authenticates_me(self):
        access = _login("loginuser").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = c.get(ME_URL)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["data"]["username"], "loginuser")

    def test_login_message(self):
        body = _login("loginuser").json()
        self.assertIn("Login", body["message"])


# ---------------------------------------------------------------------------
# 3. Login — failure and security cases
# ---------------------------------------------------------------------------

class TestLoginFailures(TestCase):
    def setUp(self):
        self.user = _make_user("authfailuser")
        self.inactive = _make_user("inactiveuser", active=False)

    def test_wrong_password_returns_401(self):
        resp = _login("authfailuser", "WrongPassword!")
        self.assertEqual(resp.status_code, 401)

    def test_nonexistent_username_returns_401(self):
        resp = _login("doesnotexist")
        self.assertEqual(resp.status_code, 401)

    def test_inactive_user_returns_401(self):
        resp = _login("inactiveuser")
        self.assertEqual(resp.status_code, 401)

    def test_empty_username_returns_401(self):
        resp = _login("", "TestPass123!")
        self.assertEqual(resp.status_code, 401)

    def test_empty_password_returns_401(self):
        c = APIClient()
        resp = c.post(LOGIN_URL, {"username": "authfailuser", "password": ""}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_missing_username_returns_401(self):
        c = APIClient()
        resp = c.post(LOGIN_URL, {"password": "TestPass123!"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_missing_password_returns_401(self):
        c = APIClient()
        resp = c.post(LOGIN_URL, {"username": "authfailuser"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_no_user_enumeration_wrong_password(self):
        """Wrong password and nonexistent user must return same message."""
        resp_bad_pw = _login("authfailuser", "WrongPass!").json()
        resp_no_user = _login("nobody_exists").json()
        self.assertEqual(resp_bad_pw["message"], resp_no_user["message"])

    def test_no_user_enumeration_inactive_vs_wrong(self):
        """Inactive user and nonexistent user must return same message."""
        resp_inactive = _login("inactiveuser").json()
        resp_no_user = _login("nobody_exists").json()
        self.assertEqual(resp_inactive["message"], resp_no_user["message"])

    def test_failure_response_has_success_false(self):
        body = _login("authfailuser", "wrong").json()
        self.assertFalse(body["success"])

    def test_failure_does_not_include_access_token(self):
        body = _login("authfailuser", "wrong").json()
        self.assertNotIn("access", str(body.get("data", "")))

    def test_get_not_allowed(self):
        resp = APIClient().get(LOGIN_URL)
        self.assertEqual(resp.status_code, 405)


# ---------------------------------------------------------------------------
# 4. Token Refresh
# ---------------------------------------------------------------------------

class TestRefreshView(TestCase):
    def setUp(self):
        self.user = _make_user("refreshuser")
        login_data = _login("refreshuser").json()["data"]
        self.access = login_data["access"]
        self.refresh = login_data["refresh"]

    def test_valid_refresh_returns_200(self):
        c = APIClient()
        resp = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_response_contains_new_access_token(self):
        c = APIClient()
        data = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json").json()["data"]
        self.assertIn("access", data)
        self.assertTrue(data["access"])

    def test_rotation_returns_new_refresh_token(self):
        """With ROTATE_REFRESH_TOKENS=True a new refresh token must be returned."""
        c = APIClient()
        data = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json").json()["data"]
        self.assertIn("refresh", data)
        self.assertNotEqual(data["refresh"], self.refresh)

    def test_old_refresh_token_is_blacklisted(self):
        """After rotation the original refresh token must be blacklisted."""
        c = APIClient()
        c.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        # Attempt to reuse the old refresh token
        resp2 = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp2.status_code, 401)

    def test_new_refresh_token_works(self):
        """The rotated refresh token must produce a valid new access token."""
        c = APIClient()
        new_refresh = c.post(
            REFRESH_URL, {"refresh": self.refresh}, format="json"
        ).json()["data"]["refresh"]
        resp = c.post(REFRESH_URL, {"refresh": new_refresh}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_new_access_token_authenticates_me(self):
        c = APIClient()
        new_access = c.post(
            REFRESH_URL, {"refresh": self.refresh}, format="json"
        ).json()["data"]["access"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        self.assertEqual(c.get(ME_URL).status_code, 200)

    def test_invalid_refresh_token_returns_401(self):
        c = APIClient()
        resp = c.post(REFRESH_URL, {"refresh": "not.a.real.token"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_missing_refresh_field_returns_401(self):
        resp = APIClient().post(REFRESH_URL, {}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_empty_refresh_field_returns_401(self):
        resp = APIClient().post(REFRESH_URL, {"refresh": ""}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_response_envelope_shape(self):
        c = APIClient()
        body = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json").json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)
        self.assertIn("message", body)

    def test_password_not_in_response(self):
        c = APIClient()
        content = c.post(REFRESH_URL, {"refresh": self.refresh}, format="json").content.decode()
        self.assertNotIn("password", content)

    def test_get_not_allowed(self):
        self.assertEqual(APIClient().get(REFRESH_URL).status_code, 405)


# ---------------------------------------------------------------------------
# 5. Logout
# ---------------------------------------------------------------------------

class TestLogoutView(TestCase):
    def setUp(self):
        self.user = _make_user("logoutuser")
        login_data = _login("logoutuser").json()["data"]
        self.access = login_data["access"]
        self.refresh = login_data["refresh"]

    def _authed_client(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        return c

    def test_logout_returns_200(self):
        resp = self._authed_client().post(
            LOGOUT_URL, {"refresh": self.refresh}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_logout_response_envelope(self):
        body = self._authed_client().post(
            LOGOUT_URL, {"refresh": self.refresh}, format="json"
        ).json()
        self.assertTrue(body["success"])
        self.assertIn("Logged out", body["message"])

    def test_refresh_token_blacklisted_after_logout(self):
        self._authed_client().post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        # Attempt to use the refresh token again
        resp = APIClient().post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_blacklisted_token_cannot_be_used_twice(self):
        c = self._authed_client()
        c.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        # Second logout with the already-blacklisted token
        resp = c.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_logout_returns_401(self):
        resp = APIClient().post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_invalid_refresh_token_returns_400(self):
        resp = self._authed_client().post(
            LOGOUT_URL, {"refresh": "bad.token.here"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_refresh_field_returns_400(self):
        resp = self._authed_client().post(LOGOUT_URL, {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_password_not_in_logout_response(self):
        content = self._authed_client().post(
            LOGOUT_URL, {"refresh": self.refresh}, format="json"
        ).content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)

    def test_token_not_in_logout_response(self):
        """The blacklisted token value must not echo back in the response."""
        body = self._authed_client().post(
            LOGOUT_URL, {"refresh": self.refresh}, format="json"
        ).json()
        self.assertIsNone(body.get("data"))

    def test_get_not_allowed(self):
        self.assertEqual(self._authed_client().get(LOGOUT_URL).status_code, 405)


# ---------------------------------------------------------------------------
# 6. Full lifecycle integration tests
# ---------------------------------------------------------------------------

class TestAuthLifecycle(TestCase):
    """
    End-to-end lifecycle tests covering the complete authentication flow.
    """
    def setUp(self):
        _ensure_groups()
        self.user = _make_user("lifecycleuser", email="lc@example.com")

    def test_login_then_me(self):
        """Tokens from login must authenticate /me/ and return correct user."""
        login_resp = _login("lifecycleuser")
        self.assertEqual(login_resp.status_code, 200)
        access = login_resp.json()["data"]["access"]

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = c.get(ME_URL)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["data"]["username"], "lifecycleuser")

    def test_login_then_refresh_then_me(self):
        """Rotated access token from refresh must still authenticate /me/."""
        access1 = _login("lifecycleuser").json()["data"]["access"]
        refresh1 = _login("lifecycleuser").json()["data"]["refresh"]

        c = APIClient()
        new_tokens = c.post(REFRESH_URL, {"refresh": refresh1}, format="json").json()["data"]
        new_access = new_tokens["access"]

        c.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        self.assertEqual(c.get(ME_URL).status_code, 200)

    def test_logout_blacklists_refresh(self):
        """After logout the refresh token must be unusable."""
        data = _login("lifecycleuser").json()["data"]
        access, refresh = data["access"], data["refresh"]

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_resp = c.post(LOGOUT_URL, {"refresh": refresh}, format="json")
        self.assertEqual(logout_resp.status_code, 200)

        # Refresh token must now be blacklisted
        refresh_resp = APIClient().post(REFRESH_URL, {"refresh": refresh}, format="json")
        self.assertEqual(refresh_resp.status_code, 401)

    def test_access_token_claims_contain_user_id(self):
        """The access token payload must contain the user's ID."""
        from rest_framework_simplejwt.tokens import AccessToken as AT
        from django.conf import settings as djsettings
        data = _login("lifecycleuser").json()["data"]
        token = AT(data["access"])
        claim = djsettings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
        self.assertEqual(str(token[claim]), str(self.user.id))

    def test_roles_reflected_after_login(self):
        """After assigning a role, /me/ must reflect it on next request."""
        self.user.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        access = _login("lifecycleuser").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        roles = c.get(ME_URL).json()["data"]["roles"]
        self.assertIn(TRAFFIC_ANALYST, roles)

    def test_inactive_user_cannot_refresh_after_deactivation(self):
        """
        A user deactivated between login and refresh cannot obtain new tokens.
        SimpleJWT checks is_active on token validation when
        USER_AUTHENTICATION_RULE is configured.  For basic coverage we verify
        that login fails after deactivation (future: check refresh behaviour
        if USER_AUTHENTICATION_RULE is enabled).
        """
        # Deactivate the user
        self.user.is_active = False
        self.user.save()
        resp = _login("lifecycleuser")
        self.assertEqual(resp.status_code, 401)

    def test_multiple_users_get_independent_tokens(self):
        """Tokens for one user must not authenticate as another user."""
        user2 = _make_user("lifecycleuser2")
        access1 = _login("lifecycleuser").json()["data"]["access"]
        access2 = _login("lifecycleuser2").json()["data"]["access"]

        c1 = APIClient(); c1.credentials(HTTP_AUTHORIZATION=f"Bearer {access1}")
        c2 = APIClient(); c2.credentials(HTTP_AUTHORIZATION=f"Bearer {access2}")

        self.assertEqual(c1.get(ME_URL).json()["data"]["username"], "lifecycleuser")
        self.assertEqual(c2.get(ME_URL).json()["data"]["username"], "lifecycleuser2")


# ---------------------------------------------------------------------------
# 7. Integration with existing admin endpoints
# ---------------------------------------------------------------------------

class TestAuthIntegrationWithAdmin(TestCase):
    """Login-obtained tokens must work with existing admin endpoints."""

    def setUp(self):
        _ensure_groups()
        from django.contrib.auth.models import Group as G
        self.admin = _make_user("intadmin")
        self.admin.groups.add(G.objects.get(name="System Administrator"))
        self.target = _make_user("inttarget")

    def test_login_token_accesses_user_list(self):
        access = _login("intadmin").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = c.get("/api/v1/auth/users/")
        self.assertEqual(resp.status_code, 200)

    def test_login_token_accesses_user_detail(self):
        access = _login("intadmin").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = c.get(f"/api/v1/auth/users/{self.target.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_login_token_can_assign_role(self):
        access = _login("intadmin").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = c.post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_login_token_rejected_from_admin_endpoint(self):
        regular = _make_user("intregular")
        access = _login("intregular").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = c.get("/api/v1/auth/users/")
        self.assertEqual(resp.status_code, 403)

    def test_refreshed_token_still_accesses_admin_endpoints(self):
        data = _login("intadmin").json()["data"]
        c = APIClient()
        new_tokens = c.post(REFRESH_URL, {"refresh": data["refresh"]}, format="json").json()["data"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {new_tokens['access']}")
        self.assertEqual(c.get("/api/v1/auth/users/").status_code, 200)


# ---------------------------------------------------------------------------
# 8. Regression tests
# ---------------------------------------------------------------------------

class TestPhase3DRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_endpoint_200(self):
        resp = APIClient().get("/api/v1/health/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "traffic-management-backend")

    def test_old_health_url_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_health_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_me_unauthenticated_401(self):
        self.assertEqual(APIClient().get(ME_URL).status_code, 401)

    def test_me_url_unchanged(self):
        self.assertEqual(reverse("accounts:me"), ME_URL)

    def test_login_url_correct(self):
        self.assertEqual(reverse("accounts:login"), LOGIN_URL)

    def test_refresh_url_correct(self):
        self.assertEqual(reverse("accounts:refresh"), REFRESH_URL)

    def test_logout_url_correct(self):
        self.assertEqual(reverse("accounts:logout"), LOGOUT_URL)

    def test_django_system_check_passes(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("check", stdout=out, stderr=out)
        self.assertIn("no issues", out.getvalue().lower())

    def test_no_pending_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending migrations found: {plan}")

    def test_admin_accessible(self):
        resp = APIClient().get("/admin/")
        self.assertIn(resp.status_code, [200, 301, 302])
