"""
Serializers for the accounts app.

Two serializers are provided:

UserProfileSerializer
    Read-only.  Used for the authenticated user's own ``/me/`` endpoint.
    Deliberately omits ``is_staff``, ``is_superuser``, and ``last_login``
    to avoid leaking privilege information to regular users.

AdminUserSerializer
    Read-only.  Used by System-Administrator-only endpoints.
    Includes additional fields appropriate for administrative views
    (``is_staff``, ``last_login``) while still excluding ``password``,
    ``is_superuser``, and ``user_permissions``.
"""

from rest_framework import serializers

from apps.accounts.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the authenticated user's own profile.

    Security guarantees
    -------------------
    - ``password`` and all internal auth fields are explicitly excluded.
    - ``roles`` is derived from the user's Django Groups; it is computed
      server-side and cannot be modified through this serializer.
    - ``is_staff`` and ``is_superuser`` are intentionally omitted from the
      public profile to avoid leaking privilege information.

    Fields
    ------
    id          : int        — primary key
    username    : str        — unique username
    email       : str        — email address
    first_name  : str        — given name
    last_name   : str        — family name
    is_active   : bool       — account active flag
    date_joined : datetime   — UTC datetime when the account was created
    roles       : list[str]  — role-group names assigned to this user
    """

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "date_joined",
            "roles",
        ]
        # All fields are read-only — this serializer is used for GET only.
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        """Return the list of role-group names the user belongs to."""
        return obj.get_roles()


class AdminUserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for administrative user-management endpoints.

    Used exclusively by System-Administrator-only views.  Extends the
    safe field set with ``is_staff`` and ``last_login`` so that admins
    have the information they need without exposing ``password``,
    ``is_superuser``, or ``user_permissions``.

    Security guarantees
    -------------------
    - ``password`` is never included.
    - ``is_superuser`` is excluded (prevents leaking super-admin status
      via the management API; superusers appear as ordinary admins).
    - ``user_permissions`` is excluded.
    - All fields are read-only; no writes are accepted through this
      serializer.

    Fields
    ------
    id          : int        — primary key
    username    : str        — unique username
    email       : str        — email address
    first_name  : str        — given name
    last_name   : str        — family name
    is_active   : bool       — account active flag
    is_staff    : bool       — Django staff flag (admin-site access)
    date_joined : datetime   — UTC datetime when the account was created
    last_login  : datetime   — UTC datetime of last login (nullable)
    roles       : list[str]  — role-group names assigned to this user
    """

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "roles",
        ]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        """Return the list of role-group names the user belongs to."""
        return obj.get_roles()
