"""
Tests for the custom DRF permission classes.
"""

from unittest.mock import MagicMock

from django.contrib.auth.models import Group
from django.test import TestCase, RequestFactory

from apps.accounts.permissions import (
    IsCameraTechnician,
    IsLawEnforcement,
    IsPaymentFinesOfficer,
    IsPublicUser,
    IsSystemAdmin,
    IsSystemAdminOrReadOnly,
    IsTrafficAnalyst,
    IsTrafficControlOfficer,
)
from apps.accounts.roles import (
    CAMERA_TECHNICIAN,
    LAW_ENFORCEMENT,
    PAYMENT_FINES_OFFICER,
    PUBLIC_USER,
    SYSTEM_ADMIN,
    TRAFFIC_ANALYST,
    TRAFFIC_CONTROL_OFFICER,
)


def _make_request(user):
    """Return a minimal mock request carrying the given user."""
    request = MagicMock()
    request.user = user
    return request


class TestIsInGroupPermissions(TestCase):
    """Verify each role-based permission class behaves correctly."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="officer", password="Pass123!"
        )
        # Ensure all groups exist (migration may not have run in isolation)
        from apps.accounts.roles import ALL_ROLES
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

    def _add_role(self, role_name: str):
        group = Group.objects.get(name=role_name)
        self.user.groups.add(group)

    def _check(self, permission_class, role_name: str):
        """Assert the permission grants access only when user has the role."""
        perm = permission_class()
        request = _make_request(self.user)
        view = MagicMock()

        # Without the role
        self.assertFalse(perm.has_permission(request, view))

        # With the role
        self._add_role(role_name)
        self.assertTrue(perm.has_permission(request, view))

    def test_is_system_admin(self):
        self._check(IsSystemAdmin, SYSTEM_ADMIN)

    def test_is_traffic_control_officer(self):
        self._check(IsTrafficControlOfficer, TRAFFIC_CONTROL_OFFICER)

    def test_is_traffic_analyst(self):
        self._check(IsTrafficAnalyst, TRAFFIC_ANALYST)

    def test_is_law_enforcement(self):
        self._check(IsLawEnforcement, LAW_ENFORCEMENT)

    def test_is_camera_technician(self):
        self._check(IsCameraTechnician, CAMERA_TECHNICIAN)

    def test_is_payment_fines_officer(self):
        self._check(IsPaymentFinesOfficer, PAYMENT_FINES_OFFICER)

    def test_is_public_user(self):
        self._check(IsPublicUser, PUBLIC_USER)

    def test_unauthenticated_user_denied(self):
        """Unauthenticated requests must be denied by all role permissions."""
        perm = IsSystemAdmin()
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        self.assertFalse(perm.has_permission(request, MagicMock()))

    def test_superuser_bypasses_role_check(self):
        """Superusers must pass all role permissions without group membership."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="su", password="SuperPass123!"
        )
        request = _make_request(superuser)
        view = MagicMock()
        for perm_class in [
            IsSystemAdmin,
            IsTrafficControlOfficer,
            IsTrafficAnalyst,
            IsLawEnforcement,
            IsCameraTechnician,
            IsPaymentFinesOfficer,
            IsPublicUser,
        ]:
            with self.subTest(permission=perm_class.__name__):
                self.assertTrue(perm_class().has_permission(request, view))


class TestIsSystemAdminOrReadOnly(TestCase):
    """Verify the combined read-only / admin permission class."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.regular_user = User.objects.create_user(
            username="regular", password="Pass123!"
        )
        self.admin_user = User.objects.create_user(
            username="adminuser", password="Pass123!"
        )
        admin_group, _ = Group.objects.get_or_create(name=SYSTEM_ADMIN)
        self.admin_user.groups.add(admin_group)

    def _request(self, user, method="GET"):
        req = MagicMock()
        req.user = user
        req.method = method
        return req

    def test_regular_user_can_read(self):
        perm = IsSystemAdminOrReadOnly()
        self.assertTrue(perm.has_permission(self._request(self.regular_user, "GET"), MagicMock()))

    def test_regular_user_cannot_write(self):
        perm = IsSystemAdminOrReadOnly()
        self.assertFalse(perm.has_permission(self._request(self.regular_user, "POST"), MagicMock()))

    def test_admin_can_write(self):
        perm = IsSystemAdminOrReadOnly()
        self.assertTrue(perm.has_permission(self._request(self.admin_user, "POST"), MagicMock()))

    def test_unauthenticated_denied(self):
        perm = IsSystemAdminOrReadOnly()
        req = MagicMock()
        req.user = MagicMock()
        req.user.is_authenticated = False
        req.method = "GET"
        self.assertFalse(perm.has_permission(req, MagicMock()))
