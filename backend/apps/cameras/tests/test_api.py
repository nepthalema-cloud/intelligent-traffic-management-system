"""
API, RBAC, health, audit, and regression tests for the cameras app.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent
from apps.audit.services import AuditAction
from apps.cameras.models import Camera, CameraHealth, Sensor, SensorHealth
from apps.roads.models import Intersection, Road, RoadSegment

User = get_user_model()

CAMERAS_URL  = "/api/v1/cameras/"
SENSORS_URL  = "/api/v1/cameras/sensors/"


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


def _camera(**kw):
    kw.setdefault("name", "CAM-TEST")
    return Camera.objects.create(**kw)


def _sensor(**kw):
    kw.setdefault("name", "SEN-TEST")
    return Sensor.objects.create(**kw)


# ---------------------------------------------------------------------------
# 1. URL routing
# ---------------------------------------------------------------------------

class TestCameraUrlRouting(TestCase):
    def test_camera_list_resolves(self):
        m = resolve(CAMERAS_URL)
        self.assertEqual(m.url_name, "camera-list")
        self.assertEqual(m.namespace, "cameras")

    def test_camera_detail_resolves(self):
        self.assertEqual(resolve("/api/v1/cameras/1/").url_name, "camera-detail")

    def test_camera_status_resolves(self):
        self.assertEqual(resolve("/api/v1/cameras/1/status/").url_name, "camera-status")

    def test_camera_health_resolves(self):
        self.assertEqual(resolve("/api/v1/cameras/1/health/").url_name, "camera-health")

    def test_camera_monitoring_summary_resolves(self):
        self.assertEqual(resolve("/api/v1/cameras/monitoring-summary/").url_name, "camera-monitoring-summary")

    def test_sensor_list_resolves(self):
        m = resolve(SENSORS_URL)
        self.assertEqual(m.url_name, "sensor-list")

    def test_sensor_health_resolves(self):
        self.assertEqual(resolve("/api/v1/cameras/sensors/1/health/").url_name, "sensor-health")

    def test_camera_list_reverses(self):
        self.assertEqual(reverse("cameras:camera-list"), CAMERAS_URL)

    def test_sensor_list_reverses(self):
        self.assertEqual(reverse("cameras:sensor-list"), SENSORS_URL)


# ---------------------------------------------------------------------------
# 2. Authentication (unauthenticated → 401)
# ---------------------------------------------------------------------------

class TestCameraAuthentication(TestCase):
    def setUp(self):
        self.cam = _camera()
        self.sen = _sensor()

    def test_camera_list_401(self):
        self.assertEqual(APIClient().get(CAMERAS_URL).status_code, 401)

    def test_camera_post_401(self):
        self.assertEqual(APIClient().post(CAMERAS_URL).status_code, 401)

    def test_camera_detail_401(self):
        self.assertEqual(APIClient().get(f"{CAMERAS_URL}{self.cam.pk}/").status_code, 401)

    def test_camera_health_401(self):
        self.assertEqual(APIClient().get(f"{CAMERAS_URL}{self.cam.pk}/health/").status_code, 401)

    def test_sensor_list_401(self):
        self.assertEqual(APIClient().get(SENSORS_URL).status_code, 401)

    def test_sensor_post_401(self):
        self.assertEqual(APIClient().post(SENSORS_URL).status_code, 401)


# ---------------------------------------------------------------------------
# 3. RBAC
# ---------------------------------------------------------------------------

class TestCameraRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("rbac_admin",   "System Administrator")
        self.camtech = _make_role_user("rbac_camtech", "Camera/Sensor Technician")
        self.tco     = _make_role_user("rbac_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("rbac_analyst", "Traffic Analyst")
        self.law     = _make_role_user("rbac_law",     "Law Enforcement / Authorized Officer")
        self.pay     = _make_role_user("rbac_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("rbac_pub",     "Public User")
        self.cam = _camera(name="RBAC-CAM")

    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(CAMERAS_URL).status_code, 200)

    def test_camtech_can_list(self):
        self.assertEqual(_jwt(self.camtech).get(CAMERAS_URL).status_code, 200)

    def test_tco_can_read(self):
        self.assertEqual(_jwt(self.tco).get(CAMERAS_URL).status_code, 200)

    def test_analyst_can_read(self):
        self.assertEqual(_jwt(self.analyst).get(CAMERAS_URL).status_code, 200)

    def test_law_enforcement_403(self):
        self.assertEqual(_jwt(self.law).get(CAMERAS_URL).status_code, 403)

    def test_payment_officer_403(self):
        self.assertEqual(_jwt(self.pay).get(CAMERAS_URL).status_code, 403)

    def test_public_user_403(self):
        self.assertEqual(_jwt(self.pub).get(CAMERAS_URL).status_code, 403)

    def test_admin_can_create(self):
        resp = _jwt(self.admin).post(CAMERAS_URL, {"name": "ADM-CAM"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_camtech_can_create(self):
        resp = _jwt(self.camtech).post(CAMERAS_URL, {"name": "TECH-CAM"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_tco_cannot_create(self):
        resp = _jwt(self.tco).post(CAMERAS_URL, {"name": "TCO-CAM"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_analyst_cannot_create(self):
        resp = _jwt(self.analyst).post(CAMERAS_URL, {"name": "ANA-CAM"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_update(self):
        resp = _jwt(self.admin).patch(
            f"{CAMERAS_URL}{self.cam.pk}/", {"model": "Updated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_camtech_can_update(self):
        resp = _jwt(self.camtech).patch(
            f"{CAMERAS_URL}{self.cam.pk}/", {"model": "Tech Update"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_cannot_update(self):
        resp = _jwt(self.tco).patch(
            f"{CAMERAS_URL}{self.cam.pk}/", {"model": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_do_everything(self):
        su = User.objects.create_superuser("su_cam", password="SuPass!")
        resp = _jwt(su).post(CAMERAS_URL, {"name": "SU-CAM"}, format="json")
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# 4. Camera CRUD
# ---------------------------------------------------------------------------

class TestCameraMonitoringSummary(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("monitor_admin", "System Administrator")
        self.cam1 = _camera(name="MON-1", is_active=True)
        self.cam2 = _camera(name="MON-2", is_active=True)
        self.cam3 = _camera(name="MON-3", is_active=False)
        CameraHealth.objects.create(
            camera=self.cam1,
            health_status="healthy",
            connectivity_status="connected",
            last_seen="2026-08-30T00:00:00Z",
        )
        CameraHealth.objects.create(
            camera=self.cam2,
            health_status="offline",
            connectivity_status="disconnected",
            last_seen="2026-08-29T00:00:00Z",
        )

    def test_monitoring_summary_requires_auth(self):
        self.assertEqual(APIClient().get("/api/v1/cameras/monitoring-summary/").status_code, 401)

    def test_monitoring_summary_returns_counts(self):
        resp = _jwt(self.admin).get("/api/v1/cameras/monitoring-summary/")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()["data"]
        self.assertEqual(payload["total_cameras"], 3)
        self.assertEqual(payload["online_cameras"], 1)
        self.assertEqual(payload["offline_cameras"], 1)
        self.assertIn("cameras", payload)


class TestCameraCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("crud_admin", "System Administrator")

    def test_list_returns_200_with_pagination(self):
        _camera(name="C1"); _camera(name="C2")
        resp = _jwt(self.admin).get(CAMERAS_URL)
        self.assertEqual(resp.status_code, 200)
        for key in ("count", "results"):
            self.assertIn(key, resp.json())

    def test_create_camera(self):
        resp = _jwt(self.admin).post(
            CAMERAS_URL, {"name": "NEW-CAM", "camera_type": "ptz"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["name"], "NEW-CAM")

    def test_create_duplicate_name_400(self):
        _camera(name="DUP-CAM")
        self.assertEqual(
            _jwt(self.admin).post(CAMERAS_URL, {"name": "DUP-CAM"}, format="json").status_code,
            400,
        )

    def test_create_segment_and_intersection_together_400(self):
        seg = RoadSegment.objects.create(road=Road.objects.create(name="R"), lane_count=1)
        inter = Intersection.objects.create(name="I")
        resp = _jwt(self.admin).post(
            CAMERAS_URL,
            {"name": "BOTH-CAM", "segment": seg.pk, "intersection": inter.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_detail(self):
        cam = _camera(name="DETAIL-CAM")
        resp = _jwt(self.admin).get(f"{CAMERAS_URL}{cam.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "DETAIL-CAM")

    def test_get_nonexistent_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{CAMERAS_URL}999999/").status_code, 404)

    def test_patch_camera(self):
        cam = _camera(name="PATCH-CAM")
        resp = _jwt(self.admin).patch(
            f"{CAMERAS_URL}{cam.pk}/", {"model": "Axis P3245"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        cam.refresh_from_db()
        self.assertEqual(cam.model, "Axis P3245")

    def test_deactivate_camera(self):
        cam = _camera(name="DEACT-CAM")
        resp = _jwt(self.admin).patch(
            f"{CAMERAS_URL}{cam.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        cam.refresh_from_db()
        self.assertFalse(cam.is_active)

    def test_reactivate_camera(self):
        cam = _camera(name="REACT-CAM", is_active=False)
        resp = _jwt(self.admin).patch(
            f"{CAMERAS_URL}{cam.pk}/status/", {"is_active": True}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        cam.refresh_from_db()
        self.assertTrue(cam.is_active)

    def test_status_invalid_value_400(self):
        cam = _camera(name="BAD-STATUS-CAM")
        resp = _jwt(self.admin).patch(
            f"{CAMERAS_URL}{cam.pk}/status/", {"is_active": "yes"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_active_only_filter(self):
        _camera(name="ACT-CAM"); _camera(name="INACT-CAM", is_active=False)
        resp = _jwt(self.admin).get(CAMERAS_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_filter_by_segment(self):
        road = Road.objects.create(name="Filter Road")
        seg = RoadSegment.objects.create(road=road, lane_count=1)
        _camera(name="SEG-CAM", segment=seg)
        _camera(name="NO-SEG-CAM")
        resp = _jwt(self.admin).get(CAMERAS_URL + f"?segment={seg.pk}")
        self.assertTrue(all(r["segment"] == seg.pk for r in resp.json()["results"]))


# ---------------------------------------------------------------------------
# 5. Camera health
# ---------------------------------------------------------------------------

class TestCameraHealthAPI(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("health_admin", "System Administrator")
        self.camtech = _make_role_user("health_tech", "Camera/Sensor Technician")
        self.cam = _camera(name="HEALTH-API-CAM")

    def test_health_get_404_when_no_record(self):
        resp = _jwt(self.admin).get(f"{CAMERAS_URL}{self.cam.pk}/health/")
        self.assertEqual(resp.status_code, 404)

    def test_health_put_creates_record(self):
        resp = _jwt(self.admin).put(
            f"{CAMERAS_URL}{self.cam.pk}/health/",
            {"health_status": "healthy", "connectivity_status": "connected"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(CameraHealth.objects.filter(camera=self.cam).count(), 1)

    def test_health_put_replaces_existing(self):
        CameraHealth.objects.create(
            camera=self.cam, health_status="healthy", connectivity_status="connected"
        )
        _jwt(self.admin).put(
            f"{CAMERAS_URL}{self.cam.pk}/health/",
            {"health_status": "offline", "connectivity_status": "disconnected"},
            format="json",
        )
        self.assertEqual(CameraHealth.objects.filter(camera=self.cam).count(), 1)
        h = CameraHealth.objects.get(camera=self.cam)
        self.assertEqual(h.health_status, "offline")

    def test_health_get_after_put(self):
        _jwt(self.admin).put(
            f"{CAMERAS_URL}{self.cam.pk}/health/",
            {"health_status": "degraded", "connectivity_status": "connected"},
            format="json",
        )
        resp = _jwt(self.admin).get(f"{CAMERAS_URL}{self.cam.pk}/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["health_status"], "degraded")

    def test_camtech_can_update_health(self):
        resp = _jwt(self.camtech).put(
            f"{CAMERAS_URL}{self.cam.pk}/health/",
            {"health_status": "healthy", "connectivity_status": "connected"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_health_for_nonexistent_camera_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{CAMERAS_URL}999999/health/").status_code, 404)


# ---------------------------------------------------------------------------
# 6. Sensor CRUD
# ---------------------------------------------------------------------------

class TestSensorCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("sen_admin", "System Administrator")

    def test_create_sensor(self):
        resp = _jwt(self.admin).post(
            SENSORS_URL, {"name": "NEW-SEN", "sensor_type": "radar"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["name"], "NEW-SEN")

    def test_create_duplicate_sensor_400(self):
        _sensor(name="DUP-SEN")
        self.assertEqual(
            _jwt(self.admin).post(SENSORS_URL, {"name": "DUP-SEN"}, format="json").status_code,
            400,
        )

    def test_list_sensors(self):
        _sensor(name="S1"); _sensor(name="S2")
        resp = _jwt(self.admin).get(SENSORS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 2)

    def test_get_sensor_detail(self):
        sen = _sensor(name="DETAIL-SEN")
        resp = _jwt(self.admin).get(f"{SENSORS_URL}{sen.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "DETAIL-SEN")

    def test_get_nonexistent_sensor_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{SENSORS_URL}999999/").status_code, 404)

    def test_patch_sensor(self):
        sen = _sensor(name="PATCH-SEN")
        resp = _jwt(self.admin).patch(
            f"{SENSORS_URL}{sen.pk}/", {"model": "Inductive X2"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        sen.refresh_from_db()
        self.assertEqual(sen.model, "Inductive X2")

    def test_deactivate_sensor(self):
        sen = _sensor(name="DEACT-SEN")
        resp = _jwt(self.admin).patch(
            f"{SENSORS_URL}{sen.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        sen.refresh_from_db()
        self.assertFalse(sen.is_active)

    def test_sensor_active_only_filter(self):
        _sensor(name="ACT-SEN"); _sensor(name="INACT-SEN", is_active=False)
        resp = _jwt(self.admin).get(SENSORS_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_sensor_camtech_can_create(self):
        camtech = _make_role_user("sen_tech", "Camera/Sensor Technician")
        resp = _jwt(camtech).post(SENSORS_URL, {"name": "TECH-SEN"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_sensor_tco_cannot_create(self):
        tco = _make_role_user("sen_tco", "Traffic Control Officer")
        resp = _jwt(tco).post(SENSORS_URL, {"name": "TCO-SEN"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_sensor_segment_and_intersection_together_400(self):
        seg = RoadSegment.objects.create(road=Road.objects.create(name="SR"), lane_count=1)
        inter = Intersection.objects.create(name="SI")
        resp = _jwt(self.admin).post(
            SENSORS_URL,
            {"name": "BOTH-SEN", "segment": seg.pk, "intersection": inter.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 7. Sensor health
# ---------------------------------------------------------------------------

class TestSensorHealthAPI(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("shen_admin", "System Administrator")
        self.sen = _sensor(name="HEALTH-API-SEN")

    def test_sensor_health_404_when_no_record(self):
        resp = _jwt(self.admin).get(f"{SENSORS_URL}{self.sen.pk}/health/")
        self.assertEqual(resp.status_code, 404)

    def test_sensor_health_put_creates(self):
        resp = _jwt(self.admin).put(
            f"{SENSORS_URL}{self.sen.pk}/health/",
            {"health_status": "healthy", "connectivity_status": "connected"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SensorHealth.objects.filter(sensor=self.sen).count(), 1)

    def test_sensor_health_replace_latest(self):
        SensorHealth.objects.create(
            sensor=self.sen, health_status="healthy", connectivity_status="connected"
        )
        _jwt(self.admin).put(
            f"{SENSORS_URL}{self.sen.pk}/health/",
            {"health_status": "offline", "connectivity_status": "disconnected"},
            format="json",
        )
        self.assertEqual(SensorHealth.objects.filter(sensor=self.sen).count(), 1)
        h = SensorHealth.objects.get(sensor=self.sen)
        self.assertEqual(h.health_status, "offline")

    def test_sensor_health_get_returns_data(self):
        SensorHealth.objects.create(
            sensor=self.sen, health_status="degraded", connectivity_status="connected"
        )
        resp = _jwt(self.admin).get(f"{SENSORS_URL}{self.sen.pk}/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["health_status"], "degraded")


# ---------------------------------------------------------------------------
# 8. Audit events
# ---------------------------------------------------------------------------

class TestCameraAuditEvents(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("aud_admin", "System Administrator")

    def test_camera_created_audit_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.CAMERA_CREATED).count()
        _jwt(self.admin).post(CAMERAS_URL, {"name": "AUD-CAM"}, format="json")
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.CAMERA_CREATED).count(),
            before + 1,
        )

    def test_camera_creation_audit_records_actor(self):
        _jwt(self.admin).post(CAMERAS_URL, {"name": "ACT-AUD-CAM"}, format="json")
        ev = AuditEvent.objects.filter(action=AuditAction.CAMERA_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, "aud_admin")

    def test_camera_creation_audit_target_type(self):
        _jwt(self.admin).post(CAMERAS_URL, {"name": "TGT-AUD-CAM"}, format="json")
        ev = AuditEvent.objects.filter(action=AuditAction.CAMERA_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "cameras.camera")

    def test_camera_update_audit_event(self):
        cam = _camera(name="UPD-AUD-CAM")
        before = AuditEvent.objects.filter(action=AuditAction.CAMERA_UPDATED).count()
        _jwt(self.admin).patch(f"{CAMERAS_URL}{cam.pk}/", {"model": "X"}, format="json")
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.CAMERA_UPDATED).count(),
            before + 1,
        )

    def test_camera_deactivation_audit_event(self):
        cam = _camera(name="DEACT-AUD-CAM")
        before = AuditEvent.objects.filter(action=AuditAction.CAMERA_DEACTIVATED).count()
        _jwt(self.admin).patch(
            f"{CAMERAS_URL}{cam.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.CAMERA_DEACTIVATED).count(),
            before + 1,
        )

    def test_sensor_created_audit_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.SENSOR_CREATED).count()
        _jwt(self.admin).post(SENSORS_URL, {"name": "AUD-SEN"}, format="json")
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.SENSOR_CREATED).count(),
            before + 1,
        )

    def test_sensor_deactivation_audit_event(self):
        sen = _sensor(name="DEACT-AUD-SEN")
        before = AuditEvent.objects.filter(action=AuditAction.SENSOR_DEACTIVATED).count()
        _jwt(self.admin).patch(
            f"{SENSORS_URL}{sen.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.SENSOR_DEACTIVATED).count(),
            before + 1,
        )

    def test_health_update_does_not_create_audit_event(self):
        """Health updates must NOT be audited per architecture doc."""
        cam = _camera(name="NO-AUD-HEALTH-CAM")
        before = AuditEvent.objects.count()
        _jwt(self.admin).put(
            f"{CAMERAS_URL}{cam.pk}/health/",
            {"health_status": "healthy", "connectivity_status": "connected"},
            format="json",
        )
        # No new audit events should be created by health update
        after = AuditEvent.objects.count()
        self.assertEqual(after, before)

    def test_audit_detail_no_password(self):
        _jwt(self.admin).post(CAMERAS_URL, {"name": "SEC-CAM"}, format="json")
        for ev in AuditEvent.objects.filter(action=AuditAction.CAMERA_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))


# ---------------------------------------------------------------------------
# 9. Regression
# ---------------------------------------------------------------------------

class TestCameraRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_endpoint_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_url_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_auth_me_still_works(self):
        user = _make_role_user("reg_cam_user", "Traffic Analyst")
        resp = _jwt(user).get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)

    def test_roads_still_work(self):
        admin = _make_role_user("reg_roads_admin", "System Administrator")
        resp = _jwt(admin).get("/api/v1/roads/")
        self.assertEqual(resp.status_code, 200)

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
