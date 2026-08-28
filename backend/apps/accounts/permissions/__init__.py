"""
Custom DRF permission classes for the AI-Powered Smart Traffic Management System.

These permission classes gate access based on the role-group a user
belongs to.  They rely on Django Groups — no custom Role model is used.

Usage example::

    from apps.accounts.permissions import IsSystemAdmin, IsTrafficControlOfficer

    class SomeProtectedView(APIView):
        permission_classes = [IsAuthenticated, IsSystemAdmin]
"""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import (
    CAMERA_TECHNICIAN,
    LAW_ENFORCEMENT,
    PAYMENT_FINES_OFFICER,
    PUBLIC_USER,
    SYSTEM_ADMIN,
    TRAFFIC_ANALYST,
    TRAFFIC_CONTROL_OFFICER,
)


class _IsInGroup(BasePermission):
    """
    Base permission that grants access when the authenticated user
    is a member of a specific Django Group (role).

    Subclasses set ``required_group`` to a role name constant.
    """

    required_group: str = ""

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name=self.required_group).exists()


class IsSystemAdmin(_IsInGroup):
    """Grants access to System Administrators."""

    required_group = SYSTEM_ADMIN


class IsTrafficControlOfficer(_IsInGroup):
    """Grants access to Traffic Control Officers."""

    required_group = TRAFFIC_CONTROL_OFFICER


class IsTrafficAnalyst(_IsInGroup):
    """Grants access to Traffic Analysts."""

    required_group = TRAFFIC_ANALYST


class IsLawEnforcement(_IsInGroup):
    """Grants access to Law Enforcement / Authorized Officers."""

    required_group = LAW_ENFORCEMENT


class IsCameraTechnician(_IsInGroup):
    """Grants access to Camera/Sensor Technicians."""

    required_group = CAMERA_TECHNICIAN


class IsPaymentFinesOfficer(_IsInGroup):
    """Grants access to Payment/Fines Officers."""

    required_group = PAYMENT_FINES_OFFICER


class IsPublicUser(_IsInGroup):
    """Grants access to Public Users."""

    required_group = PUBLIC_USER


class IsSystemAdminOrReadOnly(BasePermission):
    """
    Grants full access to System Administrators.
    Grants read-only (safe methods) access to all other authenticated users.
    """

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name=SYSTEM_ADMIN).exists()
