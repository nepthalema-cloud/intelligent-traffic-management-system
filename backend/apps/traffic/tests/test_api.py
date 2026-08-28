# Tests for the traffic app API - Phase 4C.1
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent
from apps.audit.services import AuditAction
from apps.roads.models import Intersection
from apps.traffic.models import SignalPhase, TrafficSignal

User = get_user_model()
SIGNALS_URL = "/api/v1/traffic/signals/"


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


def _intersection(**kw):
    kw.setdefault("name", "Test Jct")
    return Intersection.objects.create(**kw)


def _signal(intersection=None, **kw):
    kw.setdefault("name", "SIG-T")
    return TrafficSignal.objects.create(
        intersection=intersection or _intersection(), **kw
    )


def _phase(signal, **kw):
    kw.setdefault("phase_number", 1)
    kw.setdefault("name", "Phase 1")
    kw.setdefault("minimum_green_seconds", 15)
    kw.setdefault("maximum_green_seconds", 60)
    kw.setdefault("yellow_seconds", 4)
    kw.setdefault("all_red_seconds", 2)
    return SignalPhase.objects.create(signal=signal, **kw)


def _phase_url(signal, suffix=""):
    return f"{SIGNALS_URL}{signal.pk}/phases/{suffix}"


class TestTrafficUrlRouting(TestCase):
    def test_signal_list_resolves(self):
        m = resolve(SIGNALS_URL)
        self.assertEqual(m.url_name, "signal-list")
        self.assertEqual(m.namespace, "traffic")

    def test_signal_list_reverses(self):
        self.assertEqual(reverse("traffic:signal-list"), SIGNALS_URL)

    def test_signal_detail_resolves(self):
        self.assertEqual(resolve(f"{SIGNALS_URL}1/").url_name, "signal-detail")

    def test_signal_status_resolves(self):
        self.assertEqual(resolve(f"{SIGNALS_URL}1/status/").url_name, "signal-status")

    def test_phase_list_resolves(self):
        self.assertEqual(resolve(f"{SIGNALS_URL}1/phases/").url_name, "phase-list")

    def test_phase_detail_resolves(self):
        self.assertEqual(resolve(f"{SIGNALS_URL}1/phases/2/").url_name, "phase-detail")

    def test_phase_status_resolves(self):
        self.assertEqual(resolve(f"{SIGNALS_URL}1/phases/2/status/").url_name, "phase-status")

    def test_invalid_prefix_404(self):
        self.assertEqual(APIClient().get("/api/traffic/signals/").status_code, 404)
        self.assertEqual(APIClient().get("/api/v1/v1/traffic/signals/").status_code, 404)


class TestTrafficAuthentication(TestCase):
    def setUp(self):
        self.sig = _signal()

    def test_signal_list_401(self):
        self.assertEqual(APIClient().get(SIGNALS_URL).status_code, 401)

    def test_signal_post_401(self):
        self.assertEqual(APIClient().post(SIGNALS_URL).status_code, 401)

    def test_signal_detail_401(self):
        self.assertEqual(APIClient().get(f"{SIGNALS_URL}{self.sig.pk}/").status_code, 401)

    def test_signal_status_401(self):
        self.assertEqual(
            APIClient().patch(f"{SIGNALS_URL}{self.sig.pk}/status/").status_code, 401
        )

    def test_phase_list_401(self):
        self.assertEqual(APIClient().get(_phase_url(self.sig)).status_code, 401)

    def test_phase_post_401(self):
        self.assertEqual(APIClient().post(_phase_url(self.sig)).status_code, 401)


class TestTrafficRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("rbac_admin",   "System Administrator")
        self.tco     = _make_role_user("rbac_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("rbac_analyst", "Traffic Analyst")
        self.law     = _make_role_user("rbac_law",     "Law Enforcement / Authorized Officer")
        self.cam     = _make_role_user("rbac_cam",     "Camera/Sensor Technician")
        self.pay     = _make_role_user("rbac_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("rbac_pub",     "Public User")
        self.inter   = _intersection(name="RBAC Jct")
        self.sig     = _signal(self.inter, name="RBAC-SIG")

    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(SIGNALS_URL).status_code, 200)

    def test_tco_can_list(self):
        self.assertEqual(_jwt(self.tco).get(SIGNALS_URL).status_code, 200)

    def test_analyst_can_list(self):
        self.assertEqual(_jwt(self.analyst).get(SIGNALS_URL).status_code, 200)

    def test_law_403(self):
        self.assertEqual(_jwt(self.law).get(SIGNALS_URL).status_code, 403)

    def test_cam_403(self):
        self.assertEqual(_jwt(self.cam).get(SIGNALS_URL).status_code, 403)

    def test_pay_403(self):
        self.assertEqual(_jwt(self.pay).get(SIGNALS_URL).status_code, 403)

    def test_pub_403(self):
        self.assertEqual(_jwt(self.pub).get(SIGNALS_URL).status_code, 403)

    def test_admin_can_create(self):
        inter = _intersection(name="Admin Create Jct")
        resp = _jwt(self.admin).post(
            SIGNALS_URL, {"name": "ADMIN-NEW", "intersection": inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_tco_can_create(self):
        inter = _intersection(name="TCO Create Jct")
        resp = _jwt(self.tco).post(
            SIGNALS_URL, {"name": "TCO-NEW", "intersection": inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_analyst_cannot_create(self):
        inter = _intersection(name="Analyst Create Jct")
        resp = _jwt(self.analyst).post(
            SIGNALS_URL, {"name": "ANA-NEW", "intersection": inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_create(self):
        su = User.objects.create_superuser("su_traffic", password="SuPass!")
        inter = _intersection(name="SU Jct")
        resp = _jwt(su).post(
            SIGNALS_URL, {"name": "SU-SIG", "intersection": inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_admin_can_update(self):
        resp = _jwt(self.admin).patch(
            f"{SIGNALS_URL}{self.sig.pk}/", {"controller_type": "Siemens"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_can_update(self):
        resp = _jwt(self.tco).patch(
            f"{SIGNALS_URL}{self.sig.pk}/", {"controller_type": "SWARCO"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_analyst_cannot_update(self):
        resp = _jwt(self.analyst).patch(
            f"{SIGNALS_URL}{self.sig.pk}/", {"controller_type": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_tco_can_create_phase(self):
        resp = _jwt(self.tco).post(
            _phase_url(self.sig),
            {"phase_number": 1, "name": "Ph 1",
             "minimum_green_seconds": 10, "maximum_green_seconds": 45,
             "yellow_seconds": 3, "all_red_seconds": 2},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_analyst_cannot_create_phase(self):
        resp = _jwt(self.analyst).post(
            _phase_url(self.sig),
            {"phase_number": 1, "name": "Ph 1",
             "minimum_green_seconds": 10, "maximum_green_seconds": 45,
             "yellow_seconds": 3, "all_red_seconds": 2},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_tco_can_deactivate_signal(self):
        resp = _jwt(self.tco).patch(
            f"{SIGNALS_URL}{self.sig.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)


class TestSignalCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("crud_admin", "System Administrator")
        self.inter = _intersection(name="CRUD Jct")

    def test_list_200_with_pagination(self):
        _signal(self.inter, name="S1"); _signal(self.inter, name="S2")
        resp = _jwt(self.admin).get(SIGNALS_URL)
        self.assertEqual(resp.status_code, 200)
        for k in ("count", "results"):
            self.assertIn(k, resp.json())

    def test_create_201(self):
        resp = _jwt(self.admin).post(
            SIGNALS_URL, {"name": "NEW-SIG", "intersection": self.inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["name"], "NEW-SIG")

    def test_create_duplicate_400(self):
        _signal(self.inter, name="DUP-SIG")
        resp = _jwt(self.admin).post(
            SIGNALS_URL, {"name": "DUP-SIG", "intersection": self.inter.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_missing_intersection_400(self):
        resp = _jwt(self.admin).post(SIGNALS_URL, {"name": "NO-INT"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_detail_200(self):
        sig = _signal(self.inter, name="DETAIL-SIG")
        resp = _jwt(self.admin).get(f"{SIGNALS_URL}{sig.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "DETAIL-SIG")

    def test_nonexistent_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{SIGNALS_URL}999999/").status_code, 404)

    def test_patch_signal(self):
        sig = _signal(self.inter, name="PATCH-SIG")
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/", {"controller_type": "Siemens"}, format="json"
        )
        sig.refresh_from_db()
        self.assertEqual(sig.controller_type, "Siemens")

    def test_deactivate(self):
        sig = _signal(self.inter, name="DEACT-SIG")
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/status/", {"is_active": False}, format="json"
        )
        sig.refresh_from_db()
        self.assertFalse(sig.is_active)

    def test_reactivate(self):
        sig = _signal(self.inter, name="REACT-SIG", is_active=False)
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/status/", {"is_active": True}, format="json"
        )
        sig.refresh_from_db()
        self.assertTrue(sig.is_active)

    def test_status_non_bool_400(self):
        sig = _signal(self.inter, name="BOOL-SIG")
        resp = _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/status/", {"is_active": "yes"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_active_only_filter(self):
        _signal(self.inter, name="ACT"); _signal(self.inter, name="INACT", is_active=False)
        resp = _jwt(self.admin).get(SIGNALS_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_intersection_filter(self):
        inter2 = _intersection(name="Other Jct")
        _signal(self.inter, name="S-INT1"); _signal(inter2, name="S-INT2")
        resp = _jwt(self.admin).get(SIGNALS_URL + f"?intersection={self.inter.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["intersection"], self.inter.pk)

    def test_response_includes_intersection_name(self):
        sig = _signal(self.inter, name="NAME-SIG")
        resp = _jwt(self.admin).get(f"{SIGNALS_URL}{sig.pk}/")
        self.assertEqual(resp.json()["data"]["intersection_name"], self.inter.name)


class TestPhaseCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("phase_admin", "System Administrator")
        self.inter = _intersection(name="Phase Jct")
        self.sig   = _signal(self.inter, name="PHASE-SIG")

    def _post(self, **kw):
        return _jwt(self.admin).post(
            _phase_url(self.sig),
            {"phase_number": kw.get("pn", 1), "name": kw.get("name", "Ph"),
             "minimum_green_seconds": kw.get("min_g", 10),
             "maximum_green_seconds": kw.get("max_g", 40),
             "yellow_seconds": kw.get("yellow", 4),
             "all_red_seconds": kw.get("red", 2)},
            format="json",
        )

    def test_create_phase_201(self):
        self.assertEqual(self._post().status_code, 201)

    def test_create_duplicate_phase_number_400(self):
        self._post(pn=1)
        self.assertEqual(self._post(pn=1).status_code, 400)

    def test_same_phase_number_different_signals_ok(self):
        sig2 = _signal(self.inter, name="SIG-OTHER-PHASE")
        self._post(pn=1)
        resp = _jwt(self.admin).post(
            _phase_url(sig2),
            {"phase_number": 1, "name": "P1b",
             "minimum_green_seconds": 10, "maximum_green_seconds": 40,
             "yellow_seconds": 4, "all_red_seconds": 2},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_invalid_timing_range_400(self):
        resp = _jwt(self.admin).post(
            _phase_url(self.sig),
            {"phase_number": 1, "name": "Bad",
             "minimum_green_seconds": 50, "maximum_green_seconds": 10,
             "yellow_seconds": 4, "all_red_seconds": 2},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_inactive_signal_rejects_phase_creation(self):
        self.sig.is_active = False; self.sig.save()
        self.assertEqual(self._post().status_code, 400)

    def test_list_phases_scoped_to_signal(self):
        _phase(self.sig, phase_number=1); _phase(self.sig, phase_number=2)
        resp = _jwt(self.admin).get(_phase_url(self.sig))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 2)

    def test_phase_detail_200(self):
        ph = _phase(self.sig, phase_number=1, name="North Green")
        resp = _jwt(self.admin).get(_phase_url(self.sig, f"{ph.pk}/"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "North Green")

    def test_nonexistent_phase_404(self):
        self.assertEqual(_jwt(self.admin).get(_phase_url(self.sig, "999999/")).status_code, 404)

    def test_patch_phase(self):
        ph = _phase(self.sig, phase_number=1, name="Old")
        _jwt(self.admin).patch(_phase_url(self.sig, f"{ph.pk}/"), {"name": "New"}, format="json")
        ph.refresh_from_db()
        self.assertEqual(ph.name, "New")

    def test_patch_cannot_change_phase_number(self):
        ph = _phase(self.sig, phase_number=1)
        _jwt(self.admin).patch(_phase_url(self.sig, f"{ph.pk}/"), {"phase_number": 9}, format="json")
        ph.refresh_from_db()
        self.assertEqual(ph.phase_number, 1)

    def test_deactivate_phase(self):
        ph = _phase(self.sig, phase_number=1)
        _jwt(self.admin).patch(
            _phase_url(self.sig, f"{ph.pk}/status/"), {"is_active": False}, format="json"
        )
        ph.refresh_from_db()
        self.assertFalse(ph.is_active)

    def test_active_only_filter_phases(self):
        _phase(self.sig, phase_number=1)
        _phase(self.sig, phase_number=2, is_active=False)
        resp = _jwt(self.admin).get(_phase_url(self.sig) + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_response_includes_signal_name(self):
        ph = _phase(self.sig, phase_number=1)
        resp = _jwt(self.admin).get(_phase_url(self.sig, f"{ph.pk}/"))
        self.assertEqual(resp.json()["data"]["signal_name"], self.sig.name)

    def test_phase_wrong_signal_404(self):
        sig2 = _signal(self.inter, name="SIG2-SCOPE")
        ph = _phase(self.sig, phase_number=1)
        self.assertEqual(
            _jwt(self.admin).get(f"{SIGNALS_URL}{sig2.pk}/phases/{ph.pk}/").status_code, 404
        )


class TestTrafficAuditEvents(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("aud_t_admin", "System Administrator")
        self.inter = _intersection(name="Audit Jct")

    def _count(self, action):
        return AuditEvent.objects.filter(action=action).count()

    def test_signal_created_audit(self):
        before = self._count(AuditAction.TRAFFIC_SIGNAL_CREATED)
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "AUD-SIG", "intersection": self.inter.pk}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_SIGNAL_CREATED), before + 1)

    def test_signal_created_audit_actor(self):
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "ACT-AUD-SIG", "intersection": self.inter.pk}, format="json"
        )
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_SIGNAL_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, "aud_t_admin")

    def test_signal_created_audit_target_type(self):
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "TGT-AUD-SIG", "intersection": self.inter.pk}, format="json"
        )
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_SIGNAL_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "traffic.trafficsignal")

    def test_signal_updated_audit(self):
        sig = _signal(self.inter, name="UPD-AUD-SIG")
        before = self._count(AuditAction.TRAFFIC_SIGNAL_UPDATED)
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/", {"controller_type": "X"}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_SIGNAL_UPDATED), before + 1)

    def test_signal_deactivated_audit(self):
        sig = _signal(self.inter, name="DEACT-AUD-SIG")
        before = self._count(AuditAction.TRAFFIC_SIGNAL_DEACTIVATED)
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_SIGNAL_DEACTIVATED), before + 1)

    def test_signal_activated_audit(self):
        sig = _signal(self.inter, name="ACT-AUD-SIG2", is_active=False)
        before = self._count(AuditAction.TRAFFIC_SIGNAL_ACTIVATED)
        _jwt(self.admin).patch(
            f"{SIGNALS_URL}{sig.pk}/status/", {"is_active": True}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_SIGNAL_ACTIVATED), before + 1)

    def test_phase_created_audit(self):
        sig = _signal(self.inter, name="PHASE-AUD-SIG")
        before = self._count(AuditAction.SIGNAL_PHASE_CREATED)
        _jwt(self.admin).post(
            _phase_url(sig),
            {"phase_number": 1, "name": "Ph",
             "minimum_green_seconds": 10, "maximum_green_seconds": 40,
             "yellow_seconds": 4, "all_red_seconds": 2},
            format="json",
        )
        self.assertEqual(self._count(AuditAction.SIGNAL_PHASE_CREATED), before + 1)

    def test_phase_created_audit_target_type(self):
        sig = _signal(self.inter, name="PHASE-TGT-SIG")
        _jwt(self.admin).post(
            _phase_url(sig),
            {"phase_number": 1, "name": "Ph",
             "minimum_green_seconds": 10, "maximum_green_seconds": 40,
             "yellow_seconds": 4, "all_red_seconds": 2},
            format="json",
        )
        ev = AuditEvent.objects.filter(
            action=AuditAction.SIGNAL_PHASE_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "traffic.signalphase")

    def test_phase_updated_audit(self):
        sig = _signal(self.inter, name="PHASE-UPD-SIG")
        ph = _phase(sig, phase_number=1)
        before = self._count(AuditAction.SIGNAL_PHASE_UPDATED)
        _jwt(self.admin).patch(
            _phase_url(sig, f"{ph.pk}/"), {"name": "Updated"}, format="json"
        )
        self.assertEqual(self._count(AuditAction.SIGNAL_PHASE_UPDATED), before + 1)

    def test_phase_deactivated_audit(self):
        sig = _signal(self.inter, name="PHASE-DEACT-SIG")
        ph = _phase(sig, phase_number=1)
        before = self._count(AuditAction.SIGNAL_PHASE_DEACTIVATED)
        _jwt(self.admin).patch(
            _phase_url(sig, f"{ph.pk}/status/"), {"is_active": False}, format="json"
        )
        self.assertEqual(self._count(AuditAction.SIGNAL_PHASE_DEACTIVATED), before + 1)

    def test_no_password_in_audit_detail(self):
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "SEC-SIG", "intersection": self.inter.pk}, format="json"
        )
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_SIGNAL_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))

    def test_no_token_in_audit_detail(self):
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "TOK-SIG", "intersection": self.inter.pk}, format="json"
        )
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_SIGNAL_CREATED):
            self.assertNotIn("access", str(ev.detail or ""))
            self.assertNotIn("refresh", str(ev.detail or ""))

    def test_audit_detail_intersection_id(self):
        _jwt(self.admin).post(
            SIGNALS_URL, {"name": "INT-ID-SIG", "intersection": self.inter.pk}, format="json"
        )
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_SIGNAL_CREATED).latest("timestamp")
        self.assertEqual(ev.detail.get("intersection_id"), self.inter.pk)


class TestTrafficRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_auth_me_protected(self):
        self.assertEqual(APIClient().get("/api/v1/auth/me/").status_code, 401)

    def test_roads_still_work(self):
        admin = _make_role_user("reg_roads", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/roads/").status_code, 200)

    def test_cameras_still_work(self):
        admin = _make_role_user("reg_cams", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/cameras/").status_code, 200)

    def test_audit_api_still_works(self):
        admin = _make_role_user("reg_audit", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/audit/events/").status_code, 200)

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
