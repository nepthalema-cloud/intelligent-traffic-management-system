"""
Tests for RBAC group initialisation.

Verifies that the data migration creates exactly the expected groups
and that the role constants are consistent.
"""

from django.contrib.auth.models import Group
from django.test import TestCase

from apps.accounts.roles import ALL_ROLES, SYSTEM_ADMIN, TRAFFIC_ANALYST


class TestRoleConstants(TestCase):
    """Verify the role constant module is self-consistent."""

    def test_all_roles_is_not_empty(self):
        """ALL_ROLES must contain at least one role."""
        self.assertGreater(len(ALL_ROLES), 0)

    def test_expected_roles_present(self):
        """The seven expected roles must all be in ALL_ROLES."""
        expected = {
            "System Administrator",
            "Traffic Control Officer",
            "Traffic Analyst",
            "Law Enforcement / Authorized Officer",
            "Camera/Sensor Technician",
            "Payment/Fines Officer",
            "Public User",
        }
        self.assertEqual(expected, set(ALL_ROLES))

    def test_named_constants_match_all_roles(self):
        """Named constants must appear in ALL_ROLES."""
        self.assertIn(SYSTEM_ADMIN, ALL_ROLES)
        self.assertIn(TRAFFIC_ANALYST, ALL_ROLES)

    def test_no_duplicate_roles(self):
        """ALL_ROLES must not contain duplicates."""
        self.assertEqual(len(ALL_ROLES), len(set(ALL_ROLES)))


class TestRBACGroupsExistAfterMigration(TestCase):
    """
    Verify that the data migration created all required groups.

    Django's test runner runs all migrations before the test suite,
    so the groups should already exist in the test database.
    """

    def test_all_role_groups_exist(self):
        """Every role in ALL_ROLES must have a corresponding Group."""
        for role_name in ALL_ROLES:
            with self.subTest(role=role_name):
                self.assertTrue(
                    Group.objects.filter(name=role_name).exists(),
                    f"Group '{role_name}' was not created by the data migration.",
                )

    def test_group_count_matches_roles(self):
        """The number of created groups must equal the number of roles."""
        created_count = Group.objects.filter(name__in=ALL_ROLES).count()
        self.assertEqual(created_count, len(ALL_ROLES))
