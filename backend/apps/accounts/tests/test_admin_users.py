"""
Comprehensive tests for Phase 3C administrative user and role management APIs.

Endpoints under test
--------------------
GET    /api/v1/auth/users/
GET    /api/v1/auth/users/{id}/
POST   /api/v1/auth/users/{id}/roles/
DELETE /api/v1/auth/users/{id}/roles/{role}/
PATCH  /api/v1/auth/users/{id}/status/

Also covers regression for:
GET /api/v1/auth/me/
GET /api/v1/health/
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES, SYSTEM_ADMIN, TRAFFIC_ANALYST, PUBLIC_USER

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ensure_groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _make_user(username, password="Pass123!", **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


def _make_admin(username="admin"):
    user = _make_user(username)
    _ensure_groups()
    user.groups.add(Group.objects.get(name=SYSTEM_ADMIN))
    return user


def _make_superuser(username="superuser"):
    return User.objects.create_superuser(username=username, password="Super123!")


def _jwt(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


# ---------------------------------------------------------------------------
# 1. URL routing
# ---------------------------------------------------------------------------

class TestAdminUrlRouting(TestCase):
    def test_user_list_resolves(self):
        m = resolve("/api/v1/auth/users/")
        self.assertEqual(m.url_name, "user-list")
        self.assertEqual(m.namespace, "accounts")

    def test_user_list_reverses(self):
        self.assertEqual(reverse("accounts:user-list"), "/api/v1/auth/users/")

    def test_user_detail_resolves(self):
        m = resolve("/api/v1/auth/users/1/")
        self.assertEqual(m.url_name, "user-detail")

    def test_user_detail_reverses(self):
        self.assertEqual(reverse("accounts:user-detail", kwargs={"user_id": 42}),
                         "/api/v1/auth/users/42/")

    def test_role_assign_resolves(self):
        m = resolve("/api/v1/auth/users/1/roles/")
        self.assertEqual(m.url_name, "user-role-assign")

    def test_role_remove_resolves(self):
        m = resolve("/api/v1/auth/users/1/roles/Traffic%20Analyst/")
        self.assertEqual(m.url_name, "user-role-remove")

    def test_status_resolves(self):
        m = resolve("/api/v1/auth/users/1/status/")
        self.assertEqual(m.url_name, "user-status")


# ---------------------------------------------------------------------------
# 2. AdminUserSerializer
# ---------------------------------------------------------------------------

class TestAdminUserSerializer(TestCase):
    def setUp(self):
        _ensure_groups()
        self.user = _make_user("sertest", email="s@test.com",
                               first_name="S", last_name="T")

    def test_expected_fields(self):
        from apps.accounts.serializers import AdminUserSerializer
        data = AdminUserSerializer(self.user).data
        expected = {"id", "username", "email", "first_name", "last_name",
                    "is_active", "is_staff", "date_joined", "last_login", "roles"}
        self.assertEqual(set(data.keys()), expected)

    def test_password_not_present(self):
        from apps.accounts.serializers import AdminUserSerializer
        data = AdminUserSerializer(self.user).data
        self.assertNotIn("password", data)

    def test_is_superuser_not_present(self):
        from apps.accounts.serializers import AdminUserSerializer
        data = AdminUserSerializer(self.user).data
        self.assertNotIn("is_superuser", data)

    def test_user_permissions_not_present(self):
        from apps.accounts.serializers import AdminUserSerializer
        data = AdminUserSerializer(self.user).data
        self.assertNotIn("user_permissions", data)

    def test_roles_empty_for_new_user(self):
        from apps.accounts.serializers import AdminUserSerializer
        data = AdminUserSerializer(self.user).data
        self.assertEqual(data["roles"], [])

    def test_roles_reflect_group_membership(self):
        from apps.accounts.serializers import AdminUserSerializer
        self.user.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        data = AdminUserSerializer(self.user).data
        self.assertIn(TRAFFIC_ANALYST, data["roles"])

    def test_all_fields_read_only(self):
        from apps.accounts.serializers import AdminUserSerializer
        s = AdminUserSerializer(self.user)
        for name, field in s.fields.items():
            with self.subTest(field=name):
                self.assertTrue(field.read_only,
                                f"Field '{name}' should be read-only")


# ---------------------------------------------------------------------------
# 3. User List — GET /api/v1/auth/users/
# ---------------------------------------------------------------------------

class TestUserListView(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("listadmin")
        self.regular = _make_user("listregular")
        self.superuser = _make_superuser("listsuper")
        self.url = "/api/v1/auth/users/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_returns_403(self):
        resp = _jwt(self.regular).get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_returns_200(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_returns_200(self):
        resp = _jwt(self.superuser).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_response_has_pagination_envelope(self):
        resp = _jwt(self.admin).get(self.url)
        body = resp.json()
        for key in ("count", "total_pages", "current_page", "next", "previous", "results"):
            with self.subTest(key=key):
                self.assertIn(key, body)

    def test_results_contain_user_fields(self):
        resp = _jwt(self.admin).get(self.url)
        results = resp.json()["results"]
        self.assertGreater(len(results), 0)
        first = results[0]
        for field in ("id", "username", "email", "is_active", "roles"):
            with self.subTest(field=field):
                self.assertIn(field, first)

    def test_password_not_in_results(self):
        resp = _jwt(self.admin).get(self.url)
        content = resp.content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)

    def test_roles_present_in_results(self):
        resp = _jwt(self.admin).get(self.url)
        results = resp.json()["results"]
        for user_data in results:
            self.assertIn("roles", user_data)

    def test_pagination_page_size_param(self):
        # Create extra users to ensure pagination triggers
        for i in range(5):
            _make_user(f"paguser{i}")
        resp = _jwt(self.admin).get(self.url + "?page_size=2")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertLessEqual(len(body["results"]), 2)
        self.assertGreater(body["count"], 2)

    def test_count_reflects_all_users(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertGreaterEqual(resp.json()["count"], 2)


# ---------------------------------------------------------------------------
# 4. User Detail — GET /api/v1/auth/users/{id}/
# ---------------------------------------------------------------------------

class TestUserDetailView(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("detailadmin")
        self.regular = _make_user("detailregular")
        self.target = _make_user("detailtarget", email="t@example.com",
                                 first_name="Target", last_name="User")
        self.url = f"/api/v1/auth/users/{self.target.pk}/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_returns_403(self):
        resp = _jwt(self.regular).get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_returns_200(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_returns_200(self):
        su = _make_superuser("detailsuper")
        resp = _jwt(su).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_nonexistent_user_returns_404(self):
        resp = _jwt(self.admin).get("/api/v1/auth/users/999999/")
        self.assertEqual(resp.status_code, 404)

    def test_correct_user_data_returned(self):
        resp = _jwt(self.admin).get(self.url)
        data = resp.json()["data"]
        self.assertEqual(data["id"], self.target.pk)
        self.assertEqual(data["username"], "detailtarget")
        self.assertEqual(data["email"], "t@example.com")

    def test_password_not_in_response(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertNotIn("password", resp.content.decode())

    def test_is_superuser_not_in_response(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertNotIn("is_superuser", resp.json()["data"])

    def test_response_has_success_envelope(self):
        resp = _jwt(self.admin).get(self.url)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)

    def test_roles_field_present(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertIn("roles", resp.json()["data"])


# ---------------------------------------------------------------------------
# 5. Role Assignment — POST /api/v1/auth/users/{id}/roles/
# ---------------------------------------------------------------------------

class TestUserRoleAssignView(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("roleassignadmin")
        self.regular = _make_user("roleassignregular")
        self.target = _make_user("roleassigntarget")
        self.url = f"/api/v1/auth/users/{self.target.pk}/roles/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_returns_403(self):
        resp = _jwt(self.regular).post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_assign_valid_role(self):
        resp = _jwt(self.admin).post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_assign_valid_role(self):
        su = _make_superuser("roleassignsuper")
        resp = _jwt(su).post(self.url, {"role": PUBLIC_USER}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_role_is_actually_assigned(self):
        _jwt(self.admin).post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        self.target.refresh_from_db()
        self.assertIn(TRAFFIC_ANALYST, self.target.get_roles())

    def test_invalid_role_returns_400(self):
        resp = _jwt(self.admin).post(self.url, {"role": "HackerRole"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_role_response_lists_valid_roles(self):
        resp = _jwt(self.admin).post(self.url, {"role": "NotARole"}, format="json")
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertIn("valid_roles", body.get("errors", {}))

    def test_missing_role_field_returns_400(self):
        resp = _jwt(self.admin).post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_empty_role_string_returns_400(self):
        resp = _jwt(self.admin).post(self.url, {"role": ""}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_self_assignment_returns_400(self):
        url = f"/api/v1/auth/users/{self.admin.pk}/roles/"
        resp = _jwt(self.admin).post(url, {"role": TRAFFIC_ANALYST}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_user_returns_404(self):
        resp = _jwt(self.admin).post("/api/v1/auth/users/999999/roles/",
                                     {"role": TRAFFIC_ANALYST}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_response_contains_updated_user(self):
        resp = _jwt(self.admin).post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        data = resp.json()["data"]
        self.assertIn("roles", data)
        self.assertIn(TRAFFIC_ANALYST, data["roles"])

    def test_arbitrary_group_name_rejected(self):
        # Ensure a group with this name exists but is NOT in ALL_ROLES
        Group.objects.get_or_create(name="ArbitraryGroup")
        resp = _jwt(self.admin).post(self.url, {"role": "ArbitraryGroup"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_password_not_in_response(self):
        resp = _jwt(self.admin).post(self.url, {"role": TRAFFIC_ANALYST}, format="json")
        self.assertNotIn("password", resp.content.decode())


# ---------------------------------------------------------------------------
# 6. Role Removal — DELETE /api/v1/auth/users/{id}/roles/{role}/
# ---------------------------------------------------------------------------

class TestUserRoleRemoveView(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("roleremoveadmin")
        self.regular = _make_user("roleremoveregular")
        self.target = _make_user("roleremovetarget")
        # Pre-assign role to target
        self.target.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        self.url = f"/api/v1/auth/users/{self.target.pk}/roles/Traffic%20Analyst/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().delete(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_returns_403(self):
        resp = _jwt(self.regular).delete(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_remove_role(self):
        resp = _jwt(self.admin).delete(self.url)
        self.assertEqual(resp.status_code, 204)

    def test_superuser_can_remove_role(self):
        su = _make_superuser("roleremovesuper")
        resp = _jwt(su).delete(self.url)
        self.assertEqual(resp.status_code, 204)

    def test_role_is_actually_removed(self):
        _jwt(self.admin).delete(self.url)
        self.target.refresh_from_db()
        self.assertNotIn(TRAFFIC_ANALYST, self.target.get_roles())

    def test_invalid_role_returns_400(self):
        url = f"/api/v1/auth/users/{self.target.pk}/roles/NotARole/"
        resp = _jwt(self.admin).delete(url)
        self.assertEqual(resp.status_code, 400)

    def test_self_removal_returns_400(self):
        # Give admin a role first
        self.admin.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        url = f"/api/v1/auth/users/{self.admin.pk}/roles/Traffic%20Analyst/"
        resp = _jwt(self.admin).delete(url)
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_user_returns_404(self):
        resp = _jwt(self.admin).delete(
            f"/api/v1/auth/users/999999/roles/Traffic%20Analyst/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_removing_unassigned_role_returns_204(self):
        # Removing a role the user doesn't have should still succeed (idempotent)
        url = f"/api/v1/auth/users/{self.target.pk}/roles/Public%20User/"
        resp = _jwt(self.admin).delete(url)
        self.assertEqual(resp.status_code, 204)


# ---------------------------------------------------------------------------
# 7. User Status — PATCH /api/v1/auth/users/{id}/status/
# ---------------------------------------------------------------------------

class TestUserStatusView(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("statusadmin")
        self.regular = _make_user("statusregular")
        self.target = _make_user("statustargetu")
        self.url = f"/api/v1/auth/users/{self.target.pk}/status/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().patch(self.url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_returns_403(self):
        resp = _jwt(self.regular).patch(self.url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_deactivate(self):
        resp = _jwt(self.admin).patch(self.url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_reactivate(self):
        self.target.is_active = False
        self.target.save()
        resp = _jwt(self.admin).patch(self.url, {"is_active": True}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_deactivate(self):
        su = _make_superuser("statussuper")
        resp = _jwt(su).patch(self.url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_target_is_actually_deactivated(self):
        _jwt(self.admin).patch(self.url, {"is_active": False}, format="json")
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_target_is_actually_reactivated(self):
        self.target.is_active = False
        self.target.save()
        _jwt(self.admin).patch(self.url, {"is_active": True}, format="json")
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_self_deactivation_returns_400(self):
        url = f"/api/v1/auth/users/{self.admin.pk}/status/"
        resp = _jwt(self.admin).patch(url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_self_activation_returns_400(self):
        url = f"/api/v1/auth/users/{self.admin.pk}/status/"
        resp = _jwt(self.admin).patch(url, {"is_active": True}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_missing_is_active_returns_400(self):
        resp = _jwt(self.admin).patch(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_non_boolean_is_active_returns_400(self):
        resp = _jwt(self.admin).patch(self.url, {"is_active": "yes"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_user_returns_404(self):
        resp = _jwt(self.admin).patch(
            "/api/v1/auth/users/999999/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 404)

    def test_response_contains_updated_user(self):
        resp = _jwt(self.admin).patch(self.url, {"is_active": False}, format="json")
        data = resp.json()["data"]
        self.assertFalse(data["is_active"])
        self.assertEqual(data["username"], "statustargetu")

    def test_password_not_in_response(self):
        resp = _jwt(self.admin).patch(self.url, {"is_active": False}, format="json")
        self.assertNotIn("password", resp.content.decode())

    def test_get_not_allowed(self):
        resp = _jwt(self.admin).get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_put_not_allowed(self):
        resp = _jwt(self.admin).put(self.url, {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 405)


# ---------------------------------------------------------------------------
# 8. Superuser implicit access
# ---------------------------------------------------------------------------

class TestSuperuserImplicitAccess(TestCase):
    """
    Superusers must access all admin endpoints even without explicit
    System Administrator group membership.
    """
    def setUp(self):
        _ensure_groups()
        self.su = _make_superuser("implicitsu")
        self.target = _make_user("implicittarget")

    def test_superuser_can_list_users(self):
        resp = _jwt(self.su).get("/api/v1/auth/users/")
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_get_user_detail(self):
        resp = _jwt(self.su).get(f"/api/v1/auth/users/{self.target.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_assign_role(self):
        resp = _jwt(self.su).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_remove_role(self):
        self.target.groups.add(Group.objects.get(name=TRAFFIC_ANALYST))
        resp = _jwt(self.su).delete(
            f"/api/v1/auth/users/{self.target.pk}/roles/Traffic%20Analyst/"
        )
        self.assertEqual(resp.status_code, 204)

    def test_superuser_can_deactivate_user(self):
        resp = _jwt(self.su).patch(
            f"/api/v1/auth/users/{self.target.pk}/status/",
            {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_superuser_self_modification_still_blocked(self):
        """Service-layer self-modification guard applies to superusers too."""
        resp = _jwt(self.su).post(
            f"/api/v1/auth/users/{self.su.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_superuser_not_in_system_admin_group_still_gets_access(self):
        """Verify superuser has no System Admin group but still passes."""
        self.assertFalse(
            self.su.groups.filter(name=SYSTEM_ADMIN).exists(),
            "Test superuser must NOT be in System Admin group for this test to be valid"
        )
        resp = _jwt(self.su).get("/api/v1/auth/users/")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 9. Security: password never exposed across all admin endpoints
# ---------------------------------------------------------------------------

class TestPasswordNeverExposed(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("secadmin")
        self.target = _make_user("sectarget")

    def _assert_no_password(self, resp):
        content = resp.content.decode()
        self.assertNotIn("password", content)
        self.assertNotIn("pbkdf2", content)
        self.assertNotIn("argon2", content)
        self.assertNotIn("bcrypt", content)

    def test_list_no_password(self):
        self._assert_no_password(_jwt(self.admin).get("/api/v1/auth/users/"))

    def test_detail_no_password(self):
        self._assert_no_password(
            _jwt(self.admin).get(f"/api/v1/auth/users/{self.target.pk}/")
        )

    def test_role_assign_no_password(self):
        resp = _jwt(self.admin).post(
            f"/api/v1/auth/users/{self.target.pk}/roles/",
            {"role": TRAFFIC_ANALYST}, format="json"
        )
        self._assert_no_password(resp)

    def test_status_no_password(self):
        resp = _jwt(self.admin).patch(
            f"/api/v1/auth/users/{self.target.pk}/status/",
            {"is_active": False}, format="json"
        )
        self._assert_no_password(resp)


# ---------------------------------------------------------------------------
# 10. Regression
# ---------------------------------------------------------------------------

class TestPhase3CRegression(TestCase):
    def setUp(self):
        _ensure_groups()
        self.admin = _make_admin("regadmin")

    def test_health_endpoint_still_200(self):
        resp = APIClient().get("/api/v1/health/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "traffic-management-backend")

    def test_old_health_url_still_404(self):
        resp = APIClient().get("/api/health/")
        self.assertEqual(resp.status_code, 404)

    def test_double_prefix_health_still_404(self):
        resp = APIClient().get("/api/v1/v1/health/")
        self.assertEqual(resp.status_code, 404)

    def test_me_endpoint_still_works(self):
        resp = _jwt(self.admin).get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["username"], "regadmin")

    def test_me_endpoint_unauthenticated_still_401(self):
        resp = APIClient().get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 401)

    def test_url_routing_me(self):
        self.assertEqual(reverse("accounts:me"), "/api/v1/auth/me/")

    def test_url_routing_user_list(self):
        self.assertEqual(reverse("accounts:user-list"), "/api/v1/auth/users/")

    def test_django_check_passes(self):
        """Ensure no system check errors exist after Phase 3C changes."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("check", stdout=out, stderr=out)
        self.assertIn("no issues", out.getvalue().lower())

    def test_no_pending_migrations(self):
        """No unmigrated schema changes should exist."""
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending migrations: {plan}")
