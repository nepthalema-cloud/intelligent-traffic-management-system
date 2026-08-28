# Tests for TrafficEvent - Phase 4C.3
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
from apps.roads.models import Intersection, Road, RoadSegment
from apps.traffic.models import TrafficEvent

User = get_user_model()
EVENTS_URL = "/api/v1/traffic/events/"


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
    kw.setdefault("name", "Event Road")
    return Road.objects.create(**kw)


def _segment(**kw):
    road = kw.pop("road", None) or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _intersection(**kw):
    kw.setdefault("name", "Event Jct")
    return Intersection.objects.create(**kw)


def _event(created_by=None, segment=None, **kw):
    kw.setdefault("event_type", "congestion")
    kw.setdefault("description", "Test traffic event")
    kw.setdefault("occurred_at", timezone.now())
    return TrafficEvent.objects.create(
        segment=segment,
        created_by=created_by,
        **kw,
    )


def _post_event(client, **kw):
    data = {
        "event_type": kw.get("event_type", "congestion"),
        "description": kw.get("description", "Test event"),
        "occurred_at": kw.get("occurred_at", timezone.now().strftime("%Y-%m-%dT%H:%M:%S")),
    }
    if "segment" in kw:
        data["segment"] = kw["segment"].pk if kw["segment"] else None
    if "intersection" in kw:
        data["intersection"] = kw["intersection"].pk if kw["intersection"] else None
    return client.post(EVENTS_URL, data, format="json")


class TestEventModelBasics(TestCase):
    def test_create_minimal(self):
        e = _event()
        self.assertIsNotNone(e.pk)
        self.assertTrue(e.is_active)
        self.assertIsNotNone(e.created_at)
        self.assertIsNotNone(e.updated_at)

    def test_create_with_segment(self):
        seg = _segment()
        e = _event(segment=seg)
        self.assertEqual(e.segment, seg)

    def test_create_with_intersection(self):
        inter = _intersection(name="ModelTestJct")
        e = TrafficEvent.objects.create(
            event_type="signal_fault",
            description="Signal fault at junction",
            occurred_at=timezone.now(),
            intersection=inter,
        )
        self.assertEqual(e.intersection, inter)

    def test_create_with_created_by(self):
        user = _make_user("evtcreator")
        e = _event(created_by=user)
        self.assertEqual(e.created_by, user)

    def test_soft_deactivate(self):
        e = _event()
        e.is_active = False; e.save()
        e.refresh_from_db()
        self.assertFalse(e.is_active)

    def test_str_contains_event_type(self):
        e = _event()
        self.assertIn("congestion", str(e))

    def test_event_types_all_valid(self):
        for i, (choice, _) in enumerate(TrafficEvent.EventType.choices):
            ev = TrafficEvent.objects.create(
                event_type=choice,
                description=f"Event {i}",
                occurred_at=timezone.now(),
            )
            self.assertEqual(ev.event_type, choice)

    def test_ordering_newest_first(self):
        from datetime import timedelta
        now = timezone.now()
        e1 = TrafficEvent.objects.create(
            description="Old", event_type="other",
            occurred_at=now - timedelta(hours=2),
        )
        e2 = TrafficEvent.objects.create(
            description="New", event_type="other",
            occurred_at=now - timedelta(hours=1),
        )
        pks = list(
            TrafficEvent.objects.filter(pk__in=[e1.pk, e2.pk]).values_list("pk", flat=True)
        )
        self.assertEqual(pks[0], e2.pk)

    def test_set_null_on_segment_delete(self):
        road = _road(name="Null Evt Road")
        seg = _segment(road=road)
        e = _event(segment=seg)
        RoadSegment.objects.filter(pk=seg.pk).delete()
        e.refresh_from_db()
        self.assertIsNone(e.segment)

    def test_set_null_on_user_delete(self):
        user = _make_user("evtdel_user")
        e = _event(created_by=user)
        User.objects.filter(pk=user.pk).delete()
        e.refresh_from_db()
        self.assertIsNone(e.created_by)

    def test_has_updated_at(self):
        e = _event()
        self.assertIsNotNone(e.updated_at)

    def test_has_is_active(self):
        e = _event()
        self.assertTrue(e.is_active)


class TestEventUrlRouting(TestCase):
    def test_event_list_resolves(self):
        m = resolve(EVENTS_URL)
        self.assertEqual(m.url_name, "event-list")
        self.assertEqual(m.namespace, "traffic")

    def test_event_list_reverses(self):
        self.assertEqual(reverse("traffic:event-list"), EVENTS_URL)

    def test_event_detail_resolves(self):
        self.assertEqual(resolve(f"{EVENTS_URL}1/").url_name, "event-detail")

    def test_event_status_resolves(self):
        self.assertEqual(resolve(f"{EVENTS_URL}1/status/").url_name, "event-status")


class TestEventAuthentication(TestCase):
    def test_list_401(self):
        self.assertEqual(APIClient().get(EVENTS_URL).status_code, 401)

    def test_post_401(self):
        self.assertEqual(APIClient().post(EVENTS_URL).status_code, 401)

    def test_detail_401(self):
        _ensure_groups()
        e = _event()
        self.assertEqual(APIClient().get(f"{EVENTS_URL}{e.pk}/").status_code, 401)


class TestEventRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("tevt_admin",   "System Administrator")
        self.tco     = _make_role_user("tevt_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("tevt_analyst", "Traffic Analyst")
        self.law     = _make_role_user("tevt_law",     "Law Enforcement / Authorized Officer")
        self.cam     = _make_role_user("tevt_cam",     "Camera/Sensor Technician")
        self.pay     = _make_role_user("tevt_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("tevt_pub",     "Public User")

    # Reads
    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(EVENTS_URL).status_code, 200)

    def test_tco_can_list(self):
        self.assertEqual(_jwt(self.tco).get(EVENTS_URL).status_code, 200)

    def test_analyst_can_read(self):
        self.assertEqual(_jwt(self.analyst).get(EVENTS_URL).status_code, 200)

    def test_law_can_read(self):
        self.assertEqual(_jwt(self.law).get(EVENTS_URL).status_code, 200)

    def test_cam_tech_403(self):
        self.assertEqual(_jwt(self.cam).get(EVENTS_URL).status_code, 403)

    def test_payment_officer_403(self):
        self.assertEqual(_jwt(self.pay).get(EVENTS_URL).status_code, 403)

    def test_public_user_403(self):
        self.assertEqual(_jwt(self.pub).get(EVENTS_URL).status_code, 403)

    # Creates (Admin + TCO)
    def test_admin_can_create(self):
        self.assertEqual(_post_event(_jwt(self.admin)).status_code, 201)

    def test_tco_can_create(self):
        self.assertEqual(_post_event(_jwt(self.tco)).status_code, 201)

    def test_analyst_cannot_create(self):
        self.assertEqual(_post_event(_jwt(self.analyst)).status_code, 403)

    def test_law_cannot_create(self):
        self.assertEqual(_post_event(_jwt(self.law)).status_code, 403)

    def test_superuser_can_create(self):
        su = User.objects.create_superuser("su_evt", password="SuP!")
        self.assertEqual(_post_event(_jwt(su)).status_code, 201)

    # Updates (Admin + TCO)
    def test_admin_can_update(self):
        e = _event()
        resp = _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "Updated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_can_update(self):
        e = _event()
        resp = _jwt(self.tco).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "TCO Updated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_analyst_cannot_update(self):
        e = _event()
        resp = _jwt(self.analyst).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_law_cannot_update(self):
        e = _event()
        resp = _jwt(self.law).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    # Status (Admin only)
    def test_admin_can_deactivate(self):
        e = _event()
        resp = _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_cannot_deactivate(self):
        e = _event()
        resp = _jwt(self.tco).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


class TestEventCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("crud_evt_admin", "System Administrator")
        self.seg   = _segment(road=_road(name="CRUD Evt Road"))

    def test_list_200_with_pagination(self):
        _event(); _event()
        resp = _jwt(self.admin).get(EVENTS_URL)
        self.assertEqual(resp.status_code, 200)
        for k in ("count", "results"):
            self.assertIn(k, resp.json())

    def test_create_201(self):
        resp = _post_event(_jwt(self.admin), segment=self.seg, event_type="congestion")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["event_type"], "congestion")
        self.assertEqual(data["segment"], self.seg.pk)

    def test_create_blank_description_400(self):
        resp = _jwt(self.admin).post(
            EVENTS_URL,
            {"event_type": "other", "description": "  ",
             "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M:%S")},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_missing_description_400(self):
        resp = _jwt(self.admin).post(
            EVENTS_URL,
            {"event_type": "other",
             "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M:%S")},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_missing_occurred_at_400(self):
        resp = _jwt(self.admin).post(
            EVENTS_URL, {"event_type": "other", "description": "Test"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_detail_200(self):
        e = _event(segment=self.seg)
        resp = _jwt(self.admin).get(f"{EVENTS_URL}{e.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], e.pk)

    def test_nonexistent_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{EVENTS_URL}999999/").status_code, 404)

    def test_patch_updates_description(self):
        e = _event()
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "Updated desc"}, format="json"
        )
        e.refresh_from_db()
        self.assertEqual(e.description, "Updated desc")

    def test_deactivate_via_status(self):
        e = _event()
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": False}, format="json"
        )
        e.refresh_from_db()
        self.assertFalse(e.is_active)

    def test_reactivate_via_status(self):
        e = _event()
        e.is_active = False; e.save()
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": True}, format="json"
        )
        e.refresh_from_db()
        self.assertTrue(e.is_active)

    def test_status_non_bool_400(self):
        e = _event()
        resp = _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": "yes"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_active_only_filter(self):
        _event(); e2 = _event(); e2.is_active = False; e2.save()
        resp = _jwt(self.admin).get(EVENTS_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_event_type_filter(self):
        _event(); TrafficEvent.objects.create(
            event_type="roadwork", description="Roadwork", occurred_at=timezone.now()
        )
        resp = _jwt(self.admin).get(EVENTS_URL + "?event_type=roadwork")
        for r in resp.json()["results"]:
            self.assertEqual(r["event_type"], "roadwork")

    def test_segment_filter(self):
        _event(segment=self.seg)
        _event()  # no segment
        resp = _jwt(self.admin).get(EVENTS_URL + f"?segment={self.seg.pk}")
        for r in resp.json()["results"]:
            self.assertEqual(r["segment"], self.seg.pk)

    def test_created_by_set_from_actor(self):
        resp = _post_event(_jwt(self.admin))
        self.assertEqual(resp.json()["data"]["created_by"], self.admin.pk)

    def test_response_has_created_by_username(self):
        resp = _post_event(_jwt(self.admin))
        self.assertEqual(
            resp.json()["data"]["created_by_username"], self.admin.username
        )

    def test_no_delete_endpoint(self):
        e = _event()
        resp = _jwt(self.admin).delete(f"{EVENTS_URL}{e.pk}/")
        self.assertEqual(resp.status_code, 405)


class TestEventAudit(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("aud_evt_admin", "System Administrator")

    def _count(self, action):
        return AuditEvent.objects.filter(action=action).count()

    def test_event_created_audit(self):
        before = self._count(AuditAction.TRAFFIC_EVENT_CREATED)
        _post_event(_jwt(self.admin))
        self.assertEqual(self._count(AuditAction.TRAFFIC_EVENT_CREATED), before + 1)

    def test_event_created_audit_actor(self):
        _post_event(_jwt(self.admin))
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_EVENT_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, self.admin.username)

    def test_event_created_audit_target_type(self):
        _post_event(_jwt(self.admin))
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_EVENT_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "traffic.trafficevent")

    def test_event_updated_audit(self):
        e = _event()
        before = self._count(AuditAction.TRAFFIC_EVENT_UPDATED)
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/", {"description": "Updated"}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_EVENT_UPDATED), before + 1)

    def test_event_deactivated_audit(self):
        e = _event()
        before = self._count(AuditAction.TRAFFIC_EVENT_DEACTIVATED)
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_EVENT_DEACTIVATED), before + 1)

    def test_event_activated_audit(self):
        e = _event(); e.is_active = False; e.save()
        before = self._count(AuditAction.TRAFFIC_EVENT_ACTIVATED)
        _jwt(self.admin).patch(
            f"{EVENTS_URL}{e.pk}/status/", {"is_active": True}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_EVENT_ACTIVATED), before + 1)

    def test_no_password_in_detail(self):
        _post_event(_jwt(self.admin))
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_EVENT_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))

    def test_no_token_in_detail(self):
        _post_event(_jwt(self.admin))
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_EVENT_CREATED):
            self.assertNotIn("access", str(ev.detail or ""))
            self.assertNotIn("refresh", str(ev.detail or ""))


class TestEventRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_old_health_404(self):
        self.assertEqual(APIClient().get("/api/health/").status_code, 404)

    def test_double_prefix_404(self):
        self.assertEqual(APIClient().get("/api/v1/v1/health/").status_code, 404)

    def test_signals_still_work(self):
        admin = _make_role_user("reg_sig_evt", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/signals/").status_code, 200)

    def test_measurements_still_work(self):
        admin = _make_role_user("reg_meas_evt", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/measurements/").status_code, 200)

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
