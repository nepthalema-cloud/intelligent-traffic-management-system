"""
Accounts models package.

The User model is defined here so Django's app registry discovers it
correctly via ``apps.accounts.models``.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.

    Schema
    ------
    No extra database fields are added at this stage.  All standard
    AbstractUser fields are available: username, email, first_name,
    last_name, is_active, is_staff, is_superuser, date_joined,
    last_login, password, groups (M2M), user_permissions (M2M).

    Role helpers
    ------------
    Roles are implemented via Django Groups — see ``apps.accounts.roles``
    for the canonical role-name constants.

    The helper methods below provide a convenient read-only interface to
    role membership.  They do NOT add database columns; role assignment
    is managed through the existing ``groups`` M2M relation.

    Future fields
    -------------
    Fields such as ``avatar``, ``phone_number``, and ``last_password_change``
    will be added in a later migration when required by features.
    """

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    # ------------------------------------------------------------------
    # Role helpers — no schema change, no migration needed
    # ------------------------------------------------------------------

    def get_roles(self) -> list[str]:
        """Return a list of role-group names this user belongs to."""
        return list(self.groups.values_list("name", flat=True))

    def has_role(self, role_name: str) -> bool:
        """
        Return True if the user is a member of the named role-group.

        Superusers implicitly pass all role checks.
        """
        if self.is_superuser:
            return True
        return self.groups.filter(name=role_name).exists()

    def has_any_role(self, *role_names: str) -> bool:
        """
        Return True if the user is a member of at least one of the
        supplied role-group names.

        Superusers implicitly pass all role checks.
        """
        if self.is_superuser:
            return True
        return self.groups.filter(name__in=role_names).exists()

    # ------------------------------------------------------------------
    # Scope accessors (read-only helpers)
    # ------------------------------------------------------------------
    @property
    def region(self):
        scope = getattr(self, "scope_assignment", None)
        return getattr(scope, "region", None) if scope is not None else None

    @property
    def city(self):
        scope = getattr(self, "scope_assignment", None)
        return getattr(scope, "city", None) if scope is not None else None

    @property
    def control_center(self):
        scope = getattr(self, "scope_assignment", None)
        return getattr(scope, "control_center", None) if scope is not None else None
