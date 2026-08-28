from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.organizations.models import Region, City, TrafficControlCenter, UserScope


def _jwt_client(user) -> APIClient:
    token = AccessToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestOrganizationScopeFiltering(TestCase):
    def setUp(self):
        User = get_user_model()
        Group.objects.get_or_create(name="Traffic Analyst")
        # create regions/cities/centers
        self.r1 = Region.objects.create(name="R1", code="R1")
        self.r2 = Region.objects.create(name="R2", code="R2")
        self.c1 = City.objects.create(region=self.r1, name="C1", code="C1")
        self.c2 = City.objects.create(region=self.r2, name="C2", code="C2")
        self.cc1 = TrafficControlCenter.objects.create(name="CC1", code="CC1", region=self.r1, city=self.c1)
        self.cc2 = TrafficControlCenter.objects.create(name="CC2", code="CC2", region=self.r2, city=self.c2)

        # superuser
        self.su = User.objects.create_superuser(username="su", password="pass")
        self.su_client = _jwt_client(self.su)

        # region-scoped user
        self.reg_user = User.objects.create_user(username="reg", password="pass")
        self.reg_user.groups.add(Group.objects.get(name="Traffic Analyst"))
        UserScope.objects.create(user=self.reg_user, region=self.r1)
        self.reg_client = _jwt_client(self.reg_user)

        # city-scoped user
        self.city_user = User.objects.create_user(username="city", password="pass")
        self.city_user.groups.add(Group.objects.get(name="Traffic Analyst"))
        UserScope.objects.create(user=self.city_user, city=self.c2)
        self.city_client = _jwt_client(self.city_user)

        # control-center scoped user
        self.cc_user = User.objects.create_user(username="ccu", password="pass")
        self.cc_user.groups.add(Group.objects.get(name="Traffic Analyst"))
        UserScope.objects.create(user=self.cc_user, control_center=self.cc1)
        self.cc_client = _jwt_client(self.cc_user)

    def test_superuser_sees_all_regions(self):
        resp = self.su_client.get("/api/v1/organizations/regions/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data.get("results", [])), 2)

    def test_region_scoped_user_sees_only_assigned_region(self):
        resp = self.reg_client.get("/api/v1/organizations/regions/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [r["name"] for r in data.get("results", [])]
        self.assertIn("R1", names)
        self.assertNotIn("R2", names)

    def test_city_scoped_user_sees_only_city_region(self):
        resp = self.city_client.get("/api/v1/organizations/regions/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [r["name"] for r in data.get("results", [])]
        # city c2 belongs to region r2
        self.assertIn("R2", names)
        self.assertNotIn("R1", names)

    def test_control_center_scoped_user_sees_center_region(self):
        resp = self.cc_client.get("/api/v1/organizations/regions/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [r["name"] for r in data.get("results", [])]
        # cc1 is in region r1
        self.assertIn("R1", names)
        self.assertNotIn("R2", names)
