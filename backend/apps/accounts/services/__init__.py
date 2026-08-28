"""
Service layer for the accounts app.

All role-assignment business logic lives here so that views and
serializers remain thin.  Import and call these services from views;
do not put this logic in serializers or models.
"""

from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.accounts.roles import ALL_ROLES, SYSTEM_ADMIN


class RoleServiceError(Exception):
    """Base exception for role-service errors."""


class InvalidRoleError(RoleServiceError):
    """Raised when a caller supplies a role name that is not in ALL_ROLES."""


class SelfElevationError(RoleServiceError):
    """
    Raised when a user attempts to modify their own role membership,
    which would allow privilege escalation.
    """


class RoleService:
    """
    Encapsulates all role-assignment operations.

    Security rules enforced here
    ----------------------------
    1. Only role names from ``ALL_ROLES`` are accepted.  Arbitrary group
       names supplied by a client are rejected with ``InvalidRoleError``.
    2. An actor may not modify their own roles (``SelfElevationError``).
       This prevents a System Administrator from, e.g., adding extra
       roles to their own account through the API.
    3. These service-level checks complement the view-level permission
       checks (``IsSystemAdmin``).  Views are responsible for verifying
       that the *caller* has the System Administrator role before calling
       into this service.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def assign_role(actor: User, target: User, role_name: str) -> None:
        """
        Add ``role_name`` to ``target`` user's groups.

        Parameters
        ----------
        actor:
            The user performing the operation.  Must not be ``target``.
        target:
            The user whose role membership is being modified.
        role_name:
            A canonical role name from ``apps.accounts.roles.ALL_ROLES``.

        Raises
        ------
        InvalidRoleError
            If ``role_name`` is not in ``ALL_ROLES``.
        SelfElevationError
            If ``actor`` and ``target`` are the same user.
        """
        RoleService._validate_role(role_name)
        RoleService._reject_self_modification(actor, target)

        group = Group.objects.get(name=role_name)
        target.groups.add(group)

    @staticmethod
    def remove_role(actor: User, target: User, role_name: str) -> None:
        """
        Remove ``role_name`` from ``target`` user's groups.

        Parameters
        ----------
        actor:
            The user performing the operation.  Must not be ``target``.
        target:
            The user whose role membership is being modified.
        role_name:
            A canonical role name from ``apps.accounts.roles.ALL_ROLES``.

        Raises
        ------
        InvalidRoleError
            If ``role_name`` is not in ``ALL_ROLES``.
        SelfElevationError
            If ``actor`` and ``target`` are the same user.
        """
        RoleService._validate_role(role_name)
        RoleService._reject_self_modification(actor, target)

        group = Group.objects.get(name=role_name)
        target.groups.remove(group)

    @staticmethod
    def get_user_roles(user: User) -> list[str]:
        """
        Return the list of role-group names assigned to ``user``.

        Delegates to ``User.get_roles()`` for consistency.
        """
        return user.get_roles()

    @staticmethod
    def set_active(actor: User, target: User, is_active: bool) -> None:
        """
        Activate or deactivate a user account.

        Parameters
        ----------
        actor:
            The user performing the operation.  Must not be ``target``.
        target:
            The user account to activate or deactivate.
        is_active:
            ``True`` to activate, ``False`` to deactivate.

        Raises
        ------
        SelfElevationError
            If ``actor`` and ``target`` are the same user.
        """
        RoleService._reject_self_modification(actor, target)
        target.is_active = is_active
        target.save(update_fields=["is_active"])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_role(role_name: str) -> None:
        """Raise InvalidRoleError if ``role_name`` is not in ALL_ROLES."""
        if role_name not in ALL_ROLES:
            raise InvalidRoleError(
                f"'{role_name}' is not a valid role. "
                f"Valid roles are: {', '.join(ALL_ROLES)}"
            )

    @staticmethod
    def _reject_self_modification(actor: User, target: User) -> None:
        """Raise SelfElevationError if actor and target are the same user."""
        if actor.pk == target.pk:
            raise SelfElevationError(
                "Users may not modify their own role membership."
            )
