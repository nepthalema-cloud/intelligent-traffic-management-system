from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from apps.accounts.roles import ALL_ROLES
from apps.organizations.models import City, Region, TrafficControlCenter

User = get_user_model()


class TestOrganizationScope(TestCase):
    def setUp(self):
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

    def test_region_city_and_center_can_be_created(self):
        region = Region.objects.create(name="Amhara", code="AM")
        city = City.objects.create(name="Gondar", code="GD", region=region)
        center = TrafficControlCenter.objects.create(
            name="Gondar TMC",
            code="GONDAR-TMC",
            city=city,
            region=region,
        )
        self.assertEqual(region.name, "Amhara")
        self.assertEqual(city.region, region)
        self.assertEqual(center.city, city)

    def test_user_scope_fields_are_optional(self):
        user = User.objects.create_user(username="scopeuser", password="Pass123!")
        self.assertIsNone(user.region)
        self.assertIsNone(user.city)
        self.assertIsNone(user.control_center)
