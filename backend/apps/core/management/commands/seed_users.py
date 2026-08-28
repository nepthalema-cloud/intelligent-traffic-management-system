"""
Management command: seed_users

Creates one RBAC demo account per role. Idempotent — safe to run
multiple times without creating duplicates.

Does NOT create test/verification users. Those are created by test
runners inside isolated test databases and must never reach the
development database.

Credentials:
    Admin      / admin1234    ← primary demo login (matches UI "Fill Demo Credentials")
    admin      / Admin1234!   ← secondary sysadmin (staff=True, Django admin access)
    tco        / Admin1234!
    analyst    / Admin1234!
    law        / Admin1234!
    camtech    / Admin1234!
    payofficer / Admin1234!
    publicuser / Admin1234!

Usage:
    python manage.py seed_users
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

DEMO_USERS = [
    # (username,    email,                    role_name,                              is_staff, password)
    ("admin",       "admin@trafficops.local",     "System Administrator",              True,  "Admin1234!"),
    ("Admin",       "Admin@trafficops.local",      "System Administrator",              True,  "admin1234"),
    ("tco",         "tco@trafficops.local",        "Traffic Control Officer",           False, "Admin1234!"),
    ("analyst",     "analyst@trafficops.local",    "Traffic Analyst",                   False, "Admin1234!"),
    ("law",         "law@trafficops.local",        "Law Enforcement / Authorized Officer", False, "Admin1234!"),
    ("camtech",     "camtech@trafficops.local",    "Camera/Sensor Technician",          False, "Admin1234!"),
    ("payofficer",  "payofficer@trafficops.local", "Payment/Fines Officer",             False, "Admin1234!"),
    ("publicuser",  "public@trafficops.local",     "Public User",                       False, "Admin1234!"),
]


class Command(BaseCommand):
    help = (
        "Create one demo user per RBAC role. "
        "Idempotent — will not create duplicates."
    )

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for username, email, role_name, is_staff, password in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email":      email,
                    "is_staff":   is_staff,
                    "is_active":  True,
                    "first_name": username.capitalize(),
                },
            )
            if created:
                user.set_password(password)
                user.save()
                created_count += 1
                action = "Created"
            else:
                # Ensure role assignment is correct even for existing users
                action = "Exists "
                skipped_count += 1

            group, _ = Group.objects.get_or_create(name=role_name)
            if not user.groups.filter(name=role_name).exists():
                user.groups.add(group)

            self.stdout.write(f"  {action}: {username:<12} | {role_name}")

        self.stdout.write(self.style.SUCCESS(
            f"\n{created_count} users created, {skipped_count} already existed.\n"
            f"\n  Primary demo login:  Admin / admin1234\n"
            f"  Django admin login:  admin / Admin1234!\n"
            f"  All other accounts:  <username> / Admin1234!\n"
        ))
