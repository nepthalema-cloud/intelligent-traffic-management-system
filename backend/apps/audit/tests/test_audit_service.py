"""
Tests for the audit service — log_audit_event(), _scrub_detail, AuditAction constants.
"""

from django.test import TestCase, RequestFactory

from apps.audit.models import AuditEvent, Outcome
from apps.audit.services import (
    AuditAction,
    _scrub_detail,
    log_audit_event,
)


class TestScrubDetail(TestCase):
    """Sensitive keys must be stripped from detail before persistence."""

    def test_clean_dict_unchanged(self):
        d = {"role": "Analyst", "reason": "test"}
        self.assertEqual(_scrub_detail(d), d)

    def test_password_key_stripped(self):
        result = _scrub_detail({"password": "secret", "role": "Admin"})
        self.assertNotIn("password", result)
        self.assertIn("role", result)

    def test_token_keys_stripped(self):
        for key in ("access", "refresh", "token", "access_token", "refresh_token"):
            result = _scrub_detail({key: "jwt_value", "safe": "ok"})
            self.assertNotIn(key, result, f"Key '{key}' should be scrubbed")
            self.assertIn("safe", result)

    def test_secret_key_stripped(self):
        result = _scrub_detail({"secret_key": "abc", "info": "visible"})
        self.assertNotIn("secret_key", result)

    def test_authorization_stripped(self):
        result = _scrub_detail({"authorization": "Bearer xyz", "x": 1})
        self.assertNotIn("authorization", result)

    def test_none_returns_none(self):
        self.assertIsNone(_scrub_detail(None))

    def test_empty_dict_returns_none(self):
        # All keys scrubbed → empty → returns None
        result = _scrub_detail({"password": "x"})
        self.assertIsNone(result)

    def test_case_insensitive_scrubbing(self):
        result = _scrub_detail({"PASSWORD": "x", "safe": "y"})
        self.assertNotIn("PASSWORD", result)


class TestLogAuditEvent(TestCase):
    """log_audit_event() must create correct AuditEvent records."""

    def setUp(self):
        self.factory = RequestFactory()

    def _req(self):
        req = self.factory.get("/")
        req.META["REMOTE_ADDR"] = "10.0.0.1"
        req.META["HTTP_USER_AGENT"] = "TestBrowser/1.0"
        return req

    def test_creates_audit_event(self):
        before = AuditEvent.objects.count()
        log_audit_event(action=AuditAction.AUTH_LOGIN_SUCCESS, outcome=Outcome.SUCCESS)
        self.assertEqual(AuditEvent.objects.count(), before + 1)

    def test_action_stored_correctly(self):
        log_audit_event(action=AuditAction.AUTH_LOGIN_FAILURE, outcome=Outcome.FAILURE)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.action, AuditAction.AUTH_LOGIN_FAILURE)

    def test_outcome_stored_correctly(self):
        log_audit_event(action=AuditAction.AUTH_LOGOUT_SUCCESS, outcome=Outcome.SUCCESS)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.outcome, Outcome.SUCCESS)

    def test_ip_extracted_from_request(self):
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=self._req(),
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.ip_address, "10.0.0.1")

    def test_user_agent_extracted_from_request(self):
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=self._req(),
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.user_agent, "TestBrowser/1.0")

    def test_actor_populated_from_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username="actortest", password="P!")
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            actor=user,
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.actor_id, user.pk)
        self.assertEqual(ev.actor_username, "actortest")

    def test_no_actor_stores_null(self):
        log_audit_event(action=AuditAction.AUTH_LOGIN_FAILURE, outcome=Outcome.FAILURE)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertIsNone(ev.actor_id)
        self.assertIsNone(ev.actor_username)

    def test_target_auto_resolved_from_model_instance(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username="targettest", password="P!")
        log_audit_event(
            action=AuditAction.ADMIN_ROLE_ASSIGNED,
            outcome=Outcome.SUCCESS,
            target=user,
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.target_type, "accounts.user")
        self.assertEqual(ev.target_id, str(user.pk))

    def test_detail_scrubbed_before_storage(self):
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            detail={"password": "s3cr3t", "role": "Admin"},
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertIsNotNone(ev.detail)
        self.assertNotIn("password", ev.detail)
        self.assertIn("role", ev.detail)

    def test_returns_audit_event_instance(self):
        result = log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
        )
        self.assertIsInstance(result, AuditEvent)

    def test_no_request_stores_null_ip(self):
        log_audit_event(action=AuditAction.AUTH_LOGIN_SUCCESS, outcome=Outcome.SUCCESS)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertIsNone(ev.ip_address)

    def test_x_forwarded_for_used_as_ip(self):
        req = self.factory.get("/")
        req.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.5, 10.0.0.1"
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=req,
        )
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.ip_address, "203.0.113.5")


class TestAuditActionConstants(TestCase):
    def test_all_constants_are_strings(self):
        for attr in vars(AuditAction):
            if not attr.startswith("_"):
                val = getattr(AuditAction, attr)
                self.assertIsInstance(val, str, f"AuditAction.{attr} must be a string")

    def test_action_codes_use_dot_notation(self):
        for attr in vars(AuditAction):
            if not attr.startswith("_"):
                val = getattr(AuditAction, attr)
                self.assertIn(".", val, f"AuditAction.{attr}={val!r} must use dot notation")

    def test_required_actions_exist(self):
        required = [
            "AUTH_LOGIN_SUCCESS", "AUTH_LOGIN_FAILURE",
            "AUTH_REFRESH_SUCCESS", "AUTH_REFRESH_FAILURE",
            "AUTH_LOGOUT_SUCCESS", "AUTH_LOGOUT_FAILURE",
            "ADMIN_ROLE_ASSIGNED", "ADMIN_ROLE_REMOVED",
            "ADMIN_USER_ACTIVATED", "ADMIN_USER_DEACTIVATED",
        ]
        for name in required:
            self.assertTrue(
                hasattr(AuditAction, name),
                f"AuditAction.{name} is missing",
            )
