"""
Phase 3D.1 — JWT Security Hardening Tests.

Covers security properties that complement the existing functional tests:

1. Access-token lifetime: asserts exactly 15 minutes.
2. Refresh-token lifetime: asserts exactly 1 day.
3. Access token remains valid after logout (stateless JWT behaviour).
4. Refresh token is blacklisted after logout.
5. Complete rotation lifecycle: login → refresh → old-rejected → new-works → logout.
6. Inactive-user authentication rejection (explicit, comprehensive).
7. SECRET_KEY not exposed in any auth response.
8. No password hash in any auth response.
9. User-enumeration prevention: all auth failures return identical messages.
10. gitignore presence check (structural).
11. Production SECRET_KEY fail-fast guard logic (unit-tested without loading
    production settings, to avoid a real ImproperlyConfigured exception
    during the development test run).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()

LOGIN_URL  = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL  = "/api/v1/auth/logout/"
ME_URL      = "/api/v1/auth/me/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username, password="HardenPass123!", active=True):
    user = User.objects.create_user(username=username, password=password)
    if not active:
        user.is_active = False
        user.save()
    return user


def _login(username, password="HardenPass123!"):
    c = APIClient()
    return c.post(LOGIN_URL, {"username": username, "password": password}, format="json")


def _authed_client(user):
    token = AccessToken.for_user(user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return c


# ---------------------------------------------------------------------------
# 1. Token Lifetime Configuration
# ---------------------------------------------------------------------------

class TestTokenLifetimeConfiguration(TestCase):
    """
    Verify the JWT lifetime settings match the security decisions made
    in Phase 3D.1.

    Rationale for 15-minute access token:
    - System has sensitive roles: System Administrator, Law Enforcement,
      Traffic Control Officer.
    - Logout does not immediately invalidate access tokens (stateless JWTs).
    - A 15-minute window limits post-logout token exposure.
    - Refresh token rotation means clients remain logged in transparently.
    """

    def test_access_token_lifetime_is_15_minutes(self):
        """ACCESS_TOKEN_LIFETIME must be exactly timedelta(minutes=15)."""
        self.assertEqual(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            timedelta(minutes=15),
            "ACCESS_TOKEN_LIFETIME must be 15 minutes for this project's security profile.",
        )

    def test_refresh_token_lifetime_is_1_day(self):
        """REFRESH_TOKEN_LIFETIME must be exactly timedelta(days=1)."""
        self.assertEqual(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
            timedelta(days=1),
        )

    def test_access_token_shorter_than_refresh(self):
        """Access token must expire before refresh token."""
        self.assertLess(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
        )

    def test_access_token_under_30_minutes(self):
        """For security, access token must not exceed 30 minutes."""
        self.assertLessEqual(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            timedelta(minutes=30),
        )

    def test_rotate_refresh_tokens_enabled(self):
        self.assertTrue(settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"])

    def test_blacklist_after_rotation_enabled(self):
        self.assertTrue(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])

    def test_algorithm_is_hs256(self):
        self.assertEqual(settings.SIMPLE_JWT["ALGORITHM"], "HS256")

    def test_bearer_auth_header(self):
        self.assertIn("Bearer", settings.SIMPLE_JWT["AUTH_HEADER_TYPES"])

    def test_token_blacklist_app_installed(self):
        self.assertIn("rest_framework_simplejwt.token_blacklist", settings.INSTALLED_APPS)

    def test_access_token_lifetime_encoded_in_issued_token(self):
        """Token payload 'exp' must reflect the 15-minute lifetime."""
        import time
        user = _make_user("lifetimetest")
        token = AccessToken.for_user(user)
        issued_at = token["iat"]
        expires_at = token["exp"]
        duration_seconds = expires_at - issued_at
        # Allow ±5s tolerance for test execution time
        self.assertAlmostEqual(duration_seconds, 15 * 60, delta=5)

    def test_refresh_token_lifetime_encoded_in_issued_token(self):
        """Refresh token payload 'exp' must reflect the 1-day lifetime."""
        import time
        user = _make_user("refreshlifetime")
        token = RefreshToken.for_user(user)
        issued_at = token["iat"]
        expires_at = token["exp"]
        duration_seconds = expires_at - issued_at
        # Allow ±5s tolerance
        self.assertAlmostEqual(duration_seconds, 24 * 3600, delta=5)


# ---------------------------------------------------------------------------
# 2. Inactive User Authentication
# ---------------------------------------------------------------------------

class TestInactiveUserAuthentication(TestCase):
    """
    Verify that inactive users cannot obtain JWT tokens.

    The check is performed by Django's authenticate() called internally
    by TokenObtainPairSerializer.  LoginView catches all failure exceptions
    and returns a uniform 401.
    """

    def setUp(self):
        self.active_user   = _make_user("harden_active",   active=True)
        self.inactive_user = _make_user("harden_inactive", active=False)

    def test_active_user_can_login(self):
        resp = _login("harden_active")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access",  resp.json()["data"])
        self.assertIn("refresh", resp.json()["data"])

    def test_inactive_user_cannot_login(self):
        resp = _login("harden_inactive")
        self.assertEqual(resp.status_code, 401)

    def test_inactive_user_returns_success_false(self):
        resp = _login("harden_inactive")
        self.assertFalse(resp.json()["success"])

    def test_inactive_user_response_contains_no_tokens(self):
        body = _login("harden_inactive").json()
        data = body.get("data")
        self.assertFalse(data and "access" in str(data))

    def test_deactivated_user_cannot_login(self):
        """User deactivated after account creation must be rejected."""
        self.active_user.is_active = False
        self.active_user.save()
        resp = _login("harden_active")
        self.assertEqual(resp.status_code, 401)

    def test_reactivated_user_can_login_again(self):
        """Re-enabling a user account must restore login ability."""
        self.inactive_user.is_active = True
        self.inactive_user.save()
        resp = _login("harden_inactive")
        self.assertEqual(resp.status_code, 200)

    def test_inactive_login_message_matches_wrong_password(self):
        """Inactive user and wrong password must return identical messages."""
        inactive_msg = _login("harden_inactive").json()["message"]
        wrong_pw_msg = _login("harden_active", "WrongPassword!").json()["message"]
        self.assertEqual(inactive_msg, wrong_pw_msg,
                         "Inactive user and wrong-password responses must be identical "
                         "to prevent user-enumeration attacks.")

    def test_inactive_login_message_matches_nonexistent_user(self):
        """Inactive user and nonexistent user must return identical messages."""
        inactive_msg  = _login("harden_inactive").json()["message"]
        no_user_msg   = _login("nobody_xyz_123").json()["message"]
        self.assertEqual(inactive_msg, no_user_msg)


# ---------------------------------------------------------------------------
# 3. Logout Semantics — access token after logout
# ---------------------------------------------------------------------------

class TestLogoutSemantics(TestCase):
    """
    Document and verify the exact security behaviour of logout.

    BEFORE logout:
      access token  → valid  (authenticates requests)
      refresh token → valid  (can obtain new access token)

    AFTER logout:
      access token  → STILL VALID until its 15-minute natural expiry
                      (stateless JWT; cannot be revoked server-side)
      refresh token → BLACKLISTED (cannot obtain new access token)

    Clients MUST discard the access token immediately on logout.
    The 15-minute lifetime limits the post-logout exposure window.
    """

    def setUp(self):
        self.user = _make_user("logoutsemantic")
        resp = _login("logoutsemantic")
        data = resp.json()["data"]
        self.access  = data["access"]
        self.refresh = data["refresh"]

    def _me(self, access_token):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return c.get(ME_URL)

    def _logout(self, access_token, refresh_token):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return c.post(LOGOUT_URL, {"refresh": refresh_token}, format="json")

    def test_access_token_valid_before_logout(self):
        """Access token must authenticate /me/ before logout."""
        self.assertEqual(self._me(self.access).status_code, 200)

    def test_refresh_token_valid_before_logout(self):
        """Refresh token must produce a new access token before logout."""
        resp = APIClient().post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 200)
        # restore original refresh for logout test
        self.refresh = resp.json()["data"]["refresh"]
        self.access  = resp.json()["data"]["access"]

    def test_logout_returns_200(self):
        resp = self._logout(self.access, self.refresh)
        self.assertEqual(resp.status_code, 200)

    def test_refresh_token_blacklisted_after_logout(self):
        """Refresh token must be unusable after logout."""
        self._logout(self.access, self.refresh)
        resp = APIClient().post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_access_token_still_valid_after_logout(self):
        """
        Access token remains valid after logout because it cannot be
        revoked server-side (stateless JWT).

        This is EXPECTED behaviour — clients must discard the access token
        on logout.  The 15-minute lifetime limits the exposure window.
        """
        self._logout(self.access, self.refresh)
        # The access token was issued in the test, so it is still within
        # its 15-minute window — it must still authenticate /me/.
        resp = self._me(self.access)
        self.assertEqual(
            resp.status_code,
            200,
            "Access token is expected to remain valid after logout until natural expiry. "
            "This is a documented property of stateless JWTs. "
            "Clients must discard the access token immediately on logout.",
        )

    def test_logout_requires_authentication(self):
        """Logout without an access token must return 401."""
        resp = APIClient().post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_cannot_logout_twice_with_same_refresh(self):
        """Double logout with the same (now-blacklisted) refresh token must return 400."""
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        c.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        resp = c.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 4. Full Rotation Lifecycle
# ---------------------------------------------------------------------------

class TestRefreshRotationLifecycle(TestCase):
    """
    Verify the 10-step rotation lifecycle specified in Phase 3D.1:

    1.  Login.
    2.  Receive access + refresh tokens.
    3.  Refresh.
    4.  Confirm new refresh token is issued.
    5.  Confirm old refresh token is blacklisted.
    6.  Attempt reuse of old refresh token → rejected.
    7.  Confirm new refresh token works.
    8.  Logout using new refresh token.
    9.  Confirm new refresh token is blacklisted.
    10. Confirm access token still valid (stateless JWT).
    """

    def setUp(self):
        self.user = _make_user("rotationuser")

    def test_full_rotation_lifecycle(self):
        c = APIClient()

        # Step 1 + 2: Login, receive tokens
        resp = c.post(LOGIN_URL, {"username": "rotationuser", "password": "HardenPass123!"}, format="json")
        self.assertEqual(resp.status_code, 200, "Step 1: login failed")
        tokens = resp.json()["data"]
        access1  = tokens["access"]
        refresh1 = tokens["refresh"]
        self.assertTrue(access1,  "Step 2: access token absent")
        self.assertTrue(refresh1, "Step 2: refresh token absent")

        # Step 3: Refresh
        resp = c.post(REFRESH_URL, {"refresh": refresh1}, format="json")
        self.assertEqual(resp.status_code, 200, "Step 3: refresh failed")

        # Step 4: Confirm new refresh token issued
        new_data = resp.json()["data"]
        access2  = new_data["access"]
        refresh2 = new_data["refresh"]
        self.assertIn("refresh", new_data, "Step 4: new refresh token not present")
        self.assertNotEqual(refresh2, refresh1, "Step 4: refresh token was not rotated")

        # Step 5 + 6: Old refresh token must be blacklisted
        resp_old = c.post(REFRESH_URL, {"refresh": refresh1}, format="json")
        self.assertEqual(resp_old.status_code, 401,
                         "Steps 5+6: old refresh token was not blacklisted")

        # Step 7: New refresh token works
        resp = c.post(REFRESH_URL, {"refresh": refresh2}, format="json")
        self.assertEqual(resp.status_code, 200, "Step 7: new refresh token rejected")
        refresh3 = resp.json()["data"]["refresh"]
        access3  = resp.json()["data"]["access"]

        # Step 8: Logout using refresh3
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access3}")
        resp = c.post(LOGOUT_URL, {"refresh": refresh3}, format="json")
        self.assertEqual(resp.status_code, 200, "Step 8: logout failed")

        # Step 9: Refresh3 now blacklisted
        resp = APIClient().post(REFRESH_URL, {"refresh": refresh3}, format="json")
        self.assertEqual(resp.status_code, 401, "Step 9: refresh3 still valid after logout")

        # Step 10: Access token still valid (stateless JWT)
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {access3}")
        resp = c2.get(ME_URL)
        self.assertEqual(resp.status_code, 200,
                         "Step 10: access token expected valid within 15-min window")


# ---------------------------------------------------------------------------
# 5. Secret Not Exposed in Responses
# ---------------------------------------------------------------------------

class TestSecretsNotExposed(TestCase):
    """
    Verify that SECRET_KEY and password hashes never appear in API responses.
    """

    def setUp(self):
        self.user = _make_user("secrettest")

    def test_secret_key_not_in_login_response(self):
        content = _login("secrettest").content.decode()
        self.assertNotIn(settings.SECRET_KEY, content)

    def test_password_not_in_login_response(self):
        content = _login("secrettest").content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)

    def test_secret_key_not_in_refresh_response(self):
        refresh = _login("secrettest").json()["data"]["refresh"]
        resp = APIClient().post(REFRESH_URL, {"refresh": refresh}, format="json")
        self.assertNotIn(settings.SECRET_KEY, resp.content.decode())

    def test_secret_key_not_in_me_response(self):
        access = _login("secrettest").json()["data"]["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        content = c.get(ME_URL).content.decode()
        self.assertNotIn(settings.SECRET_KEY, content)

    def test_secret_key_not_in_logout_response(self):
        data    = _login("secrettest").json()["data"]
        access  = data["access"]
        refresh = data["refresh"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        content = c.post(LOGOUT_URL, {"refresh": refresh}, format="json").content.decode()
        self.assertNotIn(settings.SECRET_KEY, content)

    def test_algorithm_not_in_login_response(self):
        """JWT algorithm must not be echoed in API responses."""
        content = _login("secrettest").content.decode()
        # The token itself contains the algorithm in the header; we check
        # that it is not in the *decoded JSON body*, not the raw token.
        import json
        body = json.loads(content)
        self.assertNotIn("HS256", json.dumps(body.get("data", {})))


# ---------------------------------------------------------------------------
# 6. Production SECRET_KEY Fail-Fast Logic (unit test)
# ---------------------------------------------------------------------------

class TestProductionSecretKeyGuard(TestCase):
    """
    Unit-test the fail-fast logic that will be used in production.py
    without actually loading production settings (which would raise
    ImproperlyConfigured in the dev test run).

    We test the guard logic directly as a pure function.
    """

    def _validate(self, key):
        """Mirror the guard logic from production.py."""
        from django.core.exceptions import ImproperlyConfigured
        if not key:
            raise ImproperlyConfigured("SECRET_KEY not set")
        if key.startswith("django-insecure"):
            raise ImproperlyConfigured("Insecure SECRET_KEY")
        if len(key) < 50:
            raise ImproperlyConfigured(f"SECRET_KEY too short: {len(key)} chars")

    def test_empty_key_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            self._validate("")

    def test_insecure_prefix_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            self._validate("django-insecure-change-this-in-production")

    def test_short_key_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            self._validate("tooshort")

    def test_exactly_50_chars_passes(self):
        valid_key = "a" * 50
        self._validate(valid_key)  # must not raise

    def test_strong_key_passes(self):
        # A realistic strong key generated by get_random_secret_key()
        strong = "django-secure-x8!k@2m#p$q6&y9z0-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        self._validate(strong)  # must not raise

    def test_insecure_default_in_env_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            self._validate("django-insecure-change-this-in-production")

    def test_gitignore_contains_env_entry(self):
        """
        Verify .env is listed in .gitignore to prevent accidental secret commits.
        """
        import os
        gitignore_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../.gitignore",
        )
        gitignore_path = os.path.normpath(gitignore_path)
        self.assertTrue(
            os.path.exists(gitignore_path),
            ".gitignore file must exist at the project root.",
        )
        with open(gitignore_path, "r") as f:
            content = f.read()
        self.assertIn(".env", content,
                      ".env must be listed in .gitignore to prevent secret commits.")
