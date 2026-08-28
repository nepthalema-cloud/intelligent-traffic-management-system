# Tests for Phase 4D.2: TrafficViolation, ViolationEvidence, Citation
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.roles import ALL_ROLES
from apps.audit.models import AuditEvent
from apps.audit.services import AuditAction
from apps.violations.models import Citation, TrafficViolation, Vehicle, ViolationEvidence
from apps.violations.services import (
    CitationService,
    EvidenceService,
    InvalidCitationTransitionError,
    ViolationService,
)

User = get_user_model()
BASE = "/api/v1/violations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _groups():
    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)


def _user(username, role=None, password="Pass123!"):
    _groups()
    u = User.objects.create_user(username=username, password=password)
    if role:
        u.groups.add(Group.objects.get(name=role))
    return u


def _jwt(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(user))}")
    return c


def _vehicle(**kw):
    kw.setdefault("plate_number", "TEST-001")
    kw.setdefault("vehicle_type", "car")
    return Vehicle.objects.create(**kw)


def _violation(vehicle=None, **kw):
    v = vehicle or _vehicle()
    kw.setdefault("violation_type", "speeding")
    kw.setdefault("occurred_at", timezone.now())
    return TrafficViolation.objects.create(vehicle=v, **kw)


def _citation(violation=None, issued_by=None, **kw):
    v = violation or _violation()
    kw.setdefault("issued_at", timezone.now())
    kw.setdefault("state", Citation.State.ISSUED)
    return Citation.objects.create(violation=v, issued_by=issued_by, **kw)


# ===========================================================================
# Model tests
# ===========================================================================

class TestTrafficViolationModel(TestCase):
    def test_create_minimal(self):
        v = _violation()
        self.assertIsNotNone(v.pk)
        self.assertTrue(v.is_active)
        self.assertIsNotNone(v.created_at)

    def test_all_violation_types(self):
        vehicle = _vehicle(plate_number="VT-001")
        for i, (choice, _) in enumerate(TrafficViolation.ViolationType.choices):
            tv = TrafficViolation.objects.create(
                vehicle=vehicle, violation_type=choice,
                occurred_at=timezone.now(),
            )
            self.assertEqual(tv.violation_type, choice)

    def test_append_only_save_blocked(self):
        tv = _violation()
        tv.description = "modified"
        with self.assertRaises(RuntimeError):
            tv.save()

    def test_append_only_delete_blocked(self):
        tv = _violation()
        with self.assertRaises(RuntimeError):
            tv.delete()

    def test_ordering_newest_first(self):
        v1 = _violation(occurred_at=timezone.now())
        v2 = _violation(occurred_at=timezone.now())
        pks = list(TrafficViolation.objects.values_list("pk", flat=True)[:2])
        self.assertEqual(pks[0], v2.pk)

    def test_str_representation(self):
        tv = _violation()
        self.assertIn(tv.violation_type, str(tv))


class TestViolationEvidenceModel(TestCase):
    def test_create(self):
        tv = _violation()
        e = ViolationEvidence.objects.create(
            violation=tv,
            evidence_type="image",
            evidence_url="https://storage.example.com/evidence/001.jpg",
        )
        self.assertIsNotNone(e.pk)
        self.assertEqual(e.evidence_type, "image")

    def test_append_only_save_blocked(self):
        tv = _violation()
        e = ViolationEvidence.objects.create(
            violation=tv, evidence_type="image",
            evidence_url="https://s3.example.com/img.jpg",
        )
        e.description = "changed"
        with self.assertRaises(RuntimeError):
            e.save()

    def test_append_only_delete_blocked(self):
        tv = _violation()
        e = ViolationEvidence.objects.create(
            violation=tv, evidence_type="video",
            evidence_url="https://s3.example.com/vid.mp4",
        )
        with self.assertRaises(RuntimeError):
            e.delete()

    def test_all_evidence_types(self):
        tv = _violation()
        for choice, _ in ViolationEvidence.EvidenceType.choices:
            e = ViolationEvidence.objects.create(
                violation=tv, evidence_type=choice,
                evidence_url=f"https://s3.example.com/{choice}.bin",
            )
            self.assertEqual(e.evidence_type, choice)


class TestCitationModel(TestCase):
    def test_create_default_state(self):
        c = _citation()
        self.assertEqual(c.state, Citation.State.ISSUED)
        self.assertIsNotNone(c.pk)

    def test_valid_transitions_issued(self):
        allowed = Citation.VALID_TRANSITIONS[Citation.State.ISSUED]
        self.assertIn(Citation.State.CONTESTED, allowed)
        self.assertIn(Citation.State.ADJUDICATED, allowed)

    def test_valid_transitions_contested(self):
        allowed = Citation.VALID_TRANSITIONS[Citation.State.CONTESTED]
        self.assertEqual(allowed, [Citation.State.ADJUDICATED])

    def test_valid_transitions_adjudicated_terminal(self):
        allowed = Citation.VALID_TRANSITIONS[Citation.State.ADJUDICATED]
        self.assertEqual(allowed, [])

    def test_one_citation_per_violation(self):
        tv = _violation()
        _citation(violation=tv)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Citation.objects.create(
                violation=tv,
                issued_at=timezone.now(),
                state=Citation.State.ISSUED,
            )

    def test_str_representation(self):
        c = _citation()
        self.assertIn("issued", str(c))


# ===========================================================================
# Service tests
# ===========================================================================

class TestViolationService(TestCase):
    def setUp(self):
        _groups()
        self.actor = _user("svc_law", "Law Enforcement / Authorized Officer")
        self.vehicle = _vehicle(plate_number="SVC-001")

    def test_create_records_violation(self):
        tv = ViolationService.create(
            actor=self.actor,
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=self.vehicle,
        )
        self.assertIsNotNone(tv.pk)
        self.assertEqual(tv.violation_type, "speeding")

    def test_create_emits_audit(self):
        before = AuditEvent.objects.count()
        ViolationService.create(
            actor=self.actor,
            violation_type="red_light",
            occurred_at=timezone.now(),
            vehicle=self.vehicle,
        )
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.action, AuditAction.VIOLATION_CREATED)
        self.assertEqual(ev.actor_username, self.actor.username)

    def test_create_audit_no_plate_number(self):
        ViolationService.create(
            actor=self.actor,
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=self.vehicle,
        )
        ev = AuditEvent.objects.filter(action=AuditAction.VIOLATION_CREATED).latest("timestamp")
        self.assertNotIn("plate_number", str(ev.detail or ""))
        self.assertNotIn(self.vehicle.plate_number, str(ev.detail or ""))

    def test_deactivate(self):
        tv = ViolationService.create(
            actor=self.actor,
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=self.vehicle,
        )
        tv = ViolationService.deactivate(actor=self.actor, violation=tv)
        self.assertFalse(tv.is_active)

    def test_deactivate_emits_audit(self):
        tv = ViolationService.create(
            actor=self.actor, violation_type="speeding",
            occurred_at=timezone.now(), vehicle=self.vehicle,
        )
        before = AuditEvent.objects.count()
        ViolationService.deactivate(actor=self.actor, violation=tv)
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.action, AuditAction.VIOLATION_DEACTIVATED)


class TestCitationService(TestCase):
    def setUp(self):
        _groups()
        self.actor = _user("cit_law", "Law Enforcement / Authorized Officer")
        self.vehicle = _vehicle(plate_number="CIT-001")
        self.violation = ViolationService.create(
            actor=self.actor, violation_type="speeding",
            occurred_at=timezone.now(), vehicle=self.vehicle,
        )

    def test_issue_creates_citation(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation,
            issued_at=timezone.now(), issued_by=self.actor,
        )
        self.assertEqual(c.state, Citation.State.ISSUED)
        self.assertEqual(c.violation_id, self.violation.pk)

    def test_issue_emits_audit(self):
        before = AuditEvent.objects.count()
        CitationService.issue(
            actor=self.actor, violation=self.violation,
            issued_at=timezone.now(),
        )
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        ev = AuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.action, AuditAction.CITATION_ISSUED)

    def test_issue_duplicate_raises(self):
        CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        from apps.violations.services import CitationServiceError
        with self.assertRaises(CitationServiceError):
            CitationService.issue(
                actor=self.actor, violation=self.violation, issued_at=timezone.now(),
            )

    def test_transition_issued_to_contested(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        c = CitationService.transition(
            actor=self.actor, citation=c, new_state=Citation.State.CONTESTED,
        )
        self.assertEqual(c.state, Citation.State.CONTESTED)

    def test_transition_contested_to_adjudicated(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        c = CitationService.transition(actor=self.actor, citation=c,
                                       new_state=Citation.State.CONTESTED)
        c = CitationService.transition(actor=self.actor, citation=c,
                                       new_state=Citation.State.ADJUDICATED)
        self.assertEqual(c.state, Citation.State.ADJUDICATED)

    def test_transition_issued_directly_to_adjudicated(self):
        """issued → adjudicated shortcut must be valid."""
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        c = CitationService.transition(actor=self.actor, citation=c,
                                       new_state=Citation.State.ADJUDICATED)
        self.assertEqual(c.state, Citation.State.ADJUDICATED)

    def test_transition_from_terminal_raises(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        CitationService.transition(actor=self.actor, citation=c,
                                   new_state=Citation.State.ADJUDICATED)
        c.refresh_from_db()
        with self.assertRaises(InvalidCitationTransitionError):
            CitationService.transition(actor=self.actor, citation=c,
                                       new_state=Citation.State.CONTESTED)

    def test_transition_invalid_raises(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        CitationService.transition(actor=self.actor, citation=c,
                                   new_state=Citation.State.CONTESTED)
        c.refresh_from_db()
        with self.assertRaises(InvalidCitationTransitionError):
            CitationService.transition(actor=self.actor, citation=c,
                                       new_state=Citation.State.ISSUED)  # backwards

    def test_transition_emits_correct_audit(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        CitationService.transition(actor=self.actor, citation=c,
                                   new_state=Citation.State.CONTESTED)
        ev = AuditEvent.objects.filter(action=AuditAction.CITATION_CONTESTED).latest("timestamp")
        self.assertEqual(ev.actor_username, self.actor.username)

    def test_notes_updated_on_transition(self):
        c = CitationService.issue(
            actor=self.actor, violation=self.violation, issued_at=timezone.now(),
        )
        c = CitationService.transition(
            actor=self.actor, citation=c,
            new_state=Citation.State.CONTESTED,
            notes="Appealed by driver.",
        )
        self.assertEqual(c.notes, "Appealed by driver.")


# ===========================================================================
# API / RBAC tests
# ===========================================================================

class TestViolationAPIAuth(TestCase):
    def setUp(self):
        self.vehicle = _vehicle()
        self.violation = _violation(vehicle=self.vehicle)

    def test_list_unauthenticated_401(self):
        self.assertEqual(APIClient().get(f"{BASE}/").status_code, 401)

    def test_detail_unauthenticated_401(self):
        self.assertEqual(
            APIClient().get(f"{BASE}/{self.violation.pk}/").status_code, 401
        )

    def test_create_unauthenticated_401(self):
        self.assertEqual(APIClient().post(f"{BASE}/").status_code, 401)


class TestViolationRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("vrbac_admin",   "System Administrator")
        self.law     = _user("vrbac_law",     "Law Enforcement / Authorized Officer")
        self.analyst = _user("vrbac_analyst", "Traffic Analyst")
        self.pay     = _user("vrbac_pay",     "Payment/Fines Officer")
        self.tco     = _user("vrbac_tco",     "Traffic Control Officer")
        self.vehicle = _vehicle(plate_number="RBAC-001")
        self.violation = _violation(vehicle=self.vehicle)

    def _post_violation(self, client, plate="POST-RBAC"):
        v = _vehicle(plate_number=plate)
        return client.post(f"{BASE}/", {
            "violation_type": "speeding",
            "occurred_at": timezone.now().isoformat(),
            "vehicle": v.pk,
        }, format="json")

    # List access
    def test_admin_can_list(self):
        self.assertEqual(_jwt(self.admin).get(f"{BASE}/").status_code, 200)

    def test_law_can_list(self):
        self.assertEqual(_jwt(self.law).get(f"{BASE}/").status_code, 200)

    def test_analyst_can_list(self):
        self.assertEqual(_jwt(self.analyst).get(f"{BASE}/").status_code, 200)

    def test_pay_can_list(self):
        self.assertEqual(_jwt(self.pay).get(f"{BASE}/").status_code, 200)

    def test_tco_cannot_list(self):
        self.assertEqual(_jwt(self.tco).get(f"{BASE}/").status_code, 403)

    # Create access
    def test_admin_can_create(self):
        self.assertEqual(self._post_violation(_jwt(self.admin), "ADMIN-NEW").status_code, 201)

    def test_law_can_create(self):
        self.assertEqual(self._post_violation(_jwt(self.law), "LAW-NEW").status_code, 201)

    def test_analyst_cannot_create(self):
        self.assertEqual(self._post_violation(_jwt(self.analyst), "ANALYST-NEW").status_code, 403)

    def test_pay_cannot_create(self):
        self.assertEqual(self._post_violation(_jwt(self.pay), "PAY-NEW").status_code, 403)

    # Detail access
    def test_admin_can_read_detail(self):
        self.assertEqual(
            _jwt(self.admin).get(f"{BASE}/{self.violation.pk}/").status_code, 200
        )

    def test_analyst_can_read_detail(self):
        self.assertEqual(
            _jwt(self.analyst).get(f"{BASE}/{self.violation.pk}/").status_code, 200
        )

    def test_tco_cannot_read_detail(self):
        self.assertEqual(
            _jwt(self.tco).get(f"{BASE}/{self.violation.pk}/").status_code, 403
        )

    # Status (deactivate) — Admin only
    def test_admin_can_deactivate(self):
        resp = _jwt(self.admin).patch(
            f"{BASE}/{self.violation.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_law_cannot_deactivate(self):
        resp = _jwt(self.law).patch(
            f"{BASE}/{self.violation.pk}/status/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


class TestEvidenceRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("evid_admin", "System Administrator")
        self.law     = _user("evid_law",   "Law Enforcement / Authorized Officer")
        self.analyst = _user("evid_ana",   "Traffic Analyst")
        self.pay     = _user("evid_pay",   "Payment/Fines Officer")
        self.violation = _violation()

    def _post_evidence(self, client):
        return client.post(f"{BASE}/{self.violation.pk}/evidence/", {
            "evidence_type": "image",
            "evidence_url": "https://s3.example.com/evidence.jpg",
        }, format="json")

    def test_admin_can_list_evidence(self):
        self.assertEqual(
            _jwt(self.admin).get(f"{BASE}/{self.violation.pk}/evidence/").status_code, 200
        )

    def test_law_can_list_evidence(self):
        self.assertEqual(
            _jwt(self.law).get(f"{BASE}/{self.violation.pk}/evidence/").status_code, 200
        )

    def test_analyst_cannot_list_evidence(self):
        self.assertEqual(
            _jwt(self.analyst).get(f"{BASE}/{self.violation.pk}/evidence/").status_code, 403
        )

    def test_pay_cannot_list_evidence(self):
        self.assertEqual(
            _jwt(self.pay).get(f"{BASE}/{self.violation.pk}/evidence/").status_code, 403
        )

    def test_admin_can_attach_evidence(self):
        self.assertEqual(self._post_evidence(_jwt(self.admin)).status_code, 201)

    def test_law_can_attach_evidence(self):
        self.assertEqual(self._post_evidence(_jwt(self.law)).status_code, 201)

    def test_analyst_cannot_attach_evidence(self):
        self.assertEqual(self._post_evidence(_jwt(self.analyst)).status_code, 403)


class TestCitationRBAC(TestCase):
    def setUp(self):
        _groups()
        self.admin   = _user("crbac_admin", "System Administrator")
        self.law     = _user("crbac_law",   "Law Enforcement / Authorized Officer")
        self.pay     = _user("crbac_pay",   "Payment/Fines Officer")
        self.analyst = _user("crbac_ana",   "Traffic Analyst")
        self.tco     = _user("crbac_tco",   "Traffic Control Officer")

    def _violation_for(self, label):
        return _violation(vehicle=_vehicle(plate_number=label))

    def _post_citation(self, client, violation):
        return client.post(f"{BASE}/citations/", {
            "violation": violation.pk,
            "issued_at": timezone.now().isoformat(),
        }, format="json")

    def test_admin_can_list_citations(self):
        self.assertEqual(_jwt(self.admin).get(f"{BASE}/citations/").status_code, 200)

    def test_law_can_list_citations(self):
        self.assertEqual(_jwt(self.law).get(f"{BASE}/citations/").status_code, 200)

    def test_pay_can_list_citations(self):
        self.assertEqual(_jwt(self.pay).get(f"{BASE}/citations/").status_code, 200)

    def test_analyst_cannot_list_citations(self):
        self.assertEqual(_jwt(self.analyst).get(f"{BASE}/citations/").status_code, 403)

    def test_tco_cannot_list_citations(self):
        self.assertEqual(_jwt(self.tco).get(f"{BASE}/citations/").status_code, 403)

    def test_admin_can_issue_citation(self):
        v = self._violation_for("CIT-ADMIN")
        self.assertEqual(self._post_citation(_jwt(self.admin), v).status_code, 201)

    def test_law_can_issue_citation(self):
        v = self._violation_for("CIT-LAW")
        self.assertEqual(self._post_citation(_jwt(self.law), v).status_code, 201)

    def test_pay_cannot_issue_citation(self):
        v = self._violation_for("CIT-PAY")
        self.assertEqual(self._post_citation(_jwt(self.pay), v).status_code, 403)

    def test_duplicate_citation_400(self):
        v = self._violation_for("CIT-DUP")
        self._post_citation(_jwt(self.admin), v)
        resp = self._post_citation(_jwt(self.admin), v)
        self.assertEqual(resp.status_code, 400)


class TestCitationLifecycleAPI(TestCase):
    """API-level lifecycle transition tests."""

    def setUp(self):
        _groups()
        self.admin = _user("clife_admin", "System Administrator")
        self.law   = _user("clife_law",   "Law Enforcement / Authorized Officer")
        self.violation = _violation(vehicle=_vehicle(plate_number="LIFE-001"))
        # Issue a citation
        resp = _jwt(self.admin).post(f"{BASE}/citations/", {
            "violation": self.violation.pk,
            "issued_at": timezone.now().isoformat(),
        }, format="json")
        self.citation_id = resp.json()["data"]["id"]

    def test_contest_citation(self):
        resp = _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "contested"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["state"], "contested")

    def test_adjudicate_from_contested(self):
        _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "contested"}, format="json"
        )
        resp = _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "adjudicated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["state"], "adjudicated")

    def test_direct_adjudicate_from_issued(self):
        v2 = _violation(vehicle=_vehicle(plate_number="LIFE-002"))
        resp = _jwt(self.admin).post(f"{BASE}/citations/", {
            "violation": v2.pk, "issued_at": timezone.now().isoformat(),
        }, format="json")
        cid = resp.json()["data"]["id"]
        resp = _jwt(self.admin).patch(
            f"{BASE}/citations/{cid}/state/",
            {"state": "adjudicated"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["state"], "adjudicated")

    def test_invalid_transition_returns_400(self):
        # Try to go from issued to issued (nonsensical)
        resp = _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "issued"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_transition_from_terminal_returns_400(self):
        _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "adjudicated"}, format="json"
        )
        resp = _jwt(self.admin).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "contested"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_pay_cannot_transition(self):
        pay = _user("clife_pay", "Payment/Fines Officer")
        resp = _jwt(pay).patch(
            f"{BASE}/citations/{self.citation_id}/state/",
            {"state": "contested"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


class TestViolationPII(TestCase):
    """Verify plate_number is not exposed via violation API responses."""

    def setUp(self):
        _groups()
        self.admin = _user("pii_admin", "System Administrator")
        self.vehicle = _vehicle(plate_number="PII-PLATE-001")
        self.violation = _violation(vehicle=self.vehicle)

    def test_violation_response_omits_plate_number(self):
        resp = _jwt(self.admin).get(f"{BASE}/{self.violation.pk}/")
        self.assertEqual(resp.status_code, 200)
        body = str(resp.json())
        self.assertNotIn("PII-PLATE-001", body)
        # vehicle FK id IS present
        self.assertIn(str(self.vehicle.pk), body)

    def test_violation_list_omits_plate_number(self):
        resp = _jwt(self.admin).get(f"{BASE}/")
        body = str(resp.json())
        self.assertNotIn("PII-PLATE-001", body)

    def test_audit_detail_omits_plate_number(self):
        _user2 = _user("pii_law2", "Law Enforcement / Authorized Officer")
        v2 = _vehicle(plate_number="PII-PLATE-002")
        _jwt(_user2).post(f"{BASE}/", {
            "violation_type": "speeding",
            "occurred_at": timezone.now().isoformat(),
            "vehicle": v2.pk,
        }, format="json")
        for ev in AuditEvent.objects.filter(action=AuditAction.VIOLATION_CREATED):
            self.assertNotIn("PII-PLATE-002", str(ev.detail or ""))
            self.assertNotIn("plate_number", str(ev.detail or ""))


class TestViolationCRUD(TestCase):
    """CRUD + append-only enforcement via API."""

    def setUp(self):
        _groups()
        self.admin = _user("crud_admin", "System Administrator")
        self.vehicle = _vehicle(plate_number="CRUD-001")

    def test_create_201(self):
        resp = _jwt(self.admin).post(f"{BASE}/", {
            "violation_type": "red_light",
            "occurred_at": timezone.now().isoformat(),
            "vehicle": self.vehicle.pk,
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_list_200_with_pagination(self):
        _violation(vehicle=self.vehicle)
        resp = _jwt(self.admin).get(f"{BASE}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.json())
        self.assertIn("results", resp.json())

    def test_detail_200(self):
        tv = _violation(vehicle=self.vehicle)
        resp = _jwt(self.admin).get(f"{BASE}/{tv.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], tv.pk)

    def test_no_patch_on_violation(self):
        """Violations are append-only — PATCH is not routed."""
        tv = _violation(vehicle=self.vehicle)
        self.assertEqual(
            _jwt(self.admin).patch(f"{BASE}/{tv.pk}/", {}, format="json").status_code,
            405,
        )

    def test_no_delete_on_violation(self):
        tv = _violation(vehicle=self.vehicle)
        self.assertEqual(
            _jwt(self.admin).delete(f"{BASE}/{tv.pk}/").status_code, 405
        )

    def test_nonexistent_404(self):
        self.assertEqual(
            _jwt(self.admin).get(f"{BASE}/999999/").status_code, 404
        )

    def test_violation_type_filter(self):
        _violation(vehicle=self.vehicle, violation_type="speeding")
        _violation(vehicle=_vehicle(plate_number="FLT-002"), violation_type="red_light")
        resp = _jwt(self.admin).get(f"{BASE}/?violation_type=speeding")
        for r in resp.json()["results"]:
            self.assertEqual(r["violation_type"], "speeding")


class TestEvidenceCRUD(TestCase):
    def setUp(self):
        _groups()
        self.admin = _user("evcrud_admin", "System Administrator")
        self.violation = _violation()

    def test_attach_evidence_201(self):
        resp = _jwt(self.admin).post(f"{BASE}/{self.violation.pk}/evidence/", {
            "evidence_type": "image",
            "evidence_url": "https://s3.example.com/img.jpg",
            "description": "Speed camera frame",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["evidence_type"], "image")

    def test_list_evidence_200(self):
        ViolationEvidence.objects.create(
            violation=self.violation,
            evidence_type="video",
            evidence_url="https://s3.example.com/vid.mp4",
        )
        resp = _jwt(self.admin).get(f"{BASE}/{self.violation.pk}/evidence/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_blank_url_400(self):
        resp = _jwt(self.admin).post(f"{BASE}/{self.violation.pk}/evidence/", {
            "evidence_type": "image",
            "evidence_url": "   ",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_evidence_for_missing_violation_404(self):
        self.assertEqual(
            _jwt(self.admin).get(f"{BASE}/999999/evidence/").status_code, 404
        )


class TestViolationRegression(TestCase):
    """Regression: existing endpoints still work after 4D.2 changes."""

    def setUp(self):
        _groups()
        self.admin = _user("reg_admin", "System Administrator")

    def test_health_still_200(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)

    def test_vehicles_still_accessible(self):
        self.assertEqual(
            _jwt(self.admin).get("/api/v1/violations/vehicles/").status_code, 200
        )

    def test_incidents_still_accessible(self):
        self.assertEqual(
            _jwt(self.admin).get("/api/v1/traffic/incidents/").status_code, 200
        )

    def test_no_pending_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(plan, [], f"Pending migrations: {plan}")
