"""
API tests for the road infrastructure endpoints.

Covers routing, authentication, RBAC, CRUD, validation, pagination, audit.
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
from apps.roads.models import Intersection, Lane, Road, RoadSegment

User = get_user_model()

ROADS_URL         = "/api/v1/roads/"
INTERSECTIONS_URL = "/api/v1/roads/intersections/"
SEGMENTS_URL      = "/api/v1/roads/segments/"
LANES_URL         = "/api/v1/roads/lanes/"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
    kw.setdefault("name", "Test Road")
    return Road.objects.create(**kw)


def _intersection(**kw):
    kw.setdefault("name", "Test Intersection")
    return Intersection.objects.create(**kw)


def _segment(road=None, **kw):
    road = road or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _lane(segment=None, **kw):
    segment = segment or _segment()
    kw.setdefault("lane_number", 1)
    return Lane.objects.create(segment=segment, **kw)


# ---------------------------------------------------------------------------
# 1. URL routing
# ---------------------------------------------------------------------------

class TestRoadUrlRouting(TestCase):
    def test_road_list_resolves(self):
        m = resolve(ROADS_URL)
        self.assertEqual(m.url_name, "road-list")
        self.assertEqual(m.namespace, "roads")

    def test_road_list_reverses(self):
        self.assertEqual(reverse("roads:road-list"), ROADS_URL)

    def test_road_detail_resolves(self):
        m = resolve("/api/v1/roads/1/")
        self.assertEqual(m.url_name, "road-detail")

    def test_intersection_list_resolves(self):
        m = resolve(INTERSECTIONS_URL)
        self.assertEqual(m.url_name, "intersection-list")

    def test_segment_list_resolves(self):
        m = resolve(SEGMENTS_URL)
        self.assertEqual(m.url_name, "segment-list")

    def test_lane_list_resolves(self):
        m = resolve(LANES_URL)
        self.assertEqual(m.url_name, "lane-list")


# ---------------------------------------------------------------------------
# 2. Authentication — unauthenticated requests return 401
# ---------------------------------------------------------------------------

class TestRoadAuthentication(TestCase):
    def setUp(self):
        self.road = _road()
        self.intersection = _intersection()
        self.segment = _segment(self.road)
        self.lane = _lane(self.segment)

    def _check_401(self, url):
        self.assertEqual(APIClient().get(url).status_code, 401)
        self.assertEqual(APIClient().post(url).status_code, 401)

    def test_roads_unauthenticated_401(self):
        self._check_401(ROADS_URL)

    def test_intersections_unauthenticated_401(self):
        self._check_401(INTERSECTIONS_URL)

    def test_segments_unauthenticated_401(self):
        self._check_401(SEGMENTS_URL)

    def test_lanes_unauthenticated_401(self):
        self._check_401(LANES_URL)

    def test_road_detail_unauthenticated_401(self):
        self.assertEqual(APIClient().get(f"{ROADS_URL}{self.road.pk}/").status_code, 401)

    def test_road_status_unauthenticated_401(self):
        self.assertEqual(
            APIClient().patch(f"{ROADS_URL}{self.road.pk}/status/").status_code, 401
        )


# ---------------------------------------------------------------------------
# 3. RBAC — role access matrix
# ---------------------------------------------------------------------------

class TestRoadRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("rbac_admin",   "System Administrator")
        self.tco     = _make_role_user("rbac_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("rbac_analyst", "Traffic Analyst")
        self.law     = _make_role_user("rbac_law",     "Law Enforcement / Authorized Officer")
        self.cam     = _make_role_user("rbac_cam",     "Camera/Sensor Technician")
        self.pay     = _make_role_user("rbac_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("rbac_pub",     "Public User")
        self.road = _road(name="RBAC Test Road")

    def test_admin_can_list_roads(self):
        self.assertEqual(_jwt(self.admin).get(ROADS_URL).status_code, 200)

    def test_tco_can_read_roads(self):
        self.assertEqual(_jwt(self.tco).get(ROADS_URL).status_code, 200)

    def test_analyst_can_read_roads(self):
        self.assertEqual(_jwt(self.analyst).get(ROADS_URL).status_code, 200)

    def test_law_enforcement_cannot_read_roads(self):
        self.assertEqual(_jwt(self.law).get(ROADS_URL).status_code, 403)

    def test_camera_technician_cannot_read_roads(self):
        self.assertEqual(_jwt(self.cam).get(ROADS_URL).status_code, 403)

    def test_payment_officer_cannot_read_roads(self):
        self.assertEqual(_jwt(self.pay).get(ROADS_URL).status_code, 403)

    def test_public_user_cannot_read_roads(self):
        self.assertEqual(_jwt(self.pub).get(ROADS_URL).status_code, 403)

    def test_tco_cannot_create_road(self):
        resp = _jwt(self.tco).post(ROADS_URL, {"name": "TCO Road"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_analyst_cannot_create_road(self):
        resp = _jwt(self.analyst).post(ROADS_URL, {"name": "Analyst Road"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_create_road(self):
        resp = _jwt(self.admin).post(
            ROADS_URL, {"name": "Admin Road", "road_type": "primary"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_superuser_can_create_road(self):
        su = User.objects.create_superuser("su_roads", password="SuPass!")
        resp = _jwt(su).post(
            ROADS_URL, {"name": "SU Road", "road_type": "primary"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_admin_can_update_road(self):
        resp = _jwt(self.admin).patch(
            f"{ROADS_URL}{self.road.pk}/", {"name": "Updated Name"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_cannot_update_road(self):
        resp = _jwt(self.tco).patch(
            f"{ROADS_URL}{self.road.pk}/", {"name": "New Name"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# 4. Road CRUD
# ---------------------------------------------------------------------------

class TestRoadCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("crud_admin", "System Administrator")

    def test_list_roads_returns_200_and_pagination(self):
        _road(name="Road A"); _road(name="Road B")
        resp = _jwt(self.admin).get(ROADS_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("count", "results", "next", "previous"):
            self.assertIn(key, body)

    def test_create_road_returns_201(self):
        resp = _jwt(self.admin).post(
            ROADS_URL, {"name": "New Road", "road_type": "secondary"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["name"], "New Road")

    def test_create_road_duplicate_name_returns_400(self):
        _road(name="Dup Road")
        resp = _jwt(self.admin).post(ROADS_URL, {"name": "Dup Road"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_road_missing_name_returns_400(self):
        resp = _jwt(self.admin).post(ROADS_URL, {"road_type": "primary"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_get_road_detail(self):
        road = _road(name="Detail Road")
        resp = _jwt(self.admin).get(f"{ROADS_URL}{road.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "Detail Road")

    def test_get_nonexistent_road_returns_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{ROADS_URL}999999/").status_code, 404)

    def test_patch_road_updates_name(self):
        road = _road(name="Old Name")
        resp = _jwt(self.admin).patch(
            f"{ROADS_URL}{road.pk}/", {"name": "New Name"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        road.refresh_from_db()
        self.assertEqual(road.name, "New Name")

    def test_deactivate_road(self):
        road = _road(name="Active Road")
        resp = _jwt(self.admin).patch(
            f"{ROADS_URL}{road.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        road.refresh_from_db()
        self.assertFalse(road.is_active)

    def test_reactivate_road(self):
        road = _road(name="Inactive Road", is_active=False)
        resp = _jwt(self.admin).patch(
            f"{ROADS_URL}{road.pk}/status/", {"is_active": True}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        road.refresh_from_db()
        self.assertTrue(road.is_active)

    def test_status_invalid_value_returns_400(self):
        road = _road(name="Status Road")
        resp = _jwt(self.admin).patch(
            f"{ROADS_URL}{road.pk}/status/", {"is_active": "yes"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_active_only_filter(self):
        _road(name="Active F"); _road(name="Inactive F", is_active=False)
        resp = _jwt(self.admin).get(ROADS_URL + "?active_only=true")
        results = resp.json()["results"]
        self.assertTrue(all(r["is_active"] for r in results))


# ---------------------------------------------------------------------------
# 5. Intersection CRUD
# ---------------------------------------------------------------------------

class TestIntersectionCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("int_admin", "System Administrator")

    def test_create_intersection(self):
        resp = _jwt(self.admin).post(
            INTERSECTIONS_URL,
            {"name": "Main/Oak", "latitude": 10.0, "longitude": 20.0},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["name"], "Main/Oak")

    def test_create_intersection_without_coords(self):
        resp = _jwt(self.admin).post(
            INTERSECTIONS_URL, {"name": "No Coords"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_intersection_partial_coords_returns_400(self):
        resp = _jwt(self.admin).post(
            INTERSECTIONS_URL, {"name": "Partial", "latitude": 10.0}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_intersections_returns_200(self):
        _intersection(name="I1"); _intersection(name="I2")
        resp = _jwt(self.admin).get(INTERSECTIONS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 2)

    def test_get_intersection_detail(self):
        obj = _intersection(name="Detail Jct")
        resp = _jwt(self.admin).get(f"{INTERSECTIONS_URL}{obj.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "Detail Jct")

    def test_get_nonexistent_intersection_returns_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{INTERSECTIONS_URL}999999/").status_code, 404)

    def test_patch_intersection(self):
        obj = _intersection(name="Old Jct")
        resp = _jwt(self.admin).patch(
            f"{INTERSECTIONS_URL}{obj.pk}/", {"name": "New Jct"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.name, "New Jct")

    def test_deactivate_intersection(self):
        obj = _intersection(name="Active Jct")
        resp = _jwt(self.admin).patch(
            f"{INTERSECTIONS_URL}{obj.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        obj.refresh_from_db()
        self.assertFalse(obj.is_active)


# ---------------------------------------------------------------------------
# 6. RoadSegment CRUD
# ---------------------------------------------------------------------------

class TestSegmentCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("seg_admin", "System Administrator")
        self.road = _road(name="Segment Test Road")

    def test_create_segment(self):
        resp = _jwt(self.admin).post(
            SEGMENTS_URL,
            {"road": self.road.pk, "speed_limit_kmh": 60, "lane_count": 3},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["road"], self.road.pk)
        self.assertEqual(data["speed_limit_kmh"], 60)

    def test_create_segment_invalid_speed_returns_400(self):
        resp = _jwt(self.admin).post(
            SEGMENTS_URL,
            {"road": self.road.pk, "speed_limit_kmh": 0, "lane_count": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_segment_same_start_end_intersection_returns_400(self):
        i = _intersection(name="Same Jct")
        resp = _jwt(self.admin).post(
            SEGMENTS_URL,
            {"road": self.road.pk, "lane_count": 1,
             "start_intersection": i.pk, "end_intersection": i.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_segments(self):
        _segment(self.road); _segment(self.road)
        resp = _jwt(self.admin).get(SEGMENTS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 2)

    def test_filter_segments_by_road(self):
        road2 = _road(name="Other Road")
        _segment(self.road); _segment(road2)
        resp = _jwt(self.admin).get(SEGMENTS_URL + f"?road={self.road.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["road"], self.road.pk)

    def test_get_segment_detail(self):
        seg = _segment(self.road, speed_limit_kmh=80)
        resp = _jwt(self.admin).get(f"{SEGMENTS_URL}{seg.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["speed_limit_kmh"], 80)

    def test_get_nonexistent_segment_returns_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{SEGMENTS_URL}999999/").status_code, 404)

    def test_patch_segment_speed_limit(self):
        seg = _segment(self.road, speed_limit_kmh=60)
        resp = _jwt(self.admin).patch(
            f"{SEGMENTS_URL}{seg.pk}/", {"speed_limit_kmh": 80}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        seg.refresh_from_db()
        self.assertEqual(seg.speed_limit_kmh, 80)

    def test_deactivate_segment(self):
        seg = _segment(self.road)
        resp = _jwt(self.admin).patch(
            f"{SEGMENTS_URL}{seg.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        seg.refresh_from_db()
        self.assertFalse(seg.is_active)

    def test_response_includes_road_name(self):
        seg = _segment(self.road)
        resp = _jwt(self.admin).get(f"{SEGMENTS_URL}{seg.pk}/")
        self.assertEqual(resp.json()["data"]["road_name"], self.road.name)


# ---------------------------------------------------------------------------
# 7. Lane CRUD
# ---------------------------------------------------------------------------

class TestLaneCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("lane_admin", "System Administrator")
        self.segment = _segment()

    def test_create_lane(self):
        resp = _jwt(self.admin).post(
            LANES_URL,
            {"segment": self.segment.pk, "lane_number": 1, "lane_type": "travel"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["lane_number"], 1)

    def test_create_duplicate_lane_number_returns_400(self):
        _lane(self.segment, lane_number=1)
        resp = _jwt(self.admin).post(
            LANES_URL,
            {"segment": self.segment.pk, "lane_number": 1, "lane_type": "travel"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_lanes_with_segment_filter(self):
        _lane(self.segment, lane_number=1); _lane(self.segment, lane_number=2)
        resp = _jwt(self.admin).get(LANES_URL + f"?segment={self.segment.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 2)

    def test_get_lane_detail(self):
        lane = _lane(self.segment, lane_number=1, lane_type="bus")
        resp = _jwt(self.admin).get(f"{LANES_URL}{lane.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["lane_type"], "bus")

    def test_get_nonexistent_lane_returns_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{LANES_URL}999999/").status_code, 404)

    def test_patch_lane_type(self):
        lane = _lane(self.segment, lane_number=1, lane_type="travel")
        resp = _jwt(self.admin).patch(
            f"{LANES_URL}{lane.pk}/", {"lane_type": "bus"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        lane.refresh_from_db()
        self.assertEqual(lane.lane_type, "bus")

    def test_deactivate_lane(self):
        lane = _lane(self.segment, lane_number=1)
        resp = _jwt(self.admin).patch(
            f"{LANES_URL}{lane.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        lane.refresh_from_db()
        self.assertFalse(lane.is_active)


# ---------------------------------------------------------------------------
# 8. Audit event tests
# ---------------------------------------------------------------------------

class TestRoadAuditEvents(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("audit_road_admin", "System Administrator")

    def test_road_creation_creates_audit_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.ROAD_CREATED).count()
        _jwt(self.admin).post(ROADS_URL, {"name": "Audited Road"}, format="json")
        after  = AuditEvent.objects.filter(action=AuditAction.ROAD_CREATED).count()
        self.assertEqual(after, before + 1)

    def test_road_creation_audit_records_actor(self):
        _jwt(self.admin).post(ROADS_URL, {"name": "Actor Road"}, format="json")
        ev = AuditEvent.objects.filter(action=AuditAction.ROAD_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, "audit_road_admin")

    def test_road_update_creates_audit_event(self):
        road = _road(name="Upd Road")
        before = AuditEvent.objects.filter(action=AuditAction.ROAD_UPDATED).count()
        _jwt(self.admin).patch(f"{ROADS_URL}{road.pk}/", {"name": "Upd Road 2"}, format="json")
        after  = AuditEvent.objects.filter(action=AuditAction.ROAD_UPDATED).count()
        self.assertEqual(after, before + 1)

    def test_road_deactivation_creates_audit_event(self):
        road = _road(name="Deact Road")
        before = AuditEvent.objects.filter(action=AuditAction.ROAD_DEACTIVATED).count()
        _jwt(self.admin).patch(f"{ROADS_URL}{road.pk}/status/", {"is_active": False}, format="json")
        after  = AuditEvent.objects.filter(action=AuditAction.ROAD_DEACTIVATED).count()
        self.assertEqual(after, before + 1)

    def test_segment_speed_limit_change_creates_specific_audit_event(self):
        road = _road(name="Speed Audit Road")
        seg  = _segment(road, speed_limit_kmh=60)
        before = AuditEvent.objects.filter(
            action=AuditAction.SEGMENT_SPEED_LIMIT_CHANGED
        ).count()
        _jwt(self.admin).patch(
            f"{SEGMENTS_URL}{seg.pk}/", {"speed_limit_kmh": 80}, format="json"
        )
        after = AuditEvent.objects.filter(
            action=AuditAction.SEGMENT_SPEED_LIMIT_CHANGED
        ).count()
        self.assertEqual(after, before + 1)

    def test_intersection_creation_creates_audit_event(self):
        before = AuditEvent.objects.filter(
            action=AuditAction.INTERSECTION_CREATED
        ).count()
        _jwt(self.admin).post(INTERSECTIONS_URL, {"name": "Audit Jct"}, format="json")
        after  = AuditEvent.objects.filter(
            action=AuditAction.INTERSECTION_CREATED
        ).count()
        self.assertEqual(after, before + 1)

    def test_lane_creation_creates_audit_event(self):
        seg = _segment()
        before = AuditEvent.objects.filter(action=AuditAction.LANE_CREATED).count()
        _jwt(self.admin).post(
            LANES_URL,
            {"segment": seg.pk, "lane_number": 1, "lane_type": "travel"},
            format="json",
        )
        after  = AuditEvent.objects.filter(action=AuditAction.LANE_CREATED).count()
        self.assertEqual(after, before + 1)

    def test_audit_detail_never_contains_password(self):
        _jwt(self.admin).post(ROADS_URL, {"name": "Password Check Road"}, format="json")
        for ev in AuditEvent.objects.filter(action=AuditAction.ROAD_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))

    def test_audit_event_target_type_is_roads_road(self):
        _jwt(self.admin).post(ROADS_URL, {"name": "Target Road"}, format="json")
        ev = AuditEvent.objects.filter(action=AuditAction.ROAD_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "roads.road")


# ---------------------------------------------------------------------------
# 9. Regression tests
# ---------------------------------------------------------------------------

class TestRoadRegressionTests(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_endpoint_still_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_url_still_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_still_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_auth_me_still_works(self):
        user = _make_role_user("reg_user", "Traffic Analyst")
        resp = _jwt(user).get("/api/v1/auth/me/")
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
