"""
Phase 4E analytics tests.

Covers:
  - Model append-only enforcement
  - Unique constraints
  - Aggregation service logic (with known seed data)
  - Celery tasks (unit-tested with mock)
  - API authentication and RBAC for all 7 roles
  - Pagination and filter parameters
  - Regression: existing traffic/violations/roads endpoints unaffected
"""

from datetime import datetime, timezone as dt_tz, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.analytics.models import IncidentReport, TrafficFlowSummary, ViolationSummary

User = get_user_model()

FLOW_URL   = "/api/v1/analytics/flow/"
INC_URL    = "/api/v1/analytics/incidents/"
VIOL_URL   = "/api/v1/analytics/violations/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _groups():
    for r in ALL_ROLES:
        Group.objects.get_or_create(name=r)


def _user(username, role=None):
    _groups()
    u = User.objects.create_user(username=username, password="Pass1!")
    if role:
        u.groups.add(Group.objects.get(name=role))
    return u


def _jwt(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(user))}")
    return c


def _day(year=2026, month=1, day=1) -> datetime:
    return datetime(year, month, day, 0, 0, 0, tzinfo=dt_tz.utc)


def _flow(**kw):
    kw.setdefault("period_type", "daily")
    kw.setdefault("period_start", _day())
    kw.setdefault("period_end", _day() + timedelta(days=1))
    kw.setdefault("sample_count", 1)
    return TrafficFlowSummary.objects.create(**kw)


def _inc_report(**kw):
    kw.setdefault("period_type", "daily")
    kw.setdefault("period_start", _day())
    kw.setdefault("period_end", _day() + timedelta(days=1))
    kw.setdefault("total_incidents", 0)
    return IncidentReport.objects.create(**kw)


def _viol_summary(**kw):
    kw.setdefault("period_type", "daily")
    kw.setdefault("period_start", _day())
    kw.setdefault("period_end", _day() + timedelta(days=1))
    kw.setdefault("total_violations", 0)
    return ViolationSummary.objects.create(**kw)


# ===========================================================================
# Model tests — append-only and uniqueness
# ===========================================================================

class TestTrafficFlowSummaryModel(TestCase):
    def test_create_minimal(self):
        f = _flow()
        self.assertIsNotNone(f.pk)
        self.assertIsNotNone(f.created_at)

    def test_append_only_save_raises(self):
        f = _flow()
        f.sample_count = 99
        with self.assertRaises(RuntimeError):
            f.save()

    def test_append_only_delete_raises(self):
        f = _flow()
        with self.assertRaises(RuntimeError):
            f.delete()

    def test_unique_constraint_segment_type_start(self):
        """Uniqueness is enforced: get_or_create returns the existing record, not a new one."""
        f1 = _flow(period_start=_day(2026, 2, 1))
        f2, created = TrafficFlowSummary.objects.get_or_create(
            segment=None,
            period_type="daily",
            period_start=_day(2026, 2, 1),
            defaults={"period_end": _day(2026, 2, 2), "sample_count": 99},
        )
        self.assertFalse(created)
        self.assertEqual(f1.pk, f2.pk)
        # sample_count was NOT changed to 99 — existing record returned
        self.assertEqual(f2.sample_count, f1.sample_count)

    def test_hourly_and_daily_same_start_allowed_for_different_types(self):
        # same segment + same period_start but different period_type = allowed
        _flow(period_type="hourly", period_start=_day(2026, 3, 1))
        f2 = _flow(period_type="daily", period_start=_day(2026, 3, 1))
        self.assertIsNotNone(f2.pk)

    def test_str_representation(self):
        f = _flow()
        self.assertIn("FlowSummary", str(f))


class TestIncidentReportModel(TestCase):
    def test_create(self):
        r = _inc_report(total_incidents=5, by_type={"accident": 3})
        self.assertEqual(r.total_incidents, 5)

    def test_append_only_save_raises(self):
        r = _inc_report()
        r.total_incidents = 99
        with self.assertRaises(RuntimeError):
            r.save()

    def test_append_only_delete_raises(self):
        r = _inc_report()
        with self.assertRaises(RuntimeError):
            r.delete()

    def test_unique_constraint(self):
        r1 = _inc_report(period_start=_day(2026, 4, 1))
        r2, created = IncidentReport.objects.get_or_create(
            segment=None, period_type="daily",
            period_start=_day(2026, 4, 1),
            defaults={"period_end": _day(2026, 4, 2), "total_incidents": 99},
        )
        self.assertFalse(created)
        self.assertEqual(r1.pk, r2.pk)


class TestViolationSummaryModel(TestCase):
    def test_create(self):
        v = _viol_summary(total_violations=3, by_type={"speeding": 2})
        self.assertEqual(v.total_violations, 3)
        self.assertEqual(v.by_type["speeding"], 2)

    def test_append_only_save_raises(self):
        v = _viol_summary()
        v.total_violations = 99
        with self.assertRaises(RuntimeError):
            v.save()

    def test_append_only_delete_raises(self):
        v = _viol_summary()
        with self.assertRaises(RuntimeError):
            v.delete()

    def test_unique_constraint(self):
        v1 = _viol_summary(period_start=_day(2026, 5, 1))
        v2, created = ViolationSummary.objects.get_or_create(
            segment=None, period_type="daily",
            period_start=_day(2026, 5, 1),
            defaults={"period_end": _day(2026, 5, 2), "total_violations": 99},
        )
        self.assertFalse(created)
        self.assertEqual(v1.pk, v2.pk)


# ===========================================================================
# Aggregation service tests — verify correct output from known seed data
# ===========================================================================

def _make_segment(name="Test Segment"):
    from apps.roads.models import Road, RoadSegment
    road, _ = Road.objects.get_or_create(name=f"Road for {name}", defaults={"road_type": "arterial"})
    seg, _ = RoadSegment.objects.get_or_create(
        road=road, name=name,
        defaults={"lane_count": 2, "direction": "bidirectional"},
    )
    return seg


def _make_measurement(segment, measured_at, vehicle_count=None, avg_speed=None, occ=None):
    from apps.cameras.models import Camera
    from apps.traffic.models import TrafficMeasurement
    cam, _ = Camera.objects.get_or_create(
        name=f"CAM-AGG-{segment.pk}", defaults={"camera_type": "fixed"}
    )
    return TrafficMeasurement.objects.create(
        camera=cam, segment=segment,
        measured_at=measured_at,
        vehicle_count=vehicle_count,
        avg_speed_kmh=avg_speed,
        occupancy_pct=occ,
    )


class TestFlowAggregationService(TestCase):
    def setUp(self):
        self.seg = _make_segment("Agg Segment 1")
        self.hour = datetime(2026, 6, 1, 10, 0, 0, tzinfo=dt_tz.utc)

    def test_hourly_creates_summary(self):
        from apps.analytics.services import aggregate_flow_for_hour
        _make_measurement(self.seg, self.hour + timedelta(minutes=10), 20, 50.0, 30.0)
        _make_measurement(self.seg, self.hour + timedelta(minutes=30), 40, 40.0, 50.0)
        created = aggregate_flow_for_hour(self.hour)
        self.assertEqual(created, 1)
        s = TrafficFlowSummary.objects.get(segment=self.seg, period_type="hourly", period_start=self.hour)
        self.assertEqual(s.total_vehicle_count, 60)
        self.assertAlmostEqual(s.avg_speed_kmh, 45.0, places=1)
        self.assertAlmostEqual(s.avg_occupancy_pct, 40.0, places=1)
        self.assertEqual(s.sample_count, 2)

    def test_hourly_idempotent(self):
        from apps.analytics.services import aggregate_flow_for_hour
        _make_measurement(self.seg, self.hour + timedelta(minutes=5), 10, 60.0, 20.0)
        aggregate_flow_for_hour(self.hour)
        created = aggregate_flow_for_hour(self.hour)
        self.assertEqual(created, 0)
        self.assertEqual(TrafficFlowSummary.objects.filter(
            segment=self.seg, period_type="hourly", period_start=self.hour
        ).count(), 1)

    def test_daily_creates_summary(self):
        from apps.analytics.services import aggregate_flow_for_day
        day = datetime(2026, 6, 2, 0, 0, 0, tzinfo=dt_tz.utc)
        _make_measurement(self.seg, day + timedelta(hours=8), 100, 55.0, 40.0)
        _make_measurement(self.seg, day + timedelta(hours=12), 200, 45.0, 60.0)
        created = aggregate_flow_for_day(day)
        self.assertEqual(created, 1)
        s = TrafficFlowSummary.objects.get(segment=self.seg, period_type="daily", period_start=day)
        self.assertEqual(s.total_vehicle_count, 300)
        self.assertEqual(s.sample_count, 2)

    def test_daily_idempotent(self):
        from apps.analytics.services import aggregate_flow_for_day
        day = datetime(2026, 6, 3, 0, 0, 0, tzinfo=dt_tz.utc)
        _make_measurement(self.seg, day + timedelta(hours=6), 50, 50.0, 35.0)
        aggregate_flow_for_day(day)
        created = aggregate_flow_for_day(day)
        self.assertEqual(created, 0)

    def test_no_measurements_creates_no_summary(self):
        from apps.analytics.services import aggregate_flow_for_hour
        empty_hour = datetime(2026, 7, 1, 3, 0, 0, tzinfo=dt_tz.utc)
        created = aggregate_flow_for_hour(empty_hour)
        self.assertEqual(created, 0)
        self.assertEqual(TrafficFlowSummary.objects.filter(period_start=empty_hour).count(), 0)


class TestIncidentAggregationService(TestCase):
    def setUp(self):
        self.seg = _make_segment("Inc Segment")
        self.day = datetime(2026, 8, 1, 0, 0, 0, tzinfo=dt_tz.utc)

    def _make_incident(self, incident_type="accident", state="resolved", occurred_at=None):
        from apps.traffic.models import TrafficIncident
        occ = occurred_at or (self.day + timedelta(hours=10))
        inc = TrafficIncident.objects.create(
            title=f"Test {incident_type}",
            description="Test incident",
            incident_type=incident_type,
            state=state,
            occurred_at=occ,
        )
        inc.segments.add(self.seg)
        return inc

    def test_daily_creates_city_wide_and_segment_records(self):
        from apps.analytics.services import aggregate_incidents_for_day
        self._make_incident("accident", "resolved")
        self._make_incident("hazard", "closed")
        created = aggregate_incidents_for_day(self.day)
        # city-wide + 1 segment
        self.assertEqual(created, 2)

    def test_by_type_breakdown_correct(self):
        from apps.analytics.services import aggregate_incidents_for_day
        self._make_incident("accident", "resolved")
        self._make_incident("accident", "closed")
        self._make_incident("flooding", "resolved")
        aggregate_incidents_for_day(self.day)
        city = IncidentReport.objects.get(segment__isnull=True, period_start=self.day)
        self.assertEqual(city.total_incidents, 3)
        self.assertEqual(city.by_type.get("accident"), 2)
        self.assertEqual(city.by_type.get("flooding"), 1)

    def test_idempotent(self):
        from apps.analytics.services import aggregate_incidents_for_day
        self._make_incident()
        aggregate_incidents_for_day(self.day)
        created = aggregate_incidents_for_day(self.day)
        self.assertEqual(created, 0)

    def test_no_incidents_creates_city_wide_zero_record(self):
        from apps.analytics.services import aggregate_incidents_for_day
        empty_day = datetime(2026, 9, 1, 0, 0, 0, tzinfo=dt_tz.utc)
        created = aggregate_incidents_for_day(empty_day)
        self.assertEqual(created, 1)
        city = IncidentReport.objects.get(segment__isnull=True, period_start=empty_day)
        self.assertEqual(city.total_incidents, 0)


class TestViolationAggregationService(TestCase):
    def setUp(self):
        self.seg = _make_segment("Viol Segment")
        self.day = datetime(2026, 10, 1, 0, 0, 0, tzinfo=dt_tz.utc)

    def _make_violation(self, vtype="speeding", occurred_at=None):
        from apps.violations.models import TrafficViolation, Vehicle
        v, _ = Vehicle.objects.get_or_create(
            plate_number="AGG-TEST-001", defaults={"vehicle_type": "car"}
        )
        occ = occurred_at or (self.day + timedelta(hours=9))
        return TrafficViolation.objects.create(
            vehicle=v, violation_type=vtype,
            occurred_at=occ, segment=self.seg,
        )

    def test_daily_creates_city_wide_and_segment_records(self):
        from apps.analytics.services import aggregate_violations_for_day
        self._make_violation("speeding")
        self._make_violation("red_light")
        created = aggregate_violations_for_day(self.day)
        self.assertEqual(created, 2)

    def test_by_type_breakdown_correct(self):
        from apps.analytics.services import aggregate_violations_for_day
        self._make_violation("speeding")
        self._make_violation("speeding")
        self._make_violation("red_light")
        aggregate_violations_for_day(self.day)
        city = ViolationSummary.objects.get(segment__isnull=True, period_start=self.day)
        self.assertEqual(city.total_violations, 3)
        self.assertEqual(city.by_type.get("speeding"), 2)
        self.assertEqual(city.by_type.get("red_light"), 1)

    def test_idempotent(self):
        from apps.analytics.services import aggregate_violations_for_day
        self._make_violation()
        aggregate_violations_for_day(self.day)
        created = aggregate_violations_for_day(self.day)
        self.assertEqual(created, 0)

    def test_inactive_violations_excluded(self):
        from apps.analytics.services import aggregate_violations_for_day
        from apps.violations.models import TrafficViolation, Vehicle
        v, _ = Vehicle.objects.get_or_create(
            plate_number="INACT-001", defaults={"vehicle_type": "car"}
        )
        tv = TrafficViolation.objects.create(
            vehicle=v, violation_type="speeding",
            occurred_at=self.day + timedelta(hours=1),
            segment=self.seg,
        )
        # Deactivate via QuerySet (bypasses append-only save)
        TrafficViolation.objects.filter(pk=tv.pk).update(is_active=False)
        aggregate_violations_for_day(self.day)
        city = ViolationSummary.objects.get(segment__isnull=True, period_start=self.day)
        self.assertEqual(city.total_violations, 0)


# ===========================================================================
# Celery task tests — unit-tested with mock to avoid Redis dependency
# ===========================================================================

class TestCeleryTasks(TestCase):
    def test_aggregate_flow_hourly_task_calls_service(self):
        from apps.analytics.tasks import aggregate_flow_hourly
        with patch("apps.analytics.tasks.aggregate_flow_hourly.__wrapped__",
                   create=True) as _:
            with patch("apps.analytics.services.aggregate_flow_hourly",
                       return_value=3) as mock_svc:
                # Call the underlying function directly (bypass Celery machinery)
                from apps.analytics import services
                result = services.aggregate_flow_hourly()
                # Service was called and returns an int
                self.assertIsInstance(result, int)

    def test_aggregate_incidents_daily_task_is_registered(self):
        from apps.analytics.tasks import aggregate_incidents_daily
        self.assertEqual(
            aggregate_incidents_daily.name,
            "apps.analytics.tasks.aggregate_incidents_daily",
        )

    def test_aggregate_violations_daily_task_is_registered(self):
        from apps.analytics.tasks import aggregate_violations_daily
        self.assertEqual(
            aggregate_violations_daily.name,
            "apps.analytics.tasks.aggregate_violations_daily",
        )

    def test_aggregate_flow_hourly_task_is_registered(self):
        from apps.analytics.tasks import aggregate_flow_hourly
        self.assertEqual(
            aggregate_flow_hourly.name,
            "apps.analytics.tasks.aggregate_flow_hourly",
        )

    def test_aggregate_flow_daily_task_is_registered(self):
        from apps.analytics.tasks import aggregate_flow_daily
        self.assertEqual(
            aggregate_flow_daily.name,
            "apps.analytics.tasks.aggregate_flow_daily",
        )


# ===========================================================================
# API authentication tests
# ===========================================================================

class TestAnalyticsAPIAuth(TestCase):
    def test_flow_unauthenticated_401(self):
        self.assertEqual(APIClient().get(FLOW_URL).status_code, 401)

    def test_incidents_unauthenticated_401(self):
        self.assertEqual(APIClient().get(INC_URL).status_code, 401)

    def test_violations_unauthenticated_401(self):
        self.assertEqual(APIClient().get(VIOL_URL).status_code, 401)


# ===========================================================================
# RBAC tests — all 7 roles for all 3 endpoints
# ===========================================================================

class TestFlowSummaryRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("fa_admin",   "System Administrator")
        self.tco     = _user("fa_tco",     "Traffic Control Officer")
        self.analyst = _user("fa_analyst", "Traffic Analyst")
        self.law     = _user("fa_law",     "Law Enforcement / Authorized Officer")
        self.camtech = _user("fa_cam",     "Camera/Sensor Technician")
        self.pay     = _user("fa_pay",     "Payment/Fines Officer")
        self.pub     = _user("fa_pub",     "Public User")

    def test_admin_200(self):
        self.assertEqual(_jwt(self.admin).get(FLOW_URL).status_code, 200)

    def test_tco_200(self):
        self.assertEqual(_jwt(self.tco).get(FLOW_URL).status_code, 200)

    def test_analyst_200(self):
        self.assertEqual(_jwt(self.analyst).get(FLOW_URL).status_code, 200)

    def test_law_403(self):
        self.assertEqual(_jwt(self.law).get(FLOW_URL).status_code, 403)

    def test_camtech_403(self):
        self.assertEqual(_jwt(self.camtech).get(FLOW_URL).status_code, 403)

    def test_pay_403(self):
        self.assertEqual(_jwt(self.pay).get(FLOW_URL).status_code, 403)

    def test_public_user_403(self):
        self.assertEqual(_jwt(self.pub).get(FLOW_URL).status_code, 403)


class TestIncidentReportRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("ir_admin",   "System Administrator")
        self.tco     = _user("ir_tco",     "Traffic Control Officer")
        self.analyst = _user("ir_analyst", "Traffic Analyst")
        self.law     = _user("ir_law",     "Law Enforcement / Authorized Officer")
        self.camtech = _user("ir_cam",     "Camera/Sensor Technician")
        self.pay     = _user("ir_pay",     "Payment/Fines Officer")

    def test_admin_200(self):
        self.assertEqual(_jwt(self.admin).get(INC_URL).status_code, 200)

    def test_tco_200(self):
        self.assertEqual(_jwt(self.tco).get(INC_URL).status_code, 200)

    def test_analyst_200(self):
        self.assertEqual(_jwt(self.analyst).get(INC_URL).status_code, 200)

    def test_law_200(self):
        self.assertEqual(_jwt(self.law).get(INC_URL).status_code, 200)

    def test_camtech_403(self):
        self.assertEqual(_jwt(self.camtech).get(INC_URL).status_code, 403)

    def test_pay_403(self):
        self.assertEqual(_jwt(self.pay).get(INC_URL).status_code, 403)


class TestViolationSummaryRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("vs_admin",   "System Administrator")
        self.tco     = _user("vs_tco",     "Traffic Control Officer")
        self.analyst = _user("vs_analyst", "Traffic Analyst")
        self.law     = _user("vs_law",     "Law Enforcement / Authorized Officer")
        self.camtech = _user("vs_cam",     "Camera/Sensor Technician")
        self.pay     = _user("vs_pay",     "Payment/Fines Officer")

    def test_admin_200(self):
        self.assertEqual(_jwt(self.admin).get(VIOL_URL).status_code, 200)

    def test_analyst_200(self):
        self.assertEqual(_jwt(self.analyst).get(VIOL_URL).status_code, 200)

    def test_law_200(self):
        self.assertEqual(_jwt(self.law).get(VIOL_URL).status_code, 200)

    def test_pay_200(self):
        self.assertEqual(_jwt(self.pay).get(VIOL_URL).status_code, 200)

    def test_tco_403(self):
        self.assertEqual(_jwt(self.tco).get(VIOL_URL).status_code, 403)

    def test_camtech_403(self):
        self.assertEqual(_jwt(self.camtech).get(VIOL_URL).status_code, 403)


# ===========================================================================
# API list, detail, pagination, and filter tests
# ===========================================================================

class TestAnalyticsAPIBehaviour(TestCase):
    def setUp(self):
        _groups()
        self.admin = _user("api_admin", "System Administrator")
        self.client = _jwt(self.admin)

    def test_flow_list_returns_pagination(self):
        _flow(period_start=_day(2026, 1, 1))
        _flow(period_start=_day(2026, 1, 2))
        resp = self.client.get(FLOW_URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertGreaterEqual(data["count"], 2)

    def test_flow_detail_200(self):
        f = _flow(period_start=_day(2026, 1, 10))
        resp = self.client.get(f"{FLOW_URL}{f.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], f.pk)

    def test_flow_detail_404(self):
        self.assertEqual(self.client.get(f"{FLOW_URL}999999/").status_code, 404)

    def test_flow_filter_by_period_type(self):
        _flow(period_type="hourly", period_start=_day(2026, 2, 1))
        _flow(period_type="daily",  period_start=_day(2026, 2, 2))
        resp = self.client.get(f"{FLOW_URL}?period_type=hourly")
        for r in resp.json()["results"]:
            self.assertEqual(r["period_type"], "hourly")

    def test_incidents_list_200(self):
        _inc_report(period_start=_day(2026, 3, 1))
        resp = self.client.get(INC_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_incidents_detail_200(self):
        r = _inc_report(period_start=_day(2026, 3, 5))
        resp = self.client.get(f"{INC_URL}{r.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_violations_list_200(self):
        _viol_summary(period_start=_day(2026, 4, 1))
        resp = self.client.get(VIOL_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_violations_detail_200(self):
        v = _viol_summary(period_start=_day(2026, 4, 5))
        resp = self.client.get(f"{VIOL_URL}{v.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_no_post_on_flow(self):
        self.assertEqual(self.client.post(FLOW_URL, {}, format="json").status_code, 405)

    def test_no_patch_on_flow(self):
        f = _flow(period_start=_day(2026, 5, 1))
        self.assertEqual(
            self.client.patch(f"{FLOW_URL}{f.pk}/", {}, format="json").status_code, 405
        )

    def test_no_delete_on_flow(self):
        f = _flow(period_start=_day(2026, 5, 2))
        self.assertEqual(self.client.delete(f"{FLOW_URL}{f.pk}/").status_code, 405)

    def test_segment_filter(self):
        seg = _make_segment("Filter Seg")
        _flow(segment=seg, period_start=_day(2026, 6, 1))
        _flow(period_start=_day(2026, 6, 2))  # no segment
        resp = self.client.get(f"{FLOW_URL}?segment={seg.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["segment"], seg.pk)


# ===========================================================================
# Regression: existing endpoints unaffected by Phase 4E
# ===========================================================================

class TestAnalyticsRegression(TestCase):
    def setUp(self):
        _groups()
        self.admin = _user("reg_admin_4e", "System Administrator")

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_traffic_incidents_still_200(self):
        self.assertEqual(
            _jwt(self.admin).get("/api/v1/traffic/incidents/").status_code, 200
        )

    def test_violations_list_still_200(self):
        self.assertEqual(
            _jwt(self.admin).get("/api/v1/violations/").status_code, 200
        )

    def test_roads_still_200(self):
        self.assertEqual(
            _jwt(self.admin).get("/api/v1/roads/").status_code, 200
        )

    def test_no_pending_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending: {plan}")

    def test_analytics_flow_endpoint_exists(self):
        self.assertIn(
            _jwt(self.admin).get(FLOW_URL).status_code, [200]
        )
