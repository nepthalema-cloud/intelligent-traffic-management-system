"""
Audit service — the single entry point for writing audit events.

Usage
-----
All other apps call ``log_audit_event()`` from this module::

    from apps.audit.services import log_audit_event, AuditAction, Outcome

    log_audit_event(
        action=AuditAction.AUTH_LOGIN_SUCCESS,
        outcome=Outcome.SUCCESS,
        request=request,
        actor=request.user,
    )

Dependency direction
--------------------
``accounts`` → ``audit``  (correct: accounts calls audit)
``audit``    → ``accounts`` is forbidden (no import of accounts models here).

Security
--------
This module NEVER logs passwords, password hashes, SECRET_KEY, access tokens,
or refresh tokens.  The ``detail`` dict passed by callers must not contain
these values.  The ``_scrub_detail`` helper strips any accidentally-included
sensitive keys before persisting.
"""

import logging
from typing import Any

from apps.audit.models import AuditEvent, Outcome  # re-export Outcome for callers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event action constants
# ---------------------------------------------------------------------------

class AuditAction:
    """Machine-readable action codes used throughout the audit system."""

    # Authentication
    AUTH_LOGIN_SUCCESS   = "auth.login.success"
    AUTH_LOGIN_FAILURE   = "auth.login.failure"
    AUTH_REFRESH_SUCCESS = "auth.refresh.success"
    AUTH_REFRESH_FAILURE = "auth.refresh.failure"
    AUTH_LOGOUT_SUCCESS  = "auth.logout.success"
    AUTH_LOGOUT_FAILURE  = "auth.logout.failure"

    # Role management
    ADMIN_ROLE_ASSIGNED = "admin.role.assigned"
    ADMIN_ROLE_REMOVED  = "admin.role.removed"

    # User status management
    ADMIN_USER_ACTIVATED   = "admin.user.activated"
    ADMIN_USER_DEACTIVATED = "admin.user.deactivated"

    # Road infrastructure
    ROAD_CREATED         = "road.created"
    ROAD_UPDATED         = "road.updated"
    ROAD_ACTIVATED       = "road.activated"
    ROAD_DEACTIVATED     = "road.deactivated"
    SEGMENT_CREATED      = "road.segment.created"
    SEGMENT_UPDATED      = "road.segment.updated"
    SEGMENT_SPEED_LIMIT_CHANGED = "road.segment.speed_limit_changed"
    SEGMENT_ACTIVATED    = "road.segment.activated"
    SEGMENT_DEACTIVATED  = "road.segment.deactivated"
    INTERSECTION_CREATED = "road.intersection.created"
    INTERSECTION_UPDATED = "road.intersection.updated"
    INTERSECTION_ACTIVATED   = "road.intersection.activated"
    INTERSECTION_DEACTIVATED = "road.intersection.deactivated"
    LANE_CREATED         = "road.lane.created"
    LANE_UPDATED         = "road.lane.updated"
    LANE_ACTIVATED       = "road.lane.activated"
    LANE_DEACTIVATED     = "road.lane.deactivated"

    # Camera and sensor devices
    CAMERA_CREATED       = "camera.created"
    CAMERA_UPDATED       = "camera.updated"
    CAMERA_ACTIVATED     = "camera.activated"
    CAMERA_DEACTIVATED   = "camera.deactivated"
    SENSOR_CREATED       = "sensor.created"
    SENSOR_UPDATED       = "sensor.updated"
    SENSOR_ACTIVATED     = "sensor.activated"
    SENSOR_DEACTIVATED   = "sensor.deactivated"

    # Traffic signals
    TRAFFIC_SIGNAL_CREATED      = "traffic.signal.created"
    TRAFFIC_SIGNAL_UPDATED      = "traffic.signal.updated"
    TRAFFIC_SIGNAL_ACTIVATED    = "traffic.signal.activated"
    TRAFFIC_SIGNAL_DEACTIVATED  = "traffic.signal.deactivated"
    SIGNAL_PHASE_CREATED        = "traffic.signal_phase.created"
    SIGNAL_PHASE_UPDATED        = "traffic.signal_phase.updated"
    SIGNAL_PHASE_ACTIVATED      = "traffic.signal_phase.activated"
    SIGNAL_PHASE_DEACTIVATED    = "traffic.signal_phase.deactivated"

    # Traffic events
    TRAFFIC_EVENT_CREATED     = "traffic.event.created"
    TRAFFIC_EVENT_UPDATED     = "traffic.event.updated"
    TRAFFIC_EVENT_ACTIVATED   = "traffic.event.activated"
    TRAFFIC_EVENT_DEACTIVATED = "traffic.event.deactivated"

    # Traffic incidents
    TRAFFIC_INCIDENT_CREATED            = "traffic.incident.created"
    TRAFFIC_INCIDENT_UPDATED            = "traffic.incident.updated"
    TRAFFIC_INCIDENT_STATE_CHANGED      = "traffic.incident.state_changed"
    TRAFFIC_INCIDENT_ACTIVATED          = "traffic.incident.activated"
    TRAFFIC_INCIDENT_DEACTIVATED        = "traffic.incident.deactivated"

    # Vehicle reference data (violations domain)
    VEHICLE_CREATED    = "violations.vehicle.created"
    VEHICLE_UPDATED    = "violations.vehicle.updated"
    VEHICLE_ACTIVATED  = "violations.vehicle.activated"
    VEHICLE_DEACTIVATED = "violations.vehicle.deactivated"

    # Traffic violations (violations domain — Phase 4D.2)
    VIOLATION_CREATED     = "violations.violation.created"
    VIOLATION_DEACTIVATED = "violations.violation.deactivated"

    # Violation evidence (violations domain — Phase 4D.2)
    EVIDENCE_CREATED = "violations.evidence.created"

    # Citations (violations domain — Phase 4D.2)
    CITATION_ISSUED      = "violations.citation.issued"
    CITATION_CONTESTED   = "violations.citation.contested"
    CITATION_ADJUDICATED = "violations.citation.adjudicated"

    # Phase 5 — AI pipeline events
    AI_VIOLATION_AUTO_ACCEPTED  = "ai.violation.auto_accepted"
    AI_VIOLATION_PENDING_REVIEW = "ai.violation.pending_review"
    AI_VIOLATION_LOW_CONFIDENCE = "ai.violation.low_confidence"
    AI_MEASUREMENT_INGESTED     = "ai.measurement.ingested"
    CAMERA_CREDENTIAL_SET       = "camera.credential.set"
    CAMERA_CREDENTIAL_ROTATED   = "camera.credential.rotated"
    CAMERA_HEALTH_CHANGED       = "camera.health.changed"


# Keys that must never be persisted in the detail field
_FORBIDDEN_DETAIL_KEYS = frozenset({
    "password", "passwd", "secret", "secret_key",
    "access", "access_token",
    "refresh", "refresh_token",
    "token", "authorization",
    "signing_key",
})


def _scrub_detail(detail: dict | None) -> dict | None:
    """Remove any accidentally-included sensitive keys from detail."""
    if not detail:
        return detail
    scrubbed = {
        k: v for k, v in detail.items()
        if k.lower() not in _FORBIDDEN_DETAIL_KEYS
    }
    return scrubbed or None


def _get_client_ip(request) -> str | None:
    """Extract the client IP address from a DRF/Django request."""
    if request is None:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first (leftmost) address — closest to the real client
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _get_user_agent(request) -> str | None:
    """Extract the User-Agent string from a DRF/Django request."""
    if request is None:
        return None
    return request.META.get("HTTP_USER_AGENT", "")[:512] or None


def log_audit_event(
    action: str,
    outcome: str = Outcome.SUCCESS,
    request=None,
    actor=None,
    target=None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent | None:
    """
    Create and persist a single audit event.

    Parameters
    ----------
    action:
        Machine-readable action code from ``AuditAction``.
    outcome:
        One of ``Outcome.SUCCESS``, ``Outcome.FAILURE``, ``Outcome.DENIED``.
    request:
        The current DRF/Django request object.  Used to extract IP and
        user-agent.  Pass ``None`` for system-generated events.
    actor:
        The User instance who performed the action.  Pass ``None`` for
        anonymous or system events.
    target:
        The affected model instance.  The type and PK will be extracted
        automatically.  Overridden by ``target_type``/``target_id`` if both
        are provided.
    target_type:
        Override for the target content-type string (e.g. ``"accounts.user"``).
    target_id:
        Override for the target primary key as a string.
    detail:
        Optional free-form dict with extra context.  Sensitive keys are
        automatically stripped before persisting.

    Returns
    -------
    The created ``AuditEvent`` instance, or ``None`` if an error occurred
    (errors are logged but never re-raised so as not to break callers).
    """
    try:
        # Resolve actor fields
        actor_id: int | None = None
        actor_username: str | None = None
        if actor is not None and hasattr(actor, "pk") and actor.pk:
            actor_id = actor.pk
            actor_username = getattr(actor, "username", None)

        # Resolve target fields
        resolved_type = target_type
        resolved_id = target_id
        if target is not None and (resolved_type is None or resolved_id is None):
            app_label = target._meta.app_label
            model_name = target._meta.model_name
            resolved_type = resolved_type or f"{app_label}.{model_name}"
            resolved_id = resolved_id or str(target.pk)

        event = AuditEvent(
            actor_id=actor_id,
            actor_username=actor_username,
            action=action,
            target_type=resolved_type,
            target_id=resolved_id,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
            outcome=outcome,
            detail=_scrub_detail(detail),
        )
        event.save()
        return event

    except Exception as exc:  # pragma: no cover
        # Audit failures must never break the calling operation.
        logger.error(
            "Failed to write audit event: action=%s outcome=%s error=%s",
            action, outcome, exc,
            exc_info=True,
        )
        return None
