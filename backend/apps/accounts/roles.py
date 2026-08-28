"""
Role definitions for the AI-Powered Smart Traffic Management System.

RBAC Architecture Decision
--------------------------
Django's built-in ``auth.Group`` model is used to represent roles.
This avoids creating a redundant custom Role model — Groups already
provide the M2M relationship to User (via AbstractUser) and integrate
with Django's Permission system out of the box.

Each role maps to exactly one Group.  Users may belong to multiple
Groups if their responsibilities span roles, but in practice most
users will have a single role.

Roles
-----
SYSTEM_ADMIN            Full system access; manages users and configuration.
TRAFFIC_CONTROL_OFFICER Monitors live traffic, controls signals in real time.
TRAFFIC_ANALYST         Read-only access to traffic data and reports.
LAW_ENFORCEMENT         Access to violation records and enforcement tools.
CAMERA_TECHNICIAN       Manages cameras and sensors; no traffic-data write access.
PAYMENT_FINES_OFFICER   Manages fines, payments, and billing records.
PUBLIC_USER             Minimal read access to public-facing data only.
"""

# Canonical role name constants — always use these instead of raw strings.
SYSTEM_ADMIN = "System Administrator"
TRAFFIC_CONTROL_OFFICER = "Traffic Control Officer"
TRAFFIC_ANALYST = "Traffic Analyst"
LAW_ENFORCEMENT = "Law Enforcement / Authorized Officer"
CAMERA_TECHNICIAN = "Camera/Sensor Technician"
PAYMENT_FINES_OFFICER = "Payment/Fines Officer"
PUBLIC_USER = "Public User"

# Ordered list used for migration and management commands.
ALL_ROLES: list[str] = [
    SYSTEM_ADMIN,
    TRAFFIC_CONTROL_OFFICER,
    TRAFFIC_ANALYST,
    LAW_ENFORCEMENT,
    CAMERA_TECHNICIAN,
    PAYMENT_FINES_OFFICER,
    PUBLIC_USER,
]
