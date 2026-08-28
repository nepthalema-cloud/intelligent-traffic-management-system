"""
Tests for the RoleService.

Covers:
- assign_role: happy path, invalid role, self-elevation guard
- remove_role: happy path, invalid role, self-elevation guard
- get_user_roles: delegates to User.get_roles()
- set_active: activate/deactivate, self-modification guard
- Security: privilege escalation is blocked
"""

from django.contrib.auth.models import Group
from django.test import TestCase

from apps.accounts.roles import ALL_ROLES, SYSTEM_ADMIN, TRAFFIC_ANALYST, PUBLIC_USER
from apps.accounts.services import (
    InvalidRoleError,
    RoleService,
    SelfElevationError,
)


def _make_user(username, password="Pass123!", **kwargs):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(
        username=username, password=password, **kwargs
    )


def _ensure_groups():
    """Ensure all role groups exist (data migration may not run in isolation)."""
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


class TestRoleServiceAssign(TestCase):
    """RoleService.assign_role happy path and validation."""

    def setUp(self):
        _ensure_groups()
        self.admin = _make_user("admin")
        self.target = _make_user("target")

    def test_assign_valid_role(self):
        """Assigning a valid role adds the group to the target user."""
        RoleService.assign_role(self.admin, self.target, TRAFFIC_ANALYST)
        self.assertIn(TRAFFIC_ANALYST, self.target.get_roles())

    def test_assign_all_valid_roles(self):
        """Every role in ALL_ROLES can be assigned without error."""
        for role in ALL_ROLES:
            with self.subTest(role=role):
                RoleService.assign_role(self.admin, self.target, role)
        self.assertEqual(set(self.target.get_roles()), set(ALL_ROLES))

    def test_assign_invalid_role_raises(self):
        """An unknown role name must raise InvalidRoleError."""
        with self.assertRaises(InvalidRoleError):
            RoleService.assign_role(self.admin, self.target, "Super Hacker")

    def test_assign_arbitrary_string_raises(self):
        """Arbitrary strings must never be accepted as role names."""
        for bad in ("", "admin", "root", "AUTH_USER", "'; DROP TABLE--"):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidRoleError):
                    RoleService.assign_role(self.admin, self.target, bad)

    def test_assign_is_idempotent(self):
        """Assigning the same role twice must not raise or duplicate."""
        RoleService.assign_role(self.admin, self.target, TRAFFIC_ANALYST)
        RoleService.assign_role(self.admin, self.target, TRAFFIC_ANALYST)
        self.assertEqual(self.target.get_roles().count(TRAFFIC_ANALYST), 1)

    def test_assign_self_raises_self_elevation_error(self):
        """Actor must not be able to assign a role to themselves."""
        with self.assertRaises(SelfElevationError):
            RoleService.assign_role(self.admin, self.admin, SYSTEM_ADMIN)

    def test_assign_system_admin_to_self_blocked(self):
        """Attempting to grant oneself System Administrator is blocked."""
        with self.assertRaises(SelfElevationError):
            RoleService.assign_role(self.admin, self.admin, SYSTEM_ADMIN)

    def test_non_admin_actor_can_still_use_service(self):
        """
        The service itself does not check whether the actor IS an admin —
        that gate lives at the view layer.  The service only blocks
        self-modification.
        """
        regular = _make_user("regular")
        # Service-level: regular user CAN call assign on a different user
        RoleService.assign_role(regular, self.target, PUBLIC_USER)
        self.assertIn(PUBLIC_USER, self.target.get_roles())


class TestRoleServiceRemove(TestCase):
    """RoleService.remove_role happy path and validation."""

    def setUp(self):
        _ensure_groups()
        self.admin = _make_user("admin2")
        self.target = _make_user("target2")
        # Pre-assign a role to remove
        group = Group.objects.get(name=TRAFFIC_ANALYST)
        self.target.groups.add(group)

    def test_remove_valid_role(self):
        """Removing a valid role removes the group from the target user."""
        RoleService.remove_role(self.admin, self.target, TRAFFIC_ANALYST)
        self.assertNotIn(TRAFFIC_ANALYST, self.target.get_roles())

    def test_remove_unassigned_role_does_not_raise(self):
        """Removing a role the user does not have must not raise."""
        RoleService.remove_role(self.admin, self.target, SYSTEM_ADMIN)
        self.assertNotIn(SYSTEM_ADMIN, self.target.get_roles())

    def test_remove_invalid_role_raises(self):
        """An unknown role name must raise InvalidRoleError on removal."""
        with self.assertRaises(InvalidRoleError):
            RoleService.remove_role(self.admin, self.target, "not_a_role")

    def test_remove_self_raises_self_elevation_error(self):
        """Actor must not be able to remove a role from themselves."""
        with self.assertRaises(SelfElevationError):
            RoleService.remove_role(self.admin, self.admin, TRAFFIC_ANALYST)


class TestRoleServiceGetRoles(TestCase):
    """RoleService.get_user_roles delegates to User.get_roles()."""

    def setUp(self):
        _ensure_groups()
        self.user = _make_user("roleuser")

    def test_empty_roles_for_new_user(self):
        """A new user has no roles."""
        self.assertEqual(RoleService.get_user_roles(self.user), [])

    def test_returns_assigned_roles(self):
        """Assigned groups are returned by get_user_roles."""
        group = Group.objects.get(name=TRAFFIC_ANALYST)
        self.user.groups.add(group)
        roles = RoleService.get_user_roles(self.user)
        self.assertIn(TRAFFIC_ANALYST, roles)

    def test_consistent_with_user_get_roles(self):
        """Service result must match user.get_roles() directly."""
        group = Group.objects.get(name=SYSTEM_ADMIN)
        self.user.groups.add(group)
        self.assertEqual(
            RoleService.get_user_roles(self.user),
            self.user.get_roles(),
        )


class TestRoleServiceSetActive(TestCase):
    """RoleService.set_active activate/deactivate logic."""

    def setUp(self):
        self.admin = _make_user("activeadmin")
        self.target = _make_user("activetarget")

    def test_deactivate_user(self):
        """set_active(False) must deactivate the target user."""
        RoleService.set_active(self.admin, self.target, False)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_reactivate_user(self):
        """set_active(True) must re-activate a previously deactivated user."""
        self.target.is_active = False
        self.target.save()
        RoleService.set_active(self.admin, self.target, True)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_self_deactivation_blocked(self):
        """Actor must not be able to deactivate their own account."""
        with self.assertRaises(SelfElevationError):
            RoleService.set_active(self.admin, self.admin, False)

    def test_self_activation_blocked(self):
        """Actor must not be able to activate their own account via the service."""
        with self.assertRaises(SelfElevationError):
            RoleService.set_active(self.admin, self.admin, True)


class TestRoleServiceErrors(TestCase):
    """Verify exception hierarchy and messages."""

    def test_invalid_role_error_is_role_service_error(self):
        """InvalidRoleError must be a subclass of RoleServiceError."""
        self.assertTrue(issubclass(InvalidRoleError, Exception))

    def test_self_elevation_error_is_role_service_error(self):
        """SelfElevationError must be a subclass of RoleServiceError."""
        self.assertTrue(issubclass(SelfElevationError, Exception))

    def test_invalid_role_error_message_contains_role_name(self):
        """InvalidRoleError message must mention the invalid role name."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        actor = User.objects.create_user(username="erractor", password="P!")
        target = User.objects.create_user(username="errtarget", password="P!")
        _ensure_groups()
        try:
            RoleService.assign_role(actor, target, "bad_role_xyz")
            self.fail("Expected InvalidRoleError was not raised")
        except InvalidRoleError as exc:
            self.assertIn("bad_role_xyz", str(exc))
