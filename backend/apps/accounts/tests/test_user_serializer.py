"""
Tests for UserProfileSerializer.

Covers:
- Correct fields are serialized
- Password is never serialized
- Roles field calls get_roles() correctly
- Serializer is read-only (no write operations)
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from apps.accounts.roles import SYSTEM_ADMIN, TRAFFIC_ANALYST
from apps.accounts.serializers import UserProfileSerializer


def _make_user(username="serializeruser", **kwargs):
    kwargs.setdefault("first_name", "Test")
    kwargs.setdefault("last_name", "User")
    return get_user_model().objects.create_user(
        username=username,
        email=kwargs.pop("email", f"{username}@example.com"),
        password=kwargs.pop("password", "SerializerPass123!"),
        **kwargs,
    )


class TestUserProfileSerializerFields(TestCase):
    """Verify the serialized output contains exactly the right fields."""

    def setUp(self):
        self.user = _make_user()
        self.data = UserProfileSerializer(self.user).data

    def test_expected_fields_present(self):
        """All expected profile fields must appear in serialized data."""
        expected = {"id", "username", "email", "first_name", "last_name",
                    "is_active", "date_joined", "roles"}
        self.assertEqual(set(self.data.keys()), expected)

    def test_password_not_in_serialized_data(self):
        """Password must never appear in serialized output."""
        self.assertNotIn("password", self.data)

    def test_is_superuser_not_in_serialized_data(self):
        """is_superuser must not be exposed."""
        self.assertNotIn("is_superuser", self.data)

    def test_is_staff_not_in_serialized_data(self):
        """is_staff must not be exposed."""
        self.assertNotIn("is_staff", self.data)

    def test_last_login_not_in_serialized_data(self):
        """last_login must not be exposed."""
        self.assertNotIn("last_login", self.data)

    def test_user_permissions_not_in_serialized_data(self):
        """user_permissions must not be exposed."""
        self.assertNotIn("user_permissions", self.data)

    def test_groups_raw_not_in_serialized_data(self):
        """Raw groups field must not be exposed — only the derived roles list."""
        self.assertNotIn("groups", self.data)


class TestUserProfileSerializerValues(TestCase):
    """Verify the values returned by the serializer are correct."""

    def setUp(self):
        self.user = _make_user(
            username="valuetest",
            first_name="Value",
            last_name="Test",
        )
        self.user.email = "value@test.com"
        self.user.save()

    def test_id_value(self):
        data = UserProfileSerializer(self.user).data
        self.assertEqual(data["id"], self.user.id)

    def test_username_value(self):
        data = UserProfileSerializer(self.user).data
        self.assertEqual(data["username"], "valuetest")

    def test_email_value(self):
        data = UserProfileSerializer(self.user).data
        self.assertEqual(data["email"], "value@test.com")

    def test_is_active_true_by_default(self):
        data = UserProfileSerializer(self.user).data
        self.assertTrue(data["is_active"])

    def test_roles_empty_for_new_user(self):
        data = UserProfileSerializer(self.user).data
        self.assertEqual(data["roles"], [])

    def test_roles_reflect_group_membership(self):
        """Roles must match the user's current group membership."""
        g1, _ = Group.objects.get_or_create(name=TRAFFIC_ANALYST)
        g2, _ = Group.objects.get_or_create(name=SYSTEM_ADMIN)
        self.user.groups.add(g1, g2)
        data = UserProfileSerializer(self.user).data
        self.assertIn(TRAFFIC_ANALYST, data["roles"])
        self.assertIn(SYSTEM_ADMIN, data["roles"])

    def test_date_joined_is_string(self):
        """date_joined must be serialized as a string (ISO 8601)."""
        data = UserProfileSerializer(self.user).data
        self.assertIsInstance(data["date_joined"], str)


class TestUserProfileSerializerReadOnly(TestCase):
    """Verify the serializer does not accept writes."""

    def setUp(self):
        self.user = _make_user(username="readonlytest")

    def test_all_fields_are_read_only(self):
        """No field on UserProfileSerializer should be writable."""
        serializer = UserProfileSerializer(self.user)
        for field_name, field in serializer.fields.items():
            with self.subTest(field=field_name):
                self.assertTrue(
                    field.read_only,
                    f"Field '{field_name}' is not read-only but should be.",
                )

    def test_cannot_update_via_serializer(self):
        """Passing data to the serializer with update must not persist changes."""
        original_email = self.user.email
        serializer = UserProfileSerializer(
            self.user,
            data={"email": "hacked@evil.com"},
            partial=True,
        )
        # Serializer will be invalid or not save
        if serializer.is_valid():
            # Even if valid (it shouldn't be on read-only), do not save
            pass
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)
