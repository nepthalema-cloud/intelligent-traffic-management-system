# Vehicle API tests - Phase 4D.1
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent
from apps.audit.services import AuditAction
from apps.violations.models import Vehicle

User = get_user_model()
VEH_URL = "/api/v1/violations/vehicles/"


def _ensure_groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _make_user(username, password="Pass123!"):
    return User.objects.create_user(username=username, password=password)


def _make_role_user(username, role_name):
    _ensure_groups()
    user = _make_user(username)
    user.groups.add(Group.objects.get(name=role_name))
    return user


def _jwt(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(user))}")
    return c


def _vehicle(**kw):
    kw.setdefault("plate_number", "TST-001")
    kw.setdefault("vehicle_type", "car")
    return Vehicle.objects.create(**kw)


def _post_vehicle(client, **kw):
    data = {
        "plate_number": kw.get("plate_number", "POST-001"),
        "vehicle_type": kw.get("vehicle_type", "car"),
    }
    if "year" in kw:
        data["year"] = kw["year"]
    if "make" in kw:
        data["make"] = kw["make"]
    if "registration_country" in kw:
        data["registration_country"] = kw["registration_country"]
    return client.post(VEH_URL, data, format="json")


# ---------------------------------------------------------------------------
# URL routing
# ---------------------------------------------------------------------------

class TestVehicleUrlRouting(TestCase):
    def test_list_resolves(self):
        m = resolve(VEH_URL)
        self.assertEqual(m.url_name, "vehicle-list")
        self.assertEqual(m.namespace, "violations")

    def test_list_reverses(self):
        self.assertEqual(reverse("violations:vehicle-list"), VEH_URL)

    def test_detail_resolves(self):
        self.assertEqual(resolve(f"{VEH_URL}1/").url_name, "vehicle-detail")

    def test_status_resolves(self):
        self.assertEqual(resolve(f"{VEH_URL}1/status/").url_name, "vehicle-status")

    def test_invalid_prefix_404(self):
        self.assertEqual(APIClient().get("/api/violations/vehicles/").status_code, 404)
        self.assertEqual(APIClient().get("/api/v1/v1/violations/vehicles/").status_code, 404)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestVehicleAuthentication(TestCase):
    def setUp(self):
        self.v = _vehicle()

    def test_list_unauthenticated_401(self):
        self.assertEqual(APIClient().get(VEH_URL).status_code, 401)

    def test_create_unauthenticated_401(self):
        self.assertEqual(APIClient().post(VEH_URL).status_code, 401)

    def test_detail_unauthenticated_401(self):
        self.assertEqual(APIClient().get(f"{VEH_URL}{self.v.pk}/").status_code, 401)

    def test_update_unauthenticated_401(self):
        self.assertEqual(APIClient().patch(f"{VEH_URL}{self.v.pk}/").status_code, 401)

    def test_status_unauthenticated_401(self):
        self.assertEqual(APIClient().patch(f"{VEH_URL}{self.v.pk}/status/").status_code, 401)


# ---------------------------------------------------------------------------
# RBAC — all seven roles
# ---------------------------------------------------------------------------

class TestVehicleRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("veh_admin",   "System Administrator")
        self.tco     = _make_role_user("veh_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("veh_analyst", "Traffic Analyst")
        self.law     = _make_role_user("veh_law",     "Law Enforcement / Authorized Officer")
        self.cam     = _make_role_user("veh_cam",     "Camera/Sensor Technician")
        self.pay     = _make_role_user("veh_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("veh_pub",     "Public User")
        self.v = _vehicle(plate_number="RBAC-001")

    # Reads
    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(VEH_URL).status_code, 200)

    def test_law_can_list(self):
        self.assertEqual(_jwt(self.law).get(VEH_URL).status_code, 200)

    def test_pay_can_list(self):
        self.assertEqual(_jwt(self.pay).get(VEH_URL).status_code, 200)

    def test_tco_403_on_list(self):
        self.assertEqual(_jwt(self.tco).get(VEH_URL).status_code, 403)

    def test_analyst_403_on_list(self):
        self.assertEqual(_jwt(self.analyst).get(VEH_URL).status_code, 403)

    def test_cam_403_on_list(self):
        self.assertEqual(_jwt(self.cam).get(VEH_URL).status_code, 403)

    def test_pub_403_on_list(self):
        self.assertEqual(_jwt(self.pub).get(VEH_URL).status_code, 403)

    # Creates
    def test_admin_can_create(self):
        self.assertEqual(_post_vehicle(_jwt(self.admin), plate_number="ADMIN-NEW").status_code, 201)

    def test_law_can_create(self):
        self.assertEqual(_post_vehicle(_jwt(self.law), plate_number="LAW-NEW").status_code, 201)

    def test_pay_cannot_create(self):
        self.assertEqual(_post_vehicle(_jwt(self.pay), plate_number="PAY-NEW").status_code, 403)

    def test_tco_cannot_create(self):
        self.assertEqual(_post_vehicle(_jwt(self.tco), plate_number="TCO-NEW").status_code, 403)

    def test_superuser_can_create(self):
        su = User.objects.create_superuser("su_veh", password="SuP!")
        self.assertEqual(_post_vehicle(_jwt(su), plate_number="SU-NEW").status_code, 201)

    # Updates
    def test_admin_can_update(self):
        resp = _jwt(self.admin).patch(
            f"{VEH_URL}{self.v.pk}/", {"make": "Toyota"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_law_can_update(self):
        resp = _jwt(self.law).patch(
            f"{VEH_URL}{self.v.pk}/", {"make": "Honda"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_pay_cannot_update(self):
        resp = _jwt(self.pay).patch(
            f"{VEH_URL}{self.v.pk}/", {"make": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_pay_can_read_detail(self):
        resp = _jwt(self.pay).get(f"{VEH_URL}{self.v.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_law_can_read_detail(self):
        resp = _jwt(self.law).get(f"{VEH_URL}{self.v.pk}/")
        self.assertEqual(resp.status_code, 200)

    # Status
    def test_admin_can_deactivate(self):
        resp = _jwt(self.admin).patch(
            f"{VEH_URL}{self.v.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_law_can_deactivate(self):
        v2 = _vehicle(plate_number="LAW-DEACT")
        resp = _jwt(self.law).patch(
            f"{VEH_URL}{v2.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_pay_cannot_use_status_endpoint(self):
        resp = _jwt(self.pay).patch(
            f"{VEH_URL}{self.v.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# PII tests
# ---------------------------------------------------------------------------

class TestVehiclePII(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("pii_admin", "System Administrator")
        self.law   = _make_role_user("pii_law",   "Law Enforcement / Authorized Officer")
        self.pay   = _make_role_user("pii_pay",   "Payment/Fines Officer")
        self.tco   = _make_role_user("pii_tco",   "Traffic Control Officer")
        self.v = _vehicle(plate_number="PII-001")

    def test_admin_sees_plate_number(self):
        resp = _jwt(self.admin).get(f"{VEH_URL}{self.v.pk}/")
        self.assertIn("plate_number", resp.json()["data"])
        self.assertEqual(resp.json()["data"]["plate_number"], "PII-001")

    def test_law_sees_plate_number(self):
        resp = _jwt(self.law).get(f"{VEH_URL}{self.v.pk}/")
        self.assertIn("plate_number", resp.json()["data"])

    def test_pay_sees_plate_number(self):
        resp = _jwt(self.pay).get(f"{VEH_URL}{self.v.pk}/")
        self.assertIn("plate_number", resp.json()["data"])

    def test_unauthorized_role_cannot_see_vehicle_at_all(self):
        resp = _jwt(self.tco).get(f"{VEH_URL}{self.v.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_audit_detail_does_not_contain_plate_number(self):
        _post_vehicle(_jwt(self.admin), plate_number="AUDIT-PII-001")
        for ev in AuditEvent.objects.filter(action=AuditAction.VEHICLE_CREATED):
            self.assertNotIn("plate_number", str(ev.detail or ""))
            self.assertNotIn("AUDIT-PII-001", str(ev.detail or ""))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestVehicleCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("crud_veh_admin", "System Administrator")

    def test_list_200_with_pagination(self):
        _vehicle(plate_number="CR1"); _vehicle(plate_number="CR2")
        resp = _jwt(self.admin).get(VEH_URL)
        self.assertEqual(resp.status_code, 200)
        for k in ("count", "results"):
            self.assertIn(k, resp.json())

    def test_create_201(self):
        resp = _post_vehicle(_jwt(self.admin), plate_number="NEW-001", make="BMW")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["plate_number"], "NEW-001")

    def test_plate_number_normalized_to_uppercase(self):
        resp = _post_vehicle(_jwt(self.admin), plate_number="abc-999")
        self.assertEqual(resp.json()["data"]["plate_number"], "ABC-999")

    def test_create_blank_plate_400(self):
        resp = _jwt(self.admin).post(
            VEH_URL, {"plate_number": "  ", "vehicle_type": "car"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_invalid_year_400(self):
        resp = _jwt(self.admin).post(
            VEH_URL,
            {"plate_number": "YR-BAD", "vehicle_type": "car", "year": 1800},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_future_year_400(self):
        resp = _jwt(self.admin).post(
            VEH_URL,
            {"plate_number": "YR-FUT", "vehicle_type": "car", "year": 2200},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_valid_year_201(self):
        current = timezone.now().year
        resp = _jwt(self.admin).post(
            VEH_URL,
            {"plate_number": "YR-NOW", "vehicle_type": "car", "year": current},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_get_detail_200(self):
        v = _vehicle(plate_number="DET-001")
        resp = _jwt(self.admin).get(f"{VEH_URL}{v.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["plate_number"], "DET-001")

    def test_nonexistent_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{VEH_URL}999999/").status_code, 404)

    def test_patch_updates_field(self):
        v = _vehicle(plate_number="PATCH-001")
        _jwt(self.admin).patch(f"{VEH_URL}{v.pk}/", {"make": "Nissan"}, format="json")
        v.refresh_from_db()
        self.assertEqual(v.make, "Nissan")

    def test_patch_plate_number(self):
        v = _vehicle(plate_number="PATCH-PLATE")
        resp = _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/", {"plate_number": "new-plate"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.plate_number, "NEW-PLATE")

    def test_deactivate(self):
        v = _vehicle(plate_number="DEACT-001")
        _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/status/", {"is_active": False}, format="json"
        )
        v.refresh_from_db()
        self.assertFalse(v.is_active)

    def test_reactivate(self):
        v = _vehicle(plate_number="REACT-001", is_active=False)
        _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/status/", {"is_active": True}, format="json"
        )
        v.refresh_from_db()
        self.assertTrue(v.is_active)

    def test_status_non_bool_400(self):
        v = _vehicle(plate_number="BOOL-001")
        resp = _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/status/", {"is_active": "yes"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_method_405(self):
        v = _vehicle(plate_number="DEL-001")
        self.assertEqual(_jwt(self.admin).delete(f"{VEH_URL}{v.pk}/").status_code, 405)

    def test_active_only_filter(self):
        _vehicle(plate_number="ACT-001"); _vehicle(plate_number="INACT-001", is_active=False)
        resp = _jwt(self.admin).get(VEH_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_vehicle_type_filter(self):
        _vehicle(plate_number="TRUCK-001", vehicle_type="truck")
        _vehicle(plate_number="CAR-001", vehicle_type="car")
        resp = _jwt(self.admin).get(VEH_URL + "?vehicle_type=truck")
        for r in resp.json()["results"]:
            self.assertEqual(r["vehicle_type"], "truck")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class TestVehicleAudit(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("aud_veh_admin", "System Administrator")

    def _count(self, action):
        return AuditEvent.objects.filter(action=action).count()

    def test_create_generates_audit(self):
        before = self._count(AuditAction.VEHICLE_CREATED)
        _post_vehicle(_jwt(self.admin), plate_number="AUD-C001")
        self.assertEqual(self._count(AuditAction.VEHICLE_CREATED), before + 1)

    def test_create_audit_actor(self):
        _post_vehicle(_jwt(self.admin), plate_number="AUD-C002")
        ev = AuditEvent.objects.filter(
            action=AuditAction.VEHICLE_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, self.admin.username)

    def test_create_audit_target_type(self):
        _post_vehicle(_jwt(self.admin), plate_number="AUD-C003")
        ev = AuditEvent.objects.filter(
            action=AuditAction.VEHICLE_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "violations.vehicle")

    def test_update_generates_audit(self):
        v = _vehicle(plate_number="AUD-U001")
        before = self._count(AuditAction.VEHICLE_UPDATED)
        _jwt(self.admin).patch(f"{VEH_URL}{v.pk}/", {"make": "X"}, format="json")
        self.assertEqual(self._count(AuditAction.VEHICLE_UPDATED), before + 1)

    def test_deactivate_generates_audit(self):
        v = _vehicle(plate_number="AUD-D001")
        before = self._count(AuditAction.VEHICLE_DEACTIVATED)
        _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(self._count(AuditAction.VEHICLE_DEACTIVATED), before + 1)

    def test_activate_generates_audit(self):
        v = _vehicle(plate_number="AUD-A001", is_active=False)
        before = self._count(AuditAction.VEHICLE_ACTIVATED)
        _jwt(self.admin).patch(
            f"{VEH_URL}{v.pk}/status/", {"is_active": True}, format="json"
        )
        self.assertEqual(self._count(AuditAction.VEHICLE_ACTIVATED), before + 1)

    def test_audit_detail_no_plate_number(self):
        _post_vehicle(_jwt(self.admin), plate_number="PII-AUDIT-001")
        for ev in AuditEvent.objects.filter(action=AuditAction.VEHICLE_CREATED):
            detail_str = str(ev.detail or "")
            self.assertNotIn("PII-AUDIT-001", detail_str)
            self.assertNotIn("plate_number", detail_str)

    def test_audit_detail_no_password(self):
        _post_vehicle(_jwt(self.admin), plate_number="SEC-001")
        for ev in AuditEvent.objects.filter(action=AuditAction.VEHICLE_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))

    def test_audit_detail_no_token(self):
        _post_vehicle(_jwt(self.admin), plate_number="SEC-002")
        for ev in AuditEvent.objects.filter(action=AuditAction.VEHICLE_CREATED):
            self.assertNotIn("access", str(ev.detail or ""))
            self.assertNotIn("refresh", str(ev.detail or ""))


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

class TestVehicleRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_traffic_incidents_still_work(self):
        admin = _make_role_user("reg_inc_veh", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/incidents/").status_code, 200)

    def test_auth_me_still_401(self):
        self.assertEqual(APIClient().get("/api/v1/auth/me/").status_code, 401)

    def test_no_pending_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending: {plan}")

    def test_django_check_passes(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("check", stdout=out, stderr=out)
        self.assertIn("no issues", out.getvalue().lower())
