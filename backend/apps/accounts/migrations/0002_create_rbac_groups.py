"""
Data migration: create the initial RBAC groups (roles).

These groups map to the seven roles defined in apps.accounts.roles.
The migration is idempotent — it uses get_or_create so it is safe
to run more than once and safe to run against a database that already
has some of the groups present.

No schema changes are made by this migration.
"""

from django.db import migrations


ROLES = [
    "System Administrator",
    "Traffic Control Officer",
    "Traffic Analyst",
    "Law Enforcement / Authorized Officer",
    "Camera/Sensor Technician",
    "Payment/Fines Officer",
    "Public User",
]


def create_groups(apps, schema_editor):
    """Forward: ensure all role groups exist."""
    Group = apps.get_model("auth", "Group")
    for role_name in ROLES:
        Group.objects.get_or_create(name=role_name)


def delete_groups(apps, schema_editor):
    """Reverse: remove the role groups created by this migration."""
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        # auth groups table must exist before we can populate it
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_groups, reverse_code=delete_groups),
    ]
