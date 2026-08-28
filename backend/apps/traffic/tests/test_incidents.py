# Tests for TrafficIncident - Phase 4C.4
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
from apps.traffic.models import TrafficIncident

User = get_user_model()
INC_URL = "/api/v1/traffic/incidents/"


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
    kw.setdefault("name", "Inc Road")
    return Road.objects.create(**kw)


def _segment(**kw):
    road = kw.pop("road", None) or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _intersection(**kw):
    kw.setdefault("name", "Inc Jct")
    return Intersection.objects.create(**kw)


def _incident(created_by=None, **kw):
    kw.setdefault("title", "Test incident")
    kw.setdefault("description", "Test incident description")
    kw.setdefault("incident_type", "accident")
    kw.setdefault("occurred_at", timezone.now())
    return TrafficIncident.objects.create(created_by=created_by, **kw)


def _post_incident(client, **kw):
    data = {
        "title": kw.get("title", "Test Inc"),
        "description": kw.get("description", "Description"),
        "incident_type": kw.get("incident_type", "accident"),
        "occurred_at": kw.get("occurred_at", timezone.now().strftime("%Y-%m-%dT%H:%M:%S")),
    }
    if "segment_ids" in kw:
        data["segment_ids"] = kw["segment_ids"]
    if "intersection" in kw and kw["intersection"]:
        data["intersection"] = kw["intersection"].pk
    return client.post(INC_URL, data, format="json")


class TestIncidentModelBasics(TestCase):
    def test_create_minimal(self):
        inc = _incident()
        self.assertEqual(inc.state, TrafficIncident.State.REPORTED)
        self.assertTrue(inc.is_active)
        self.assertIsNotNone(inc.created_at)
        self.assertIsNotNone(inc.updated_at)

    def test_default_state_is_reported(self):
        inc = _incident()
        self.assertEqual(inc.state, "reported")

    def test_str_contains_type_and_title(self):
        inc = _incident(title="Major accident on highway", incident_type="accident")
        self.assertIn("accident", str(inc))
        self.assertIn("Major accident", str(inc))

    def test_create_with_segments(self):
        seg1 = _segment(road=_road(name="R1"))
        seg2 = _segment(road=_road(name="R2"))
        inc = _incident()
        inc.segments.set([seg1, seg2])
        self.assertEqual(inc.segments.count(), 2)

    def test_create_with_intersection(self):
        inter = _intersection(name="ModelTestJct2")
        inc = TrafficIncident.objects.create(
            title="Signal fault", description="Desc",
            incident_type="other", occurred_at=timezone.now(),
            intersection=inter,
        )
        self.assertEqual(inc.intersection, inter)

    def test_create_with_created_by(self):
        user = _make_user("incmodel_user")
        inc = _incident(created_by=user)
        self.assertEqual(inc.created_by, user)

    def test_set_null_on_user_delete(self):
        user = _make_user("incuserdel")
        inc = _incident(created_by=user)
        User.objects.filter(pk=user.pk).delete()
        inc.refresh_from_db()
        self.assertIsNone(inc.created_by)

    def test_all_incident_types_valid(self):
        for i, (choice, _) in enumerate(TrafficIncident.IncidentType.choices):
            inc = TrafficIncident.objects.create(
                title=f"Inc {i}", description="D",
                incident_type=choice, occurred_at=timezone.now(),
            )
            self.assertEqual(inc.incident_type, choice)

    def test_soft_deactivate(self):
        inc = _incident()
        inc.is_active = False; inc.save()
        inc.refresh_from_db()
        self.assertFalse(inc.is_active)

    def test_ordering_newest_first(self):
        from datetime import timedelta
        now = timezone.now()
        i1 = _incident(occurred_at=now - timedelta(hours=2))
        i2 = _incident(occurred_at=now - timedelta(hours=1))
        pks = list(
            TrafficIncident.objects.filter(pk__in=[i1.pk, i2.pk]).values_list("pk", flat=True)
        )
        self.assertEqual(pks[0], i2.pk)


class TestIncidentLifecycle(TestCase):
    def setUp(self):
        self.inc = _incident()

    def test_initial_state_reported(self):
        self.assertEqual(self.inc.state, TrafficIncident.State.REPORTED)

    def test_valid_transition_reported_to_investigating(self):
        from apps.traffic.services import TrafficIncidentService
        actor = _make_user("lc_actor1")
        TrafficIncidentService.transition_state(
            actor=actor, incident=self.inc, new_state="investigating"
        )
        self.inc.refresh_from_db()
        self.assertEqual(self.inc.state, "investigating")

    def test_valid_transition_chain(self):
        from apps.traffic.services import TrafficIncidentService
        actor = _make_user("lc_actor2")
        for state in ["investigating", "managing", "resolved", "closed"]:
            TrafficIncidentService.transition_state(
                actor=actor, incident=self.inc, new_state=state
            )
        self.inc.refresh_from_db()
        self.assertEqual(self.inc.state, "closed")

    def test_invalid_transition_skip_state(self):
        from apps.traffic.services import TrafficIncidentService, InvalidStateTransitionError
        actor = _make_user("lc_actor3")
        with self.assertRaises(InvalidStateTransitionError):
            TrafficIncidentService.transition_state(
                actor=actor, incident=self.inc, new_state="managing"
            )

    def test_invalid_transition_backwards(self):
        from apps.traffic.services import TrafficIncidentService, InvalidStateTransitionError
        actor = _make_user("lc_actor4")
        self.inc.state = "resolved"; self.inc.save()
        with self.assertRaises(InvalidStateTransitionError):
            TrafficIncidentService.transition_state(
                actor=actor, incident=self.inc, new_state="reported"
            )

    def test_terminal_state_closed_no_transitions(self):
        from apps.traffic.services import TrafficIncidentService, InvalidStateTransitionError
        actor = _make_user("lc_actor5")
        self.inc.state = "closed"; self.inc.save()
        with self.assertRaises(InvalidStateTransitionError):
            TrafficIncidentService.transition_state(
                actor=actor, incident=self.inc, new_state="resolved"
            )

    def test_valid_transitions_dict_complete(self):
        for state in TrafficIncident.State.values:
            self.assertIn(
                state, TrafficIncident.VALID_TRANSITIONS,
                f"State '{state}' missing from VALID_TRANSITIONS"
            )


class TestIncidentUrlRouting(TestCase):
    def test_incident_list_resolves(self):
        m = resolve(INC_URL)
        self.assertEqual(m.url_name, "incident-list")
        self.assertEqual(m.namespace, "traffic")

    def test_incident_list_reverses(self):
        self.assertEqual(reverse("traffic:incident-list"), INC_URL)

    def test_incident_detail_resolves(self):
        self.assertEqual(resolve(f"{INC_URL}1/").url_name, "incident-detail")

    def test_incident_state_resolves(self):
        self.assertEqual(resolve(f"{INC_URL}1/state/").url_name, "incident-state")

    def test_incident_status_resolves(self):
        self.assertEqual(resolve(f"{INC_URL}1/status/").url_name, "incident-status")

    def test_invalid_prefixes_404(self):
        self.assertEqual(APIClient().get("/api/traffic/incidents/").status_code, 404)
        self.assertEqual(APIClient().get("/api/v1/v1/traffic/incidents/").status_code, 404)


class TestIncidentAuthentication(TestCase):
    def test_list_401(self):
        self.assertEqual(APIClient().get(INC_URL).status_code, 401)

    def test_post_401(self):
        self.assertEqual(APIClient().post(INC_URL).status_code, 401)

    def test_detail_401(self):
        _ensure_groups()
        inc = _incident()
        self.assertEqual(APIClient().get(f"{INC_URL}{inc.pk}/").status_code, 401)


class TestIncidentRBAC(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_role_user("inc_rbac_admin",   "System Administrator")
        self.tco     = _make_role_user("inc_rbac_tco",     "Traffic Control Officer")
        self.analyst = _make_role_user("inc_rbac_analyst", "Traffic Analyst")
        self.law     = _make_role_user("inc_rbac_law",     "Law Enforcement / Authorized Officer")
        self.cam     = _make_role_user("inc_rbac_cam",     "Camera/Sensor Technician")
        self.pay     = _make_role_user("inc_rbac_pay",     "Payment/Fines Officer")
        self.pub     = _make_role_user("inc_rbac_pub",     "Public User")

    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(INC_URL).status_code, 200)

    def test_tco_can_list(self):
        self.assertEqual(_jwt(self.tco).get(INC_URL).status_code, 200)

    def test_analyst_can_read(self):
        self.assertEqual(_jwt(self.analyst).get(INC_URL).status_code, 200)

    def test_law_can_read(self):
        self.assertEqual(_jwt(self.law).get(INC_URL).status_code, 200)

    def test_cam_tech_403(self):
        self.assertEqual(_jwt(self.cam).get(INC_URL).status_code, 403)

    def test_payment_403(self):
        self.assertEqual(_jwt(self.pay).get(INC_URL).status_code, 403)

    def test_public_403(self):
        self.assertEqual(_jwt(self.pub).get(INC_URL).status_code, 403)

    def test_admin_can_create(self):
        self.assertEqual(_post_incident(_jwt(self.admin)).status_code, 201)

    def test_tco_can_create(self):
        self.assertEqual(_post_incident(_jwt(self.tco)).status_code, 201)

    def test_analyst_cannot_create(self):
        self.assertEqual(_post_incident(_jwt(self.analyst)).status_code, 403)

    def test_law_cannot_create(self):
        self.assertEqual(_post_incident(_jwt(self.law)).status_code, 403)

    def test_superuser_can_create(self):
        su = User.objects.create_superuser("su_inc", password="SuP!")
        self.assertEqual(_post_incident(_jwt(su)).status_code, 201)

    def test_admin_can_update(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/", {"title": "Updated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_can_update(self):
        inc = _incident()
        resp = _jwt(self.tco).patch(
            f"{INC_URL}{inc.pk}/", {"title": "TCO Updated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_analyst_cannot_update(self):
        inc = _incident()
        resp = _jwt(self.analyst).patch(
            f"{INC_URL}{inc.pk}/", {"title": "No"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_transition_state(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_can_transition_state(self):
        inc = _incident()
        resp = _jwt(self.tco).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_analyst_cannot_transition_state(self):
        inc = _incident()
        resp = _jwt(self.analyst).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_deactivate(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_tco_can_deactivate(self):
        inc = _incident()
        resp = _jwt(self.tco).patch(
            f"{INC_URL}{inc.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)


class TestIncidentCRUD(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("inc_crud_admin", "System Administrator")
        self.seg   = _segment(road=_road(name="CRUD Inc Road"))

    def test_list_200_with_pagination(self):
        _incident(); _incident()
        resp = _jwt(self.admin).get(INC_URL)
        self.assertEqual(resp.status_code, 200)
        for k in ("count", "results"):
            self.assertIn(k, resp.json())

    def test_create_201(self):
        resp = _post_incident(_jwt(self.admin), segment_ids=[self.seg.pk])
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertIn(self.seg.pk, data["segment_ids"])

    def test_create_blank_title_400(self):
        resp = _jwt(self.admin).post(
            INC_URL,
            {"title": "  ", "description": "D",
             "incident_type": "other",
             "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M:%S")},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_missing_occurred_at_400(self):
        resp = _jwt(self.admin).post(
            INC_URL, {"title": "T", "description": "D"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_invalid_segment_id_400(self):
        resp = _post_incident(_jwt(self.admin), segment_ids=[999999])
        self.assertEqual(resp.status_code, 400)

    def test_get_detail_200(self):
        inc = _incident()
        resp = _jwt(self.admin).get(f"{INC_URL}{inc.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], inc.pk)

    def test_nonexistent_404(self):
        self.assertEqual(_jwt(self.admin).get(f"{INC_URL}999999/").status_code, 404)

    def test_patch_updates_title(self):
        inc = _incident()
        _jwt(self.admin).patch(f"{INC_URL}{inc.pk}/", {"title": "New Title"}, format="json")
        inc.refresh_from_db()
        self.assertEqual(inc.title, "New Title")

    def test_default_state_is_reported(self):
        resp = _post_incident(_jwt(self.admin))
        self.assertEqual(resp.json()["data"]["state"], "reported")

    def test_deactivate(self):
        inc = _incident()
        _jwt(self.admin).patch(f"{INC_URL}{inc.pk}/status/", {"is_active": False}, format="json")
        inc.refresh_from_db()
        self.assertFalse(inc.is_active)

    def test_active_only_filter(self):
        _incident(); inc2 = _incident(); inc2.is_active = False; inc2.save()
        resp = _jwt(self.admin).get(INC_URL + "?active_only=true")
        self.assertTrue(all(r["is_active"] for r in resp.json()["results"]))

    def test_state_filter(self):
        _incident()
        inc2 = _incident(); inc2.state = "resolved"; inc2.save()
        resp = _jwt(self.admin).get(INC_URL + "?state=resolved")
        for r in resp.json()["results"]:
            self.assertEqual(r["state"], "resolved")

    def test_created_by_set_from_actor(self):
        resp = _post_incident(_jwt(self.admin))
        self.assertEqual(resp.json()["data"]["created_by"], self.admin.pk)

    def test_no_delete_endpoint(self):
        inc = _incident()
        resp = _jwt(self.admin).delete(f"{INC_URL}{inc.pk}/")
        self.assertEqual(resp.status_code, 405)


class TestIncidentStateTransitions(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("inc_state_admin", "System Administrator")

    def test_api_valid_transition_200(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["state"], "investigating")

    def test_api_invalid_transition_400(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "closed"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_same_state_400(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "reported"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_invalid_state_value_400(self):
        inc = _incident()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "banana"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_full_lifecycle_api(self):
        inc = _incident()
        for s in ["investigating", "managing", "resolved", "closed"]:
            resp = _jwt(self.admin).patch(
                f"{INC_URL}{inc.pk}/state/", {"state": s}, format="json"
            )
            self.assertEqual(resp.status_code, 200, f"Failed at state: {s}")
        inc.refresh_from_db()
        self.assertEqual(inc.state, "closed")

    def test_terminal_state_closed_rejects_transition(self):
        inc = _incident(); inc.state = "closed"; inc.save()
        resp = _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "resolved"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_state_persists_in_db(self):
        inc = _incident()
        _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        inc.refresh_from_db()
        self.assertEqual(inc.state, "investigating")


class TestIncidentAudit(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_role_user("inc_aud_admin", "System Administrator")

    def _count(self, action):
        return AuditEvent.objects.filter(action=action).count()

    def test_incident_created_audit(self):
        before = self._count(AuditAction.TRAFFIC_INCIDENT_CREATED)
        _post_incident(_jwt(self.admin))
        self.assertEqual(self._count(AuditAction.TRAFFIC_INCIDENT_CREATED), before + 1)

    def test_incident_created_audit_actor(self):
        _post_incident(_jwt(self.admin))
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_INCIDENT_CREATED).latest("timestamp")
        self.assertEqual(ev.actor_username, self.admin.username)

    def test_incident_created_audit_target_type(self):
        _post_incident(_jwt(self.admin))
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_INCIDENT_CREATED).latest("timestamp")
        self.assertEqual(ev.target_type, "traffic.trafficincident")

    def test_incident_updated_audit(self):
        inc = _incident()
        before = self._count(AuditAction.TRAFFIC_INCIDENT_UPDATED)
        _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/", {"title": "Updated"}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_INCIDENT_UPDATED), before + 1)

    def test_state_changed_audit(self):
        inc = _incident()
        before = self._count(AuditAction.TRAFFIC_INCIDENT_STATE_CHANGED)
        _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_INCIDENT_STATE_CHANGED), before + 1)

    def test_state_audit_detail_has_states(self):
        inc = _incident()
        _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/state/", {"state": "investigating"}, format="json"
        )
        ev = AuditEvent.objects.filter(
            action=AuditAction.TRAFFIC_INCIDENT_STATE_CHANGED).latest("timestamp")
        self.assertEqual(ev.detail.get("old_state"), "reported")
        self.assertEqual(ev.detail.get("new_state"), "investigating")

    def test_deactivated_audit(self):
        inc = _incident()
        before = self._count(AuditAction.TRAFFIC_INCIDENT_DEACTIVATED)
        _jwt(self.admin).patch(
            f"{INC_URL}{inc.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(self._count(AuditAction.TRAFFIC_INCIDENT_DEACTIVATED), before + 1)

    def test_no_password_in_detail(self):
        _post_incident(_jwt(self.admin))
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_INCIDENT_CREATED):
            self.assertNotIn("password", str(ev.detail or ""))

    def test_no_token_in_detail(self):
        _post_incident(_jwt(self.admin))
        for ev in AuditEvent.objects.filter(action=AuditAction.TRAFFIC_INCIDENT_CREATED):
            self.assertNotIn("access", str(ev.detail or ""))
            self.assertNotIn("refresh", str(ev.detail or ""))


class TestIncidentRegression(TestCase):
    def setUp(self):
        _ensure_groups()

    def test_health_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_events_still_work(self):
        admin = _make_role_user("reg_evt_inc", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/events/").status_code, 200)

    def test_measurements_still_work(self):
        admin = _make_role_user("reg_meas_inc", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/measurements/").status_code, 200)

    def test_signals_still_work(self):
        admin = _make_role_user("reg_sig_inc", "System Administrator")
        self.assertEqual(_jwt(admin).get("/api/v1/traffic/signals/").status_code, 200)

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
