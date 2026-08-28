"""
Tests for JWT configuration and SimpleJWT integration.
"""

from django.conf import settings
from django.test import TestCase


class TestJWTConfiguration(TestCase):
    """Verify SIMPLE_JWT settings are configured correctly."""

    def setUp(self):
        self.jwt = settings.SIMPLE_JWT

    def test_access_token_lifetime_is_set(self):
        """ACCESS_TOKEN_LIFETIME must be a timedelta of exactly 15 minutes."""
        from datetime import timedelta
        self.assertIn("ACCESS_TOKEN_LIFETIME", self.jwt)
        lifetime = self.jwt["ACCESS_TOKEN_LIFETIME"]
        self.assertIsInstance(lifetime, timedelta)
        self.assertEqual(
            lifetime,
            timedelta(minutes=15),
            f"ACCESS_TOKEN_LIFETIME should be 15 minutes for this project's "
            f"security profile (admin/law-enforcement roles). Got: {lifetime}",
        )

    def test_refresh_token_lifetime_is_set(self):
        """REFRESH_TOKEN_LIFETIME must be a timedelta of exactly 1 day."""
        from datetime import timedelta
        self.assertIn("REFRESH_TOKEN_LIFETIME", self.jwt)
        lifetime = self.jwt["REFRESH_TOKEN_LIFETIME"]
        self.assertIsInstance(lifetime, timedelta)
        self.assertEqual(
            lifetime,
            timedelta(days=1),
            f"REFRESH_TOKEN_LIFETIME should be 1 day. Got: {lifetime}",
        )

    def test_access_token_shorter_than_refresh(self):
        """Access token lifetime must be shorter than refresh token lifetime."""
        self.assertLess(
            self.jwt["ACCESS_TOKEN_LIFETIME"],
            self.jwt["REFRESH_TOKEN_LIFETIME"],
        )

    def test_access_token_lifetime_under_30_minutes(self):
        """
        For a system with sensitive admin roles, access token lifetime
        must not exceed 30 minutes to limit exposure after logout.
        """
        from datetime import timedelta
        lifetime = self.jwt["ACCESS_TOKEN_LIFETIME"]
        self.assertLessEqual(
            lifetime,
            timedelta(minutes=30),
            "ACCESS_TOKEN_LIFETIME must be ≤ 30 minutes for this security profile.",
        )

    def test_rotate_refresh_tokens_enabled(self):
        """Refresh token rotation must be enabled."""
        self.assertTrue(self.jwt.get("ROTATE_REFRESH_TOKENS"))

    def test_blacklist_after_rotation_enabled(self):
        """Token blacklisting after rotation must be enabled."""
        self.assertTrue(self.jwt.get("BLACKLIST_AFTER_ROTATION"))

    def test_algorithm_is_hs256(self):
        """Algorithm must be HS256."""
        self.assertEqual(self.jwt.get("ALGORITHM"), "HS256")

    def test_bearer_auth_header(self):
        """AUTH_HEADER_TYPES must include Bearer."""
        self.assertIn("Bearer", self.jwt.get("AUTH_HEADER_TYPES", ()))

    def test_signing_key_is_configured(self):
        """SIGNING_KEY must be present and non-empty."""
        key = self.jwt.get("SIGNING_KEY", "")
        self.assertTrue(key, "SIGNING_KEY must not be empty")

    def test_token_blacklist_app_installed(self):
        """token_blacklist app must be in INSTALLED_APPS for BLACKLIST_AFTER_ROTATION to work."""
        self.assertIn(
            "rest_framework_simplejwt.token_blacklist",
            settings.INSTALLED_APPS,
            "rest_framework_simplejwt.token_blacklist must be in INSTALLED_APPS "
            "because BLACKLIST_AFTER_ROTATION is True.",
        )

    def test_jwt_authentication_in_drf_defaults(self):
        """JWTAuthentication must be in DRF's default authentication classes."""
        auth_classes = settings.REST_FRAMEWORK.get("DEFAULT_AUTHENTICATION_CLASSES", [])
        self.assertIn(
            "rest_framework_simplejwt.authentication.JWTAuthentication",
            auth_classes,
        )

    def test_default_permission_is_authenticated(self):
        """Default DRF permission must be IsAuthenticated."""
        perm_classes = settings.REST_FRAMEWORK.get("DEFAULT_PERMISSION_CLASSES", [])
        self.assertIn(
            "rest_framework.permissions.IsAuthenticated",
            perm_classes,
        )


class TestSimpleJWTTokenGeneration(TestCase):
    """Verify that SimpleJWT can generate tokens for a user."""

    def test_access_token_can_be_generated(self):
        """AccessToken must be creatable for a real user."""
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken
        from django.conf import settings as django_settings

        User = get_user_model()
        user = User.objects.create_user(username="jwtuser", password="JwtPass123!")
        token = AccessToken.for_user(user)
        self.assertIsNotNone(token)
        # SimpleJWT serialises the PK as a string in the token payload
        claim = django_settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
        self.assertEqual(str(token[claim]), str(user.id))

    def test_refresh_token_can_be_generated(self):
        """RefreshToken must be creatable and contain an access token."""
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import RefreshToken

        User = get_user_model()
        user = User.objects.create_user(username="jwtuser2", password="JwtPass123!")
        refresh = RefreshToken.for_user(user)
        self.assertIsNotNone(refresh)
        self.assertIsNotNone(str(refresh.access_token))
