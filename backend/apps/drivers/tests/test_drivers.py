from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import ALL_ROLES
from apps.drivers.models import Driver
from apps.violations.models import Vehicle

User = get_user_model()


class TestDriverModel(TestCase):
    def setUp(self):
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

    def test_driver_can_be_created(self):
        driver = Driver.objects.create(
            first_name="Abebe",
            last_name="Bekele",
            license_number="ABC12345",
            license_status="active",
            license_issue_date=timezone.now().date(),
            license_expiry_date=timezone.now().date(),
        )
        self.assertEqual(driver.full_name, "Abebe Bekele")
        self.assertEqual(driver.license_status, "active")

    def test_driver_unique_license_number(self):
        Driver.objects.create(
            first_name="A",
            last_name="B",
            license_number="UNIQUE-1",
            license_status="active",
            license_issue_date=timezone.now().date(),
            license_expiry_date=timezone.now().date(),
        )
        with self.assertRaises(Exception):
            Driver.objects.create(
                first_name="C",
                last_name="D",
                license_number="UNIQUE-1",
                license_status="active",
                license_issue_date=timezone.now().date(),
                license_expiry_date=timezone.now().date(),
            )

    def test_vehicle_can_link_to_driver(self):
        driver = Driver.objects.create(
            first_name="Test",
            last_name="Driver",
            license_number="VLINK-1",
            license_status="active",
            license_issue_date=timezone.now().date(),
            license_expiry_date=timezone.now().date(),
        )
        vehicle = Vehicle.objects.create(plate_number="ABC-123", vehicle_type="car")
        vehicle.driver = driver
        vehicle.save(update_fields=["driver"])
        self.assertEqual(vehicle.driver, driver)
