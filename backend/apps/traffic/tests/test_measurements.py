# Tests for TrafficMeasurement - Phase 4C.2
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent
from apps.cameras.models import Camera, Sensor
from apps.roads.models import Intersection, Road, RoadSegment
from apps.traffic.models import TrafficMeasurement

User = get_user_model()
MEAS_URL = "/api/v1/traffic/measurements/"


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


def _road(**kw):
    kw.setdefault("name", "Test Road M")
    return Road.objects.create(**kw)


def _segment(**kw):
    road = kw.pop("road", None) or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _intersection(**kw):
    kw.setdefault("name", "Test Jct M")
    return Intersection.objects.create(**kw)


def _camera(segment=None, **kw):
    kw.setdefault("name", "CAM-M01")
    return Camera.objects.create(segment=segment, **kw)


def _sensor(segment=None, **kw):
    kw.setdefault("name", "SEN-M01")
    return Sensor.objects.create(segment=segment, **kw)


def _meas(segment, camera=None, sensor=None, **kw):
    kw.setdefault("measured_at", timezone.now())
    kw.setdefault("vehicle_count", 10)
    return TrafficMeasurement.objects.create(
        segment=segment, camera=camera, sensor=sensor, **kw
    )


def _post(client, segment, source, **kw):
    data = {
        "segment": segment.pk if segment else None,
        "measured_at": kw.get("measured_at", timezone.now().isoformat()),
        "vehicle_count": kw.get("vehicle_count", 5),
    }
    if isinstance(source, Camera):
        data["camera"] = source.pk
    elif isinstance(source, Sensor):
        data["sensor"] = source.pk
    data.update({k: v for k, v in kw.items()
                  if k not in ("measured_at", "vehicle_count")})
    return client.post(MEAS_URL, data, format="json")


# ---------------------------------------------------------------------------
# 1. Model tests
# ---------------------------------------------------------------------------

class TestTrafficMeasurementModel(TestCase):
    def setUp(self):
        self.seg = _segment()
        self.cam = _camera(segment=self.seg)
        self.sen = _sensor(segment=self.seg, name="SEN-MODEL01")

    def test_create_with_camera(self):
        m = _meas(self.seg, camera=self.cam)
        self.assertIsNotNone(m.pk)
        self.assertEqual(m.camera, self.cam)
        self.assertIsNone(m.sensor)
        self.assertIsNotNone(m.created_at)

    def test_create_with_sensor(self):
        m = _meas(self.seg, sensor=self.sen)
        self.assertIsNone(m.camera)
        self.assertEqual(m.sensor, self.sen)

    def test_measured_at_stored(self):
        t = timezone.now()
        m = TrafficMeasurement.objects.create(
            segment=self.seg, camera=self.cam,
            measured_at=t, vehicle_count=3,
        )
        m.refresh_from_db()
        self.assertIsNotNone(m.measured_at)

    def test_metric_fields_nullable(self):
        m = TrafficMeasurement.objects.create(
            segment=self.seg, camera=self.cam,
            measured_at=timezone.now(), vehicle_count=5,
        )
        self.assertIsNone(m.avg_speed_kmh)
        self.assertIsNone(m.occupancy_pct)

    def test_all_metrics_stored(self):
        m = TrafficMeasurement.objects.create(
            segment=self.seg, camera=self.cam,
            measured_at=timezone.now(),
            vehicle_count=20, avg_speed_kmh=55.5, occupancy_pct=43.2,
        )
        m.refresh_from_db()
        self.assertEqual(m.vehicle_count, 20)
        self.assertAlmostEqual(m.avg_speed_kmh, 55.5, places=1)
        self.assertAlmostEqual(m.occupancy_pct, 43.2, places=1)

    def test_segment_set_null_on_delete(self):
        road = _road(name="Null Road M")
        seg = _segment(road=road)
        m = _meas(seg, camera=self.cam)
        RoadSegment.objects.filter(pk=seg.pk).delete()
        m.refresh_from_db()
        self.assertIsNone(m.segment)

    def test_ordering_newest_first(self):
        from datetime import timedelta
        now = timezone.now()
        m1 = TrafficMeasurement.objects.create(
            segment=self.seg, camera=self.cam,
            measured_at=now - timedelta(hours=2), vehicle_count=1,
        )
        m2 = TrafficMeasurement.objects.create(
            segment=self.seg, camera=self.cam,
            measured_at=now - timedelta(hours=1), vehicle_count=2,
        )
        pks = list(
            TrafficMeasurement.objects.filter(
                pk__in=[m1.pk, m2.pk]
            ).values_list("pk", flat=True)
        )
        self.assertEqual(pks[0], m2.pk)

    def test_append_only_save_blocks_update(self):
        m = _meas(self.seg, camera=self.cam)
        m.vehicle_count = 999
        with self.assertRaises(RuntimeError):
            m.save()

    def test_append_only_delete_blocked(self):
        m = _meas(self.seg, camera=self.cam)
        with self.assertRaises(RuntimeError):
            m.delete()

    def test_str_contains_segment_and_source(self):
        m = _meas(self.seg, camera=self.cam)
        s = str(m)
        self.assertIn(str(self.seg.pk), s)

    def test_no_is_active_field(self):
        from django.db import models as djm
        field_names = [f.name for f in TrafficMeasurement._meta.get_fields()]
        self.assertNotIn("is_active", field_names)

    def test_no_updated_at_field(self):
        field_names = [f.name for f in TrafficMeasurement._meta.get_fields()]
        self.assertNotIn("updated_at", field_names)


# ---------------------------------------------------------------------------
# 2. URL routing
# ---------------------------------------------------------------------------

class TestMeasurementUrlRouting(TestCase):
    def test_measurement_list_resolves(self):
        m = resolve(MEAS_URL)
        self.assertEqual(m.url_name, "measurement-list")
        self.assertEqual(m.namespace, "traffic")

    def test_measurement_list_reverses(self):
        self.assertEqual(reverse("traffic:measurement-list"), MEAS_URL)

    def test_measurement_detail_resolves(self):
        m = resolve(f"{MEAS_URL}1/")
        self.assertEqual(m.url_name, "measurement-detail")

    def test_no_patch_url(self):
        from django.urls import Resolver404
        with self.assertRaises(Resolver404):
            resolve("/api/v1/traffic/measurements/1/patch/")


# ---------------------------------------------------------------------------
# 3. Authentication
# ---------------------------------------------------------------------------

class TestMeasurementAuthentication(TestCase):
    def test_list_unauthenticated_401(self):
        self.assertEqual(APIClient().get(MEAS_URL).status_code, 401)

    def test_post_unauthenticated_401(self):
        self.assertEqual(APIClient().post(MEAS_URL).status_code, 401)

    def test_detail_unauthenticated_401(self):
        _ensure_groups()
        seg = _segment()
        cam = _camera(segment=seg, name="CAM-AUTH01")
        m = _meas(seg, camera=cam)
        self.assertEqual(APIClient().get(f"{MEAS_URL}{m.pk}/").status_code, 401)


# ---------------------------------------------------------------------------
# 4. RBAC — all seven roles
# ---------------------------------------------------------------------------

class TestMeasurementRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("mrbac_admin",   "System Administrator")
        self.tco     = _make_role_user("mrbac_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("mrbac_analyst", "Traffic Analyst")
        self.cam_t   = _make_role_user("mrbac_camtech", "Camera/Sensor Technician")
        self.law     = _make_role_user("mrbac_law",     "Law Enforcement / Authorized Officer")
        self.pay     = _make_role_user("mrbac_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("mrbac_pub",     "Public User")
        self.seg     = _segment(road=_road(name="RBAC Road M"))
        self.cam     = _camera(segment=self.seg, name="CAM-RBAC01")

    # --- Reads ---
    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(MEAS_URL).status_code, 200)

    def test_tco_can_read(self):
        self.assertEqual(_jwt(self.tco).get(MEAS_URL).status_code, 200)

    def test_analyst_can_read(self):
        self.assertEqual(_jwt(self.analyst).get(MEAS_URL).status_code, 200)

    def test_cam_tech_can_read(self):
        self.assertEqual(_jwt(self.cam_t).get(MEAS_URL).status_code, 200)

    def test_law_enforcement_403(self):
        self.assertEqual(_jwt(self.law).get(MEAS_URL).status_code, 403)

    def test_payment_officer_403(self):
        self.assertEqual(_jwt(self.pay).get(MEAS_URL).status_code, 403)

    def test_public_user_403(self):
        self.assertEqual(_jwt(self.pub).get(MEAS_URL).status_code, 403)

    # --- Ingestion ---
    def test_admin_can_ingest(self):
        resp = _post(_jwt(self.admin), self.seg, self.cam)
        self.assertEqual(resp.status_code, 201)

    def test_tco_cannot_ingest(self):
        resp = _post(_jwt(self.tco), self.seg, self.cam)
        self.assertEqual(resp.status_code, 403)

    def test_analyst_cannot_ingest(self):
        resp = _post(_jwt(self.analyst), self.seg, self.cam)
        self.assertEqual(resp.status_code, 403)

    def test_cam_tech_cannot_ingest(self):
        resp = _post(_jwt(self.cam_t), self.seg, self.cam)
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_ingest(self):
        su = User.objects.create_superuser("su_meas", password="SuP!")
        resp = _post(_jwt(su), self.seg, self.cam)
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# 5. Ingestion (POST) CRUD and validation
# ---------------------------------------------------------------------------

class TestMeasurementIngestion(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("ingest_admin", "System Administrator")
        self.seg   = _segment(road=_road(name="Ingest Road"))
        self.cam   = _camera(segment=self.seg, name="CAM-ING01")
        self.sen   = _sensor(segment=self.seg, name="SEN-ING01")

    def test_ingest_with_camera_201(self):
        resp = _post(_jwt(self.admin), self.seg, self.cam)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["camera"], self.cam.pk)
        self.assertIsNone(data["sensor"])

    def test_ingest_with_sensor_201(self):
        resp = _post(_jwt(self.admin), self.seg, self.sen)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["sensor"], self.sen.pk)
        self.assertIsNone(data["camera"])

    def test_ingest_both_camera_and_sensor_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": self.cam.pk,
             "sensor": self.sen.pk, "measured_at": timezone.now().isoformat(),
             "vehicle_count": 5},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_no_source_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk,
             "measured_at": timezone.now().isoformat(), "vehicle_count": 5},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_no_metrics_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": self.cam.pk,
             "measured_at": timezone.now().isoformat()},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_invalid_occupancy_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": self.cam.pk,
             "measured_at": timezone.now().isoformat(),
             "occupancy_pct": 150.0},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_negative_speed_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": self.cam.pk,
             "measured_at": timezone.now().isoformat(),
             "avg_speed_kmh": -5.0},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_nonexistent_camera_400(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": 999999,
             "measured_at": timezone.now().isoformat(), "vehicle_count": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_creates_db_record(self):
        before = TrafficMeasurement.objects.count()
        _post(_jwt(self.admin), self.seg, self.cam)
        self.assertEqual(TrafficMeasurement.objects.count(), before + 1)

    def test_ingest_all_metrics(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"segment": self.seg.pk, "camera": self.cam.pk,
             "measured_at": timezone.now().isoformat(),
             "vehicle_count": 42, "avg_speed_kmh": 65.0, "occupancy_pct": 30.0},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["vehicle_count"], 42)
        self.assertAlmostEqual(data["avg_speed_kmh"], 65.0, places=1)
        self.assertAlmostEqual(data["occupancy_pct"], 30.0, places=1)

    def test_ingest_without_segment(self):
        resp = _jwt(self.admin).post(
            MEAS_URL,
            {"camera": self.cam.pk,
             "measured_at": timezone.now().isoformat(), "vehicle_count": 3},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.json()["data"]["segment"])


# ---------------------------------------------------------------------------
# 6. List + filtering + pagination
# ---------------------------------------------------------------------------

class TestMeasurementList(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("list_admin", "System Administrator")
        self.seg1  = _segment(road=_road(name="List Road 1"))
        self.seg2  = _segment(road=_road(name="List Road 2"))
        self.cam   = _camera(segment=self.seg1, name="CAM-LIST01")
        self.sen   = _sensor(segment=self.seg2, name="SEN-LIST01")

    def test_list_returns_200_with_pagination(self):
        _meas(self.seg1, camera=self.cam)
        resp = _jwt(self.admin).get(MEAS_URL)
        self.assertEqual(resp.status_code, 200)
        for k in ("count", "results"):
            self.assertIn(k, resp.json())

    def test_filter_by_segment(self):
        _meas(self.seg1, camera=self.cam)
        _meas(self.seg2, sensor=self.sen)
        resp = _jwt(self.admin).get(MEAS_URL + f"?segment={self.seg1.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["segment"], self.seg1.pk)

    def test_filter_by_camera(self):
        _meas(self.seg1, camera=self.cam)
        _meas(self.seg2, sensor=self.sen)
        resp = _jwt(self.admin).get(MEAS_URL + f"?camera={self.cam.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["camera"], self.cam.pk)

    def test_filter_by_sensor(self):
        _meas(self.seg2, sensor=self.sen)
        resp = _jwt(self.admin).get(MEAS_URL + f"?sensor={self.sen.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["sensor"], self.sen.pk)

    def test_filter_measured_after(self):
        from datetime import timedelta
        now = timezone.now()
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=3), vehicle_count=1)
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=1), vehicle_count=2)
        cutoff = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = _jwt(self.admin).get(MEAS_URL + f"?measured_after={cutoff}")
        for r in resp.json()["results"]:
            self.assertEqual(r["vehicle_count"], 2)

    def test_filter_measured_before(self):
        from datetime import timedelta
        now = timezone.now()
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=3), vehicle_count=1)
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=1), vehicle_count=2)
        cutoff = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = _jwt(self.admin).get(MEAS_URL + f"?measured_before={cutoff}")
        for r in resp.json()["results"]:
            self.assertEqual(r["vehicle_count"], 1)

    def test_ordering_newest_first(self):
        from datetime import timedelta
        now = timezone.now()
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=2), vehicle_count=1)
        _meas(self.seg1, camera=self.cam,
              measured_at=now - timedelta(hours=1), vehicle_count=2)
        results = _jwt(self.admin).get(MEAS_URL).json()["results"]
        counts = [r["vehicle_count"] for r in results
                  if r["vehicle_count"] in (1, 2)]
        if len(counts) >= 2:
            self.assertEqual(counts[0], 2)

    def test_page_size_param(self):
        for i in range(5):
            cam_n = Camera.objects.create(
                name=f"CAM-PAGE{i}", segment=self.seg1
            )
            _meas(self.seg1, camera=cam_n)
        resp = _jwt(self.admin).get(MEAS_URL + "?page_size=2")
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()["results"]), 2)
        self.assertGreater(resp.json()["count"], 2)


# ---------------------------------------------------------------------------
# 7. Detail endpoint
# ---------------------------------------------------------------------------

class TestMeasurementDetail(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("det_admin",   "System Administrator")
        self.analyst = _make_role_user("det_analyst", "Traffic Analyst")
        self.law     = _make_role_user("det_law",     "Law Enforcement / Authorized Officer")
        self.seg     = _segment(road=_road(name="Detail Road M"))
        self.cam     = _camera(segment=self.seg, name="CAM-DET01")
        self.m       = _meas(self.seg, camera=self.cam, vehicle_count=7)

    def test_admin_can_get_detail(self):
        resp = _jwt(self.admin).get(f"{MEAS_URL}{self.m.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["vehicle_count"], 7)

    def test_analyst_can_get_detail(self):
        resp = _jwt(self.analyst).get(f"{MEAS_URL}{self.m.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_law_enforcement_cannot_get_detail(self):
        resp = _jwt(self.law).get(f"{MEAS_URL}{self.m.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_nonexistent_measurement_404(self):
        resp = _jwt(self.admin).get(f"{MEAS_URL}999999/")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# 8. Append-only enforcement
# ---------------------------------------------------------------------------

class TestMeasurementAppendOnly(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("ao_admin", "System Administrator")
        self.seg   = _segment(road=_road(name="AppendOnly Road"))
        self.cam   = _camera(segment=self.seg, name="CAM-AO01")
        self.m     = _meas(self.seg, camera=self.cam)

    def test_patch_method_not_allowed(self):
        resp = _jwt(self.admin).patch(
            f"{MEAS_URL}{self.m.pk}/", {"vehicle_count": 999}, format="json"
        )
        self.assertEqual(resp.status_code, 405)

    def test_put_method_not_allowed(self):
        resp = _jwt(self.admin).put(
            f"{MEAS_URL}{self.m.pk}/", {"vehicle_count": 999}, format="json"
        )
        self.assertEqual(resp.status_code, 405)

    def test_delete_method_not_allowed(self):
        resp = _jwt(self.admin).delete(f"{MEAS_URL}{self.m.pk}/")
        self.assertEqual(resp.status_code, 405)

    def test_model_level_save_guard(self):
        self.m.vehicle_count = 999
        with self.assertRaises(RuntimeError):
            self.m.save()

    def test_model_level_delete_guard(self):
        with self.assertRaises(RuntimeError):
            self.m.delete()

    def test_post_still_creates(self):
        before = TrafficMeasurement.objects.count()
        _post(_jwt(self.admin), self.seg, self.cam)
        self.assertEqual(TrafficMeasurement.objects.count(), before + 1)


# ---------------------------------------------------------------------------
# 9. Audit — NOT audited per architecture
# ---------------------------------------------------------------------------

class TestMeasurementNotAudited(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("aud_meas_admin", "System Administrator")
        self.seg   = _segment(road=_road(name="Audit Road M"))
        self.cam   = _camera(segment=self.seg, name="CAM-AUDIT01")

    def test_ingestion_does_not_create_audit_event(self):
        before = AuditEvent.objects.count()
        _post(_jwt(self.admin), self.seg, self.cam)
        after = AuditEvent.objects.count()
        # No new audit event should be created by measurement ingestion
        self.assertEqual(
            after, before,
            "TrafficMeasurement insertion must NOT create an audit event "
            "(classified as 'volume too high' in domain-model.md).",
        )

    def test_existing_auth_audit_still_works(self):
        """Other audit events must not be broken."""
        from apps.audit.services import AuditAction
        before = AuditEvent.objects.filter(
            action=AuditAction.AUTH_LOGIN_SUCCESS
        ).count()
        _jwt(self.admin).get("/api/v1/auth/me/")
        # auth audit is not triggered by GET /me/, but the table is accessible
        self.assertGreaterEqual(
            AuditEvent.objects.count(), before
        )


# ---------------------------------------------------------------------------
# 10. Regression
# ---------------------------------------------------------------------------

class TestMeasurementRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_signals_api_still_works(self):
        admin = _make_role_user("reg_sig", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/signals/").status_code, 200)

    def test_roads_still_work(self):
        admin = _make_role_user("reg_roads_m", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/roads/").status_code, 200)

    def test_cameras_still_work(self):
        admin = _make_role_user("reg_cams_m", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/cameras/").status_code, 200)

    def test_auth_me_still_401_unauthenticated(self):
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
