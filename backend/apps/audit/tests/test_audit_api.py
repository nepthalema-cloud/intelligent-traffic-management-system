"""
Tests for the audit REST API endpoints.

GET /api/v1/audit/events/
GET /api/v1/audit/events/{id}/
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent, Outcome
from apps.audit.services import AuditAction, log_audit_event

User = get_user_model()

LIST_URL = "/api/v1/audit/events/"


def _ensure_groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _make_user(username, password="ApiAuditPass123!"):
    return User.objects.create_user(username=username, password=password)


def _make_admin(username):
    _ensure_groups()
    user = _make_user(username)
    user.groups.add(Group.objects.get(name="System Administrator"))
    return user


def _jwt(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(user))}")
    return c


def _create_event(**kwargs):
    defaults = dict(action=AuditAction.AUTH_LOGIN_SUCCESS, outcome=Outcome.SUCCESS)
    defaults.update(kwargs)
    return AuditEvent.objects.create(**defaults)


class TestAuditApiUrlRouting(TestCase):
    def test_event_list_resolves(self):
        m = resolve(LIST_URL)
        self.assertEqual(m.url_name, "event-list")
        self.assertEqual(m.namespace, "audit")

    def test_event_list_reverses(self):
        self.assertEqual(reverse("audit:event-list"), LIST_URL)

    def test_event_detail_resolves(self):
        import uuid
        uid = str(uuid.uuid4())
        m = resolve(f"/api/v1/audit/events/{uid}/")
        self.assertEqual(m.url_name, "event-detail")


class TestAuditEventListAccess(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin   = _make_admin("auditapi_admin")
        self.regular = _make_user("auditapi_regular")
        _create_event(actor_username="someone")

    def test_unauthenticated_returns_401(self):
        self.assertEqual(APIClient().get(LIST_URL).status_code, 401)

    def test_regular_user_returns_403(self):
        self.assertEqual(_jwt(self.regular).get(LIST_URL).status_code, 403)

    def test_admin_returns_200(self):
        self.assertEqual(_jwt(self.admin).get(LIST_URL).status_code, 200)

    def test_superuser_returns_200(self):
        su = User.objects.create_superuser(username="audit_su", password="Su123!")
        self.assertEqual(_jwt(su).get(LIST_URL).status_code, 200)

    def test_response_has_pagination_envelope(self):
        resp = _jwt(self.admin).get(LIST_URL)
        body = resp.json()
        for key in ("count", "results", "next", "previous"):
            self.assertIn(key, body)

    def test_results_contain_expected_fields(self):
        resp = _jwt(self.admin).get(LIST_URL)
        results = resp.json()["results"]
        self.assertGreater(len(results), 0)
        first = results[0]
        for field in ("id", "timestamp", "action", "outcome", "actor_username"):
            self.assertIn(field, first)

    def test_no_write_methods_allowed(self):
        for method in ("post", "put", "patch", "delete"):
            resp = getattr(_jwt(self.admin), method)(LIST_URL, data={})
            self.assertEqual(resp.status_code, 405, f"{method.upper()} should return 405")

    def test_filter_by_action(self):
        _create_event(action=AuditAction.AUTH_LOGOUT_SUCCESS)
        resp = _jwt(self.admin).get(LIST_URL + f"?action={AuditAction.AUTH_LOGOUT_SUCCESS}")
        results = resp.json()["results"]
        self.assertTrue(all(r["action"] == AuditAction.AUTH_LOGOUT_SUCCESS for r in results))

    def test_filter_by_outcome(self):
        _create_event(outcome=Outcome.FAILURE)
        resp = _jwt(self.admin).get(LIST_URL + "?outcome=failure")
        results = resp.json()["results"]
        self.assertTrue(all(r["outcome"] == "failure" for r in results))


class TestAuditEventDetailAccess(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("auditdetail_admin")
        self.ev = _create_event(actor_username="detailactor")
        self.url = f"/api/v1/audit/events/{self.ev.pk}/"

    def test_unauthenticated_returns_401(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)

    def test_regular_user_returns_403(self):
        regular = _make_user("auditdetail_regular")
        self.assertEqual(_jwt(regular).get(self.url).status_code, 403)

    def test_admin_returns_200(self):
        self.assertEqual(_jwt(self.admin).get(self.url).status_code, 200)

    def test_returns_correct_event(self):
        resp = _jwt(self.admin).get(self.url)
        data = resp.json()["data"]
        self.assertEqual(data["id"], str(self.ev.pk))
        self.assertEqual(data["actor_username"], "detailactor")

    def test_nonexistent_event_returns_404(self):
        import uuid
        url = f"/api/v1/audit/events/{uuid.uuid4()}/"
        self.assertEqual(_jwt(self.admin).get(url).status_code, 404)

    def test_no_write_methods_allowed(self):
        for method in ("post", "put", "patch", "delete"):
            resp = getattr(_jwt(self.admin), method)(self.url, data={})
            self.assertEqual(resp.status_code, 405)


class TestAuditApiSecretSafety(TestCase):
    """Audit API must never expose passwords, tokens, or SECRET_KEY."""

    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("auditsec_admin")
        _create_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            detail={"role": "Admin"},  # clean detail
        )

    def test_no_password_in_list_response(self):
        content = _jwt(self.admin).get(LIST_URL).content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)

    def test_no_secret_key_in_list_response(self):
        from django.conf import settings as djsettings
        content = _jwt(self.admin).get(LIST_URL).content.decode()
        self.assertNotIn(djsettings.SECRET_KEY, content)

    def test_audit_records_cannot_be_deleted_via_api(self):
        ev = _create_event()
        url = f"/api/v1/audit/events/{ev.pk}/"
        resp = _jwt(self.admin).delete(url)
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(AuditEvent.objects.filter(pk=ev.pk).exists())

    def test_audit_records_cannot_be_modified_via_api(self):
        ev = _create_event()
        url = f"/api/v1/audit/events/{ev.pk}/"
        resp = _jwt(self.admin).patch(url, {"action": "hacked"}, format="json")
        self.assertEqual(resp.status_code, 405)
        ev.refresh_from_db()
        self.assertNotEqual(ev.action, "hacked")


class TestAuditApiRegression(TestCase):
    """Existing endpoints must not be broken by the audit app addition."""

    def setUp(self):
        _ensure_groups()

    def test_health_endpoint_still_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_login_still_works(self):
        User.objects.create_user(username="auditregr", password="AuditRegr123!")
        resp = APIClient().post(
            "/api/v1/auth/login/",
            {"username": "auditregr", "password": "AuditRegr123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_no_pending_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending migrations: {plan}")

    def test_django_check_passes(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("check", stdout=out, stderr=out)
        self.assertIn("no issues", out.getvalue().lower())
