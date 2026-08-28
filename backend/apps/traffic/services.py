"""
Service layer for the traffic app — Phase 4C.1.

TrafficSignalService  — create/update/deactivate TrafficSignal records
SignalPhaseService    — create/update/deactivate SignalPhase records

Business rules enforced here
-----------------------------
- Signal names must be unique.
- Phase numbers must be unique within a signal.
- New phases cannot be created under an inactive signal.
- ``minimum_green_seconds <= maximum_green_seconds`` (validated at serializer
  level; service assumes the caller has already validated this).
- All mutating operations emit audit events.
- Audit failures never break the underlying operation.

Dependency direction
--------------------
traffic.services → audit.services  (correct)
audit.services   → traffic          (forbidden)
"""

from apps.audit.services import AuditAction, Outcome, log_audit_event
from apps.traffic.models import SignalPhase, TrafficEvent, TrafficIncident, TrafficMeasurement, TrafficSignal


class TrafficSignalServiceError(Exception):
    """Base exception for TrafficSignalService errors."""


class DuplicateSignalNameError(TrafficSignalServiceError):
    pass


class SignalPhaseServiceError(Exception):
    """Base exception for SignalPhaseService errors."""


class DuplicatePhaseNumberError(SignalPhaseServiceError):
    pass


class InactiveSignalError(SignalPhaseServiceError):
    """Raised when trying to add a phase to an inactive signal."""


class TrafficSignalService:
    """Encapsulates all create/update/deactivate operations for TrafficSignal."""

    @staticmethod
    def create(
        actor,
        name: str,
        intersection,
        controller_type: str = "",
        controller_identifier: str = "",
        request=None,
    ) -> TrafficSignal:
        if TrafficSignal.objects.filter(name=name).exists():
            raise DuplicateSignalNameError(
                f"A traffic signal named '{name}' already exists."
            )
        signal = TrafficSignal.objects.create(
            name=name,
            intersection=intersection,
            controller_type=controller_type,
            controller_identifier=controller_identifier,
        )
        log_audit_event(
            action=AuditAction.TRAFFIC_SIGNAL_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=signal,
            detail={
                "name": name,
                "intersection_id": intersection.pk,
            },
        )
        return signal

    @staticmethod
    def update(actor, signal: TrafficSignal, request=None, **fields) -> TrafficSignal:
        old_name = signal.name
        for attr, value in fields.items():
            setattr(signal, attr, value)
        signal.save()
        log_audit_event(
            action=AuditAction.TRAFFIC_SIGNAL_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=signal,
            detail={"fields_changed": list(fields.keys()), "old_name": old_name},
        )
        return signal

    @staticmethod
    def set_active(
        actor, signal: TrafficSignal, is_active: bool, request=None
    ) -> TrafficSignal:
        signal.is_active = is_active
        signal.save(update_fields=["is_active", "updated_at"])
        action = (
            AuditAction.TRAFFIC_SIGNAL_ACTIVATED
            if is_active
            else AuditAction.TRAFFIC_SIGNAL_DEACTIVATED
        )
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=signal,
            detail={"is_active": is_active},
        )
        return signal


class SignalPhaseService:
    """Encapsulates all create/update/deactivate operations for SignalPhase."""

    @staticmethod
    def create(
        actor,
        signal: TrafficSignal,
        phase_number: int,
        name: str,
        minimum_green_seconds: int,
        maximum_green_seconds: int,
        yellow_seconds: int,
        all_red_seconds: int,
        movement: str = "",
        request=None,
    ) -> SignalPhase:
        if not signal.is_active:
            raise InactiveSignalError(
                f"Cannot create a phase for inactive signal '{signal.name}'. "
                "Activate the signal first."
            )
        if SignalPhase.objects.filter(signal=signal, phase_number=phase_number).exists():
            raise DuplicatePhaseNumberError(
                f"Phase {phase_number} already exists on signal '{signal.name}'."
            )
        phase = SignalPhase.objects.create(
            signal=signal,
            phase_number=phase_number,
            name=name,
            movement=movement,
            minimum_green_seconds=minimum_green_seconds,
            maximum_green_seconds=maximum_green_seconds,
            yellow_seconds=yellow_seconds,
            all_red_seconds=all_red_seconds,
        )
        log_audit_event(
            action=AuditAction.SIGNAL_PHASE_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=phase,
            detail={
                "signal_id": signal.pk,
                "phase_number": phase_number,
            },
        )
        return phase

    @staticmethod
    def update(actor, phase: SignalPhase, request=None, **fields) -> SignalPhase:
        for attr, value in fields.items():
            setattr(phase, attr, value)
        phase.save()
        log_audit_event(
            action=AuditAction.SIGNAL_PHASE_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=phase,
            detail={"fields_changed": list(fields.keys())},
        )
        return phase

    @staticmethod
    def set_active(
        actor, phase: SignalPhase, is_active: bool, request=None
    ) -> SignalPhase:
        phase.is_active = is_active
        phase.save(update_fields=["is_active", "updated_at"])
        action = (
            AuditAction.SIGNAL_PHASE_ACTIVATED
            if is_active
            else AuditAction.SIGNAL_PHASE_DEACTIVATED
        )
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=phase,
            detail={"is_active": is_active},
        )
        return phase


class MeasurementServiceError(Exception):
    """Base exception for MeasurementService errors."""


class InvalidMeasurementSourceError(MeasurementServiceError):
    """Raised when source validation fails (missing, duplicate, or wrong type)."""


class MeasurementService:
    """
    Encapsulates creation of TrafficMeasurement records.

    Create only — no update/delete operations exist.

    Audit
    -----
    Individual measurement inserts are NOT audited.
    The architecture document (domain-model.md) explicitly classifies
    TrafficMeasurement as 'No (volume too high)' for audit.
    """

    @staticmethod
    def create(
        segment,
        measured_at,
        camera=None,
        sensor=None,
        vehicle_count=None,
        avg_speed_kmh=None,
        occupancy_pct=None,
        data_source="demo",   # Phase 5: "ai" | "sensor" | "manual" | "demo"
    ) -> TrafficMeasurement:
        """
        Create and persist a single TrafficMeasurement record.

        Business rules enforced here
        ----------------------------
        - Exactly one of camera or sensor must be supplied.
        - No audit event is emitted (volume too high).
        - Record is append-only; no update/delete path exists in this service.
        """
        if camera is not None and sensor is not None:
            raise InvalidMeasurementSourceError(
                "A measurement must reference exactly one source: "
                "either a camera or a sensor, not both."
            )
        if camera is None and sensor is None:
            raise InvalidMeasurementSourceError(
                "A measurement must reference exactly one source: "
                "provide either 'camera' or 'sensor'."
            )
        return TrafficMeasurement.objects.create(
            segment=segment,
            measured_at=measured_at,
            camera=camera,
            sensor=sensor,
            vehicle_count=vehicle_count,
            avg_speed_kmh=avg_speed_kmh,
            occupancy_pct=occupancy_pct,
            data_source=data_source,
        )

    @staticmethod
    def bulk_create(measurements: list[dict]) -> list[TrafficMeasurement]:
        """
        Bulk-insert a list of measurement dicts for throughput-efficient ingestion.

        Each dict must contain the same keys accepted by ``create()``.
        No per-row validation is performed here — callers must validate upstream.
        No audit events are emitted.
        """
        objects = [
            TrafficMeasurement(
                segment=m["segment"],
                measured_at=m["measured_at"],
                camera=m.get("camera"),
                sensor=m.get("sensor"),
                vehicle_count=m.get("vehicle_count"),
                avg_speed_kmh=m.get("avg_speed_kmh"),
                occupancy_pct=m.get("occupancy_pct"),
            )
            for m in measurements
        ]
        return TrafficMeasurement.objects.bulk_create(objects)


class TrafficEventServiceError(Exception):
    """Base exception for TrafficEventService errors."""


class TrafficEventService:
    """
    Encapsulates all create/update/deactivate operations for TrafficEvent.

    Audit events are emitted for every mutating operation (creation, updates,
    status changes) as required by domain-model.md: Audit = "Yes".
    """

    @staticmethod
    def create(
        actor,
        event_type: str,
        description: str,
        occurred_at,
        segment=None,
        intersection=None,
        request=None,
    ):
        from apps.traffic.models import TrafficEvent
        event = TrafficEvent.objects.create(
            event_type=event_type,
            description=description,
            occurred_at=occurred_at,
            segment=segment,
            intersection=intersection,
            created_by=actor if (actor and actor.pk) else None,
        )
        log_audit_event(
            action=AuditAction.TRAFFIC_EVENT_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=event,
            detail={
                "event_type": event_type,
                "segment_id": segment.pk if segment else None,
                "intersection_id": intersection.pk if intersection else None,
            },
        )
        return event

    @staticmethod
    def update(actor, event, request=None, **fields):
        for attr, value in fields.items():
            setattr(event, attr, value)
        event.save()
        log_audit_event(
            action=AuditAction.TRAFFIC_EVENT_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=event,
            detail={"fields_changed": list(fields.keys())},
        )
        return event

    @staticmethod
    def set_active(actor, event, is_active: bool, request=None):
        event.is_active = is_active
        event.save(update_fields=["is_active", "updated_at"])
        action = (
            AuditAction.TRAFFIC_EVENT_ACTIVATED
            if is_active
            else AuditAction.TRAFFIC_EVENT_DEACTIVATED
        )
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=event,
            detail={"is_active": is_active},
        )
        return event


class TrafficIncidentServiceError(Exception):
    """Base exception for TrafficIncidentService errors."""


class InvalidStateTransitionError(TrafficIncidentServiceError):
    """Raised when a requested lifecycle transition is not permitted."""


class TrafficIncidentService:
    """
    Encapsulates create/update/lifecycle-transition/deactivate operations
    for TrafficIncident records.

    All mutating operations emit audit events (domain-model.md: Audit = Yes).
    Lifecycle transition validation is the exclusive responsibility of this
    service — views must not bypass it.
    """

    @staticmethod
    def create(
        actor,
        title: str,
        description: str,
        incident_type: str,
        occurred_at,
        intersection=None,
        segment_ids: list[int] | None = None,
        request=None,
    ):
        from apps.traffic.models import TrafficIncident
        incident = TrafficIncident.objects.create(
            title=title,
            description=description,
            incident_type=incident_type,
            occurred_at=occurred_at,
            intersection=intersection,
            created_by=actor if (actor and actor.pk) else None,
        )
        if segment_ids:
            incident.segments.set(segment_ids)
        log_audit_event(
            action=AuditAction.TRAFFIC_INCIDENT_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=incident,
            detail={
                "title": title,
                "incident_type": incident_type,
                "state": incident.state,
                "intersection_id": intersection.pk if intersection else None,
                "segment_ids": segment_ids or [],
            },
        )
        return incident

    @staticmethod
    def update(actor, incident, request=None, segment_ids=None, **fields):
        from apps.traffic.models import TrafficIncident
        for attr, value in fields.items():
            setattr(incident, attr, value)
        incident.save()
        if segment_ids is not None:
            incident.segments.set(segment_ids)
        log_audit_event(
            action=AuditAction.TRAFFIC_INCIDENT_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=incident,
            detail={"fields_changed": list(fields.keys())},
        )
        return incident

    @staticmethod
    def transition_state(actor, incident, new_state: str, request=None):
        """
        Advance the incident through the documented lifecycle.

        Raises InvalidStateTransitionError for disallowed transitions.
        """
        from apps.traffic.models import TrafficIncident
        allowed = TrafficIncident.VALID_TRANSITIONS.get(incident.state, [])
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Transition from '{incident.state}' to '{new_state}' is not "
                f"permitted. Allowed next states: {allowed or ['(none — terminal state)']}"
            )
        old_state = incident.state
        incident.state = new_state
        incident.save(update_fields=["state", "updated_at"])
        log_audit_event(
            action=AuditAction.TRAFFIC_INCIDENT_STATE_CHANGED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=incident,
            detail={"old_state": old_state, "new_state": new_state},
        )
        return incident

    @staticmethod
    def set_active(actor, incident, is_active: bool, request=None):
        incident.is_active = is_active
        incident.save(update_fields=["is_active", "updated_at"])
        action = (
            AuditAction.TRAFFIC_INCIDENT_ACTIVATED
            if is_active
            else AuditAction.TRAFFIC_INCIDENT_DEACTIVATED
        )
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=incident,
            detail={"is_active": is_active},
        )
        return incident
