"""
Service layer for the violations app.

VehicleService    — Phase 4D.1 (unchanged)
ViolationService  — Phase 4D.2: create TrafficViolation records (append-only)
EvidenceService   — Phase 4D.2: attach ViolationEvidence to a violation (append-only)
CitationService   — Phase 4D.2: issue a Citation and manage its lifecycle

PII policy
----------
``plate_number`` is NOT included in audit ``detail`` fields.
Only non-sensitive identifiers (vehicle_id, violation_id, etc.) are logged.

Append-only enforcement
-----------------------
TrafficViolation and ViolationEvidence have no update/delete service methods.
The model-level save()/delete() overrides provide a second line of defence.

Lifecycle validation
--------------------
CitationService.transition() validates state changes against
Citation.VALID_TRANSITIONS before persisting.

Dependency direction
--------------------
violations.services → audit.services   (correct)
violations.services → roads, cameras   (read-only FK lookups, acceptable)
audit.services      → violations        (forbidden)
"""

from apps.audit.services import AuditAction, Outcome, log_audit_event
from apps.violations.models import Citation, TrafficViolation, Vehicle, ViolationEvidence


# ---------------------------------------------------------------------------
# Shared exceptions
# ---------------------------------------------------------------------------

class ViolationServiceError(Exception):
    """Base exception for ViolationService errors."""


class CitationServiceError(Exception):
    """Base exception for CitationService errors."""


class InvalidCitationTransitionError(CitationServiceError):
    """Raised when a requested state transition is not permitted."""


# ---------------------------------------------------------------------------
# VehicleService  (Phase 4D.1 — unchanged)
# ---------------------------------------------------------------------------

class VehicleService:
    """Encapsulates all create/update/deactivate operations for Vehicle records."""

    @staticmethod
    def create(
        actor,
        plate_number: str,
        vehicle_type: str = "other",
        registration_country: str = "",
        color: str = "",
        make: str = "",
        model: str = "",
        year: int | None = None,
        request=None,
    ) -> Vehicle:
        vehicle = Vehicle.objects.create(
            plate_number=plate_number,
            vehicle_type=vehicle_type,
            registration_country=registration_country,
            color=color,
            make=make,
            model=model,
            year=year,
        )
        # PII: plate_number intentionally excluded from audit detail
        log_audit_event(
            action=AuditAction.VEHICLE_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=vehicle,
            detail={"vehicle_id": vehicle.pk, "vehicle_type": vehicle_type},
        )
        return vehicle

    @staticmethod
    def update(actor, vehicle: Vehicle, request=None, **fields) -> Vehicle:
        for attr, value in fields.items():
            setattr(vehicle, attr, value)
        vehicle.save()
        safe_fields = [f for f in fields.keys() if f != "plate_number"]
        log_audit_event(
            action=AuditAction.VEHICLE_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=vehicle,
            detail={
                "vehicle_id": vehicle.pk,
                "fields_changed": safe_fields,
                "plate_number_changed": "plate_number" in fields,
            },
        )
        return vehicle

    @staticmethod
    def set_active(actor, vehicle: Vehicle, is_active: bool, request=None) -> Vehicle:
        vehicle.is_active = is_active
        vehicle.save(update_fields=["is_active", "updated_at"])
        action = (
            AuditAction.VEHICLE_ACTIVATED if is_active
            else AuditAction.VEHICLE_DEACTIVATED
        )
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=vehicle,
            detail={"vehicle_id": vehicle.pk, "is_active": is_active},
        )
        return vehicle


# ---------------------------------------------------------------------------
# ViolationService  (Phase 4D.2)
# ---------------------------------------------------------------------------

class ViolationService:
    """
    Create and administratively deactivate TrafficViolation records.

    No update method — violations are append-only legal records.
    """

    @staticmethod
    def create(
        actor,
        violation_type: str,
        occurred_at,
        vehicle: Vehicle,
        description: str = "",
        segment=None,
        intersection=None,
        camera=None,
        reported_by=None,
        request=None,
    ) -> TrafficViolation:
        violation = TrafficViolation.objects.create(
            violation_type=violation_type,
            description=description,
            occurred_at=occurred_at,
            vehicle=vehicle,
            segment=segment,
            intersection=intersection,
            camera=camera,
            reported_by=reported_by,
        )
        # PII: vehicle plate_number NOT in audit detail
        log_audit_event(
            action=AuditAction.VIOLATION_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=violation,
            detail={
                "violation_id":   violation.pk,
                "violation_type": violation_type,
                "vehicle_id":     vehicle.pk,
            },
        )
        return violation

    @staticmethod
    def deactivate(actor, violation: TrafficViolation, request=None) -> TrafficViolation:
        """
        Administratively deactivate a violation record.

        Does not delete; legal records are preserved.  Only sets is_active=False
        via a direct QuerySet update to bypass the model's append-only save().
        """
        TrafficViolation.objects.filter(pk=violation.pk).update(is_active=False)
        violation.refresh_from_db()
        log_audit_event(
            action=AuditAction.VIOLATION_DEACTIVATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=violation,
            detail={"violation_id": violation.pk},
        )
        return violation


# ---------------------------------------------------------------------------
# EvidenceService  (Phase 4D.2)
# ---------------------------------------------------------------------------

class EvidenceService:
    """Attach ViolationEvidence records to a TrafficViolation. Append-only."""

    @staticmethod
    def create(
        actor,
        violation: TrafficViolation,
        evidence_type: str,
        evidence_url: str,
        description: str = "",
        request=None,
    ) -> ViolationEvidence:
        evidence = ViolationEvidence.objects.create(
            violation=violation,
            evidence_type=evidence_type,
            evidence_url=evidence_url,
            description=description,
        )
        log_audit_event(
            action=AuditAction.EVIDENCE_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=evidence,
            detail={
                "evidence_id":  evidence.pk,
                "violation_id": violation.pk,
                "evidence_type": evidence_type,
                # evidence_url omitted — may contain storage keys/tokens
            },
        )
        return evidence


# ---------------------------------------------------------------------------
# CitationService  (Phase 4D.2)
# ---------------------------------------------------------------------------

class CitationService:
    """Issue Citations and manage their lifecycle transitions."""

    @staticmethod
    def issue(
        actor,
        violation: TrafficViolation,
        issued_at,
        issued_by=None,
        notes: str = "",
        request=None,
    ) -> Citation:
        """Create a Citation in the 'issued' state for a given violation."""
        if hasattr(violation, "citation"):
            raise CitationServiceError(
                f"Violation #{violation.pk} already has a citation."
            )
        citation = Citation.objects.create(
            violation=violation,
            issued_by=issued_by,
            issued_at=issued_at,
            state=Citation.State.ISSUED,
            notes=notes,
        )
        log_audit_event(
            action=AuditAction.CITATION_ISSUED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=citation,
            detail={
                "citation_id":  citation.pk,
                "violation_id": violation.pk,
            },
        )
        return citation

    @staticmethod
    def transition(
        actor,
        citation: Citation,
        new_state: str,
        notes: str = "",
        request=None,
    ) -> Citation:
        """
        Advance a Citation to a new lifecycle state.

        Valid transitions (from domain-model.md + documented assumption):
          issued      → contested | adjudicated
          contested   → adjudicated
          adjudicated → (terminal — no further transitions)
        """
        allowed = Citation.VALID_TRANSITIONS.get(citation.state, [])
        if new_state not in allowed:
            raise InvalidCitationTransitionError(
                f"Cannot transition citation #{citation.pk} from "
                f"'{citation.state}' to '{new_state}'. "
                f"Allowed transitions: {allowed or ['none — terminal state']}."
            )

        old_state = citation.state
        citation.state = new_state
        if notes:
            citation.notes = notes
        citation.save(update_fields=["state", "notes", "updated_at"])

        # Map state to audit action
        action_map = {
            Citation.State.CONTESTED:   AuditAction.CITATION_CONTESTED,
            Citation.State.ADJUDICATED: AuditAction.CITATION_ADJUDICATED,
        }
        log_audit_event(
            action=action_map[new_state],
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=citation,
            detail={
                "citation_id":  citation.pk,
                "violation_id": citation.violation_id,
                "from_state":   old_state,
                "to_state":     new_state,
            },
        )
        return citation
