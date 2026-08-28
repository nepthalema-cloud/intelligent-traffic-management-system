"""
Integration tests verifying that authentication and admin operations
produce the correct audit events.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES, TRAFFIC_ANALYST
from apps.audit.models import AuditEvent, Outcome
from apps.audit.services import AuditAction

User = get_user_model()

LOGIN_URL   = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL  = "/api/v1/auth/logout/"


def _ensure_groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _make_user(username, password="AuditPass123!", active=True):
    user = User.objects.create_user(username=username, password=password)
    if not active:
        user.is_active = False
        user.save()
    return user


def _make_admin(username):
    _ensure_groups()
    user = _make_user(username)
    user.groups.add(Group.objects.get(name="System Administrator"))
    return user


def _jwt_client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(user))}")
    return c


def _login(username, password="AuditPass123!"):
    c = APIClient()
    return c.post(LOGIN_URL, {"username": username, "password": password}, format="json")


class TestLoginAuditEvents(TestCase):
    def setUp(self):
        self.user = _make_user("audit_login_ok")
        self.inactive = _make_user("audit_login_inactive", active=False)

    def test_successful_login_creates_success_event(self):
        before = AuditEvent.objects.count()
        _login("audit_login_ok")
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        ev = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_SUCCESS).latest("timestamp")
        self.assertEqual(ev.outcome, Outcome.SUCCESS)
        self.assertEqual(ev.actor_username, "audit_login_ok")

    def test_successful_login_event_has_correct_action(self):
        _login("audit_login_ok")
        ev = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_SUCCESS).latest("timestamp")
        self.assertEqual(ev.action, AuditAction.AUTH_LOGIN_SUCCESS)

    def test_failed_login_creates_failure_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        _login("audit_login_ok", "wrong_password")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_failed_login_event_outcome_is_failure(self):
        _login("audit_login_ok", "wrong_password")
        ev = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).latest("timestamp")
        self.assertEqual(ev.outcome, Outcome.FAILURE)

    def test_inactive_user_login_creates_failure_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        _login("audit_login_inactive")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_nonexistent_user_login_creates_failure_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        _login("nobody_xyz_999")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_login_event_never_contains_password(self):
        _login("audit_login_ok")
        for ev in AuditEvent.objects.all():
            detail_str = str(ev.detail or "")
            self.assertNotIn("AuditPass123!", detail_str)
            self.assertNotIn("password", detail_str)

    def test_login_event_never_contains_token(self):
        _login("audit_login_ok")
        for ev in AuditEvent.objects.filter(action=AuditAction.AUTH_LOGIN_SUCCESS):
            detail_str = str(ev.detail or "")
            self.assertNotIn("access", detail_str)
            self.assertNotIn("refresh", detail_str)


class TestRefreshAuditEvents(TestCase):
    def setUp(self):
        self.user = _make_user("audit_refresh_user")
        login_data = _login("audit_refresh_user").json()["data"]
        self.refresh_token = login_data["refresh"]
        self.access_token  = login_data["access"]

    def test_successful_refresh_creates_success_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_SUCCESS).count()
        APIClient().post(REFRESH_URL, {"refresh": self.refresh_token}, format="json")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_SUCCESS).count()
        self.assertEqual(after, before + 1)

    def test_failed_refresh_creates_failure_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_FAILURE).count()
        APIClient().post(REFRESH_URL, {"refresh": "invalid.token.here"}, format="json")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_blacklisted_token_refresh_creates_failure_event(self):
        # Use the token once (rotation blacklists it)
        APIClient().post(REFRESH_URL, {"refresh": self.refresh_token}, format="json")
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_FAILURE).count()
        # Try to reuse it — it is now blacklisted
        APIClient().post(REFRESH_URL, {"refresh": self.refresh_token}, format="json")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_refresh_event_never_contains_token_value(self):
        APIClient().post(REFRESH_URL, {"refresh": self.refresh_token}, format="json")
        for ev in AuditEvent.objects.filter(action=AuditAction.AUTH_REFRESH_SUCCESS):
            detail_str = str(ev.detail or "")
            self.assertNotIn("refresh", detail_str)
            self.assertNotIn("access", detail_str)


class TestLogoutAuditEvents(TestCase):
    def setUp(self):
        self.user = _make_user("audit_logout_user")
        login_data = _login("audit_logout_user").json()["data"]
        self.refresh_token = login_data["refresh"]
        self.access_token  = login_data["access"]

    def _authed_client(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        return c

    def test_successful_logout_creates_success_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_SUCCESS).count()
        self._authed_client().post(LOGOUT_URL, {"refresh": self.refresh_token}, format="json")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_SUCCESS).count()
        self.assertEqual(after, before + 1)

    def test_logout_event_actor_is_correct_user(self):
        self._authed_client().post(LOGOUT_URL, {"refresh": self.refresh_token}, format="json")
        ev = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_SUCCESS).latest("timestamp")
        self.assertEqual(ev.actor_username, "audit_logout_user")

    def test_failed_logout_invalid_token_creates_failure_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_FAILURE).count()
        self._authed_client().post(LOGOUT_URL, {"refresh": "bad.token"}, format="json")
        after = AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_logout_event_never_contains_token_value(self):
        self._authed_client().post(LOGOUT_URL, {"refresh": self.refresh_token}, format="json")
        for ev in AuditEvent.objects.filter(action=AuditAction.AUTH_LOGOUT_SUCCESS):
            detail_str = str(ev.detail or "")
            self.assertNotIn("refresh", detail_str)
            self.assertNotIn("access", detail_str)


class TestAdminAuditEvents(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("audit_admin")
        self.target = _make_user("audit_target")

    def test_role_assigned_creates_audit_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_ASSIGNED).count()
        _jwt_client(self.admin).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        after = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_ASSIGNED).count()
        self.assertEqual(after, before + 1)

    def test_role_assigned_event_has_role_in_detail(self):
        _jwt_client(self.admin).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        ev = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_ASSIGNED).latest("timestamp")
        self.assertEqual(ev.detail["role"], TRAFFIC_ANALYST)

    def test_role_assigned_event_has_correct_target(self):
        _jwt_client(self.admin).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        ev = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_ASSIGNED).latest("timestamp")
        self.assertEqual(ev.target_id, str(self.target.pk))
        self.assertEqual(ev.target_type, "accounts.user")

    def test_role_assigned_event_actor_is_admin(self):
        _jwt_client(self.admin).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        ev = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_ASSIGNED).latest("timestamp")
        self.assertEqual(ev.actor_username, "audit_admin")

    def test_role_removed_creates_audit_event(self):
        self.target.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        before = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_REMOVED).count()
        _jwt_client(self.admin).delete(
            f"/api/v1/auth/users/{self.target.pk}/roles/Traffic%20Analyst/"
        )
        after = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_REMOVED).count()
        self.assertEqual(after, before + 1)

    def test_role_removed_event_has_role_in_detail(self):
        self.target.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        _jwt_client(self.admin).delete(
            f"/api/v1/auth/users/{self.target.pk}/roles/Traffic%20Analyst/"
        )
        ev = AuditEvent.objects.filter(action=AuditAction.ADMIN_ROLE_REMOVED).latest("timestamp")
        self.assertIn("Traffic Analyst", ev.detail.get("role", ""))

    def test_user_deactivated_creates_audit_event(self):
        before = AuditEvent.objects.filter(action=AuditAction.ADMIN_USER_DEACTIVATED).count()
        _jwt_client(self.admin).patch(
            f"/api/v1/auth/users/{self.target.pk}/status/",
            {"is_active": False}, format="json"
        )
        after = AuditEvent.objects.filter(action=AuditAction.ADMIN_USER_DEACTIVATED).count()
        self.assertEqual(after, before + 1)

    def test_user_activated_creates_audit_event(self):
        self.target.is_active = False; self.target.save()
        before = AuditEvent.objects.filter(action=AuditAction.ADMIN_USER_ACTIVATED).count()
        _jwt_client(self.admin).patch(
            f"/api/v1/auth/users/{self.target.pk}/status/",
            {"is_active": True}, format="json"
        )
        after = AuditEvent.objects.filter(action=AuditAction.ADMIN_USER_ACTIVATED).count()
        self.assertEqual(after, before + 1)

    def test_status_event_detail_contains_is_active(self):
        _jwt_client(self.admin).patch(
            f"/api/v1/auth/users/{self.target.pk}/status/",
            {"is_active": False}, format="json"
        )
        ev = AuditEvent.objects.filter(action=AuditAction.ADMIN_USER_DEACTIVATED).latest("timestamp")
        self.assertFalse(ev.detail["is_active"])
