"""
Tests for the custom User model and AUTH_USER_MODEL configuration.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.test import TestCase


class TestAuthUserModelSetting(TestCase):
    """Verify AUTH_USER_MODEL is configured correctly."""

    def test_auth_user_model_setting(self):
        """AUTH_USER_MODEL must point to accounts.User."""
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")

    def test_get_user_model_returns_custom_user(self):
        """get_user_model() must return our custom User class."""
        User = get_user_model()
        self.assertEqual(User.__name__, "User")
        self.assertEqual(User._meta.app_label, "accounts")

    def test_user_is_abstract_user_subclass(self):
        """Custom User must extend AbstractUser."""
        User = get_user_model()
        self.assertTrue(issubclass(User, AbstractUser))

    def test_user_db_table(self):
        """User must be stored in accounts_user table."""
        User = get_user_model()
        self.assertEqual(User._meta.db_table, "accounts_user")


class TestUserRoleHelpers(TestCase):
    """Verify User role helper methods work correctly."""

    def setUp(self):
        from django.contrib.auth.models import Group

        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser", password="TestPass123!"
        )
        self.group_admin, _ = Group.objects.get_or_create(name="System Administrator")
        self.group_analyst, _ = Group.objects.get_or_create(name="Traffic Analyst")

    def test_get_roles_empty_for_new_user(self):
        """A newly created user should have no roles."""
        self.assertEqual(self.user.get_roles(), [])

    def test_has_role_false_when_not_in_group(self):
        """has_role returns False when user is not in the group."""
        self.assertFalse(self.user.has_role("System Administrator"))

    def test_has_role_true_after_adding_to_group(self):
        """has_role returns True after user is added to a role group."""
        self.user.groups.add(self.group_admin)
        self.assertTrue(self.user.has_role("System Administrator"))

    def test_get_roles_lists_assigned_groups(self):
        """get_roles returns all group names the user belongs to."""
        self.user.groups.add(self.group_admin, self.group_analyst)
        roles = self.user.get_roles()
        self.assertIn("System Administrator", roles)
        self.assertIn("Traffic Analyst", roles)
        self.assertEqual(len(roles), 2)

    def test_has_any_role_true_with_one_match(self):
        """has_any_role returns True if user has at least one of the roles."""
        self.user.groups.add(self.group_analyst)
        self.assertTrue(
            self.user.has_any_role("System Administrator", "Traffic Analyst")
        )

    def test_has_any_role_false_with_no_match(self):
        """has_any_role returns False if user has none of the specified roles."""
        self.assertFalse(
            self.user.has_any_role("System Administrator", "Traffic Analyst")
        )

    def test_superuser_implicitly_passes_has_role(self):
        """Superusers should pass has_role regardless of group membership."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="admin", password="AdminPass123!"
        )
        self.assertTrue(superuser.has_role("System Administrator"))
        self.assertTrue(superuser.has_role("NonExistentRole"))

    def test_superuser_implicitly_passes_has_any_role(self):
        """Superusers should pass has_any_role regardless of group membership."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="admin2", password="AdminPass123!"
        )
        self.assertTrue(superuser.has_any_role("Traffic Analyst", "Public User"))
