"""
Service layer for the roads app.

All business operations for Road, RoadSegment, Intersection, and Lane
live here.  Views are kept thin and call these service methods.

Audit events are emitted from this layer so that every code path that
mutates road data — including future management commands — produces an
audit trail automatically.

Dependency direction:  roads.services → audit.services  (correct)
                       audit.services → roads           (forbidden)
"""

from apps.audit.services import AuditAction, Outcome, log_audit_event
from apps.roads.models import Intersection, Lane, Road, RoadSegment


class RoadServiceError(Exception):
    """Base exception for road service errors."""


class RoadNotFoundError(RoadServiceError):
    pass


class IntersectionNotFoundError(RoadServiceError):
    pass


class SegmentNotFoundError(RoadServiceError):
    pass


class LaneNotFoundError(RoadServiceError):
    pass


class DuplicateRoadNameError(RoadServiceError):
    pass


class InvalidLaneNumberError(RoadServiceError):
    pass


class RoadService:
    """Encapsulates all create/update/deactivate operations for road infrastructure."""

    # ------------------------------------------------------------------
    # Road
    # ------------------------------------------------------------------

    @staticmethod
    def create_road(actor, name: str, road_type: str = "other",
                    description: str = "", request=None) -> Road:
        if Road.objects.filter(name=name).exists():
            raise DuplicateRoadNameError(f"A road named '{name}' already exists.")
        road = Road.objects.create(name=name, road_type=road_type, description=description)
        log_audit_event(
            action=AuditAction.ROAD_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=road,
            detail={"name": name, "road_type": road_type},
        )
        return road

    @staticmethod
    def update_road(actor, road: Road, request=None, **fields) -> Road:
        old_name = road.name
        for attr, value in fields.items():
            setattr(road, attr, value)
        road.save()
        log_audit_event(
            action=AuditAction.ROAD_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=road,
            detail={"fields_changed": list(fields.keys()), "old_name": old_name},
        )
        return road

    @staticmethod
    def set_road_active(actor, road: Road, is_active: bool, request=None) -> Road:
        road.is_active = is_active
        road.save(update_fields=["is_active", "updated_at"])
        action = AuditAction.ROAD_ACTIVATED if is_active else AuditAction.ROAD_DEACTIVATED
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=road,
            detail={"is_active": is_active},
        )
        return road

    # ------------------------------------------------------------------
    # Intersection
    # ------------------------------------------------------------------

    @staticmethod
    def create_intersection(actor, name: str, description: str = "",
                            latitude=None, longitude=None, request=None) -> Intersection:
        intersection = Intersection.objects.create(
            name=name, description=description,
            latitude=latitude, longitude=longitude,
        )
        log_audit_event(
            action=AuditAction.INTERSECTION_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=intersection,
            detail={"name": name},
        )
        return intersection

    @staticmethod
    def update_intersection(actor, intersection: Intersection,
                            request=None, **fields) -> Intersection:
        for attr, value in fields.items():
            setattr(intersection, attr, value)
        intersection.save()
        log_audit_event(
            action=AuditAction.INTERSECTION_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=intersection,
            detail={"fields_changed": list(fields.keys())},
        )
        return intersection

    @staticmethod
    def set_intersection_active(actor, intersection: Intersection,
                                is_active: bool, request=None) -> Intersection:
        intersection.is_active = is_active
        intersection.save(update_fields=["is_active", "updated_at"])
        action = (AuditAction.INTERSECTION_ACTIVATED if is_active
                  else AuditAction.INTERSECTION_DEACTIVATED)
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=intersection,
            detail={"is_active": is_active},
        )
        return intersection

    # ------------------------------------------------------------------
    # RoadSegment
    # ------------------------------------------------------------------

    @staticmethod
    def create_segment(actor, road: Road, request=None, **fields) -> RoadSegment:
        segment = RoadSegment.objects.create(road=road, **fields)
        log_audit_event(
            action=AuditAction.SEGMENT_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=segment,
            detail={"road_id": road.pk, "speed_limit_kmh": fields.get("speed_limit_kmh")},
        )
        return segment

    @staticmethod
    def update_segment(actor, segment: RoadSegment,
                       request=None, **fields) -> RoadSegment:
        old_speed = segment.speed_limit_kmh
        for attr, value in fields.items():
            setattr(segment, attr, value)
        segment.save()

        # Emit a specific audit event when speed limit changes
        new_speed = segment.speed_limit_kmh
        if "speed_limit_kmh" in fields and old_speed != new_speed:
            log_audit_event(
                action=AuditAction.SEGMENT_SPEED_LIMIT_CHANGED,
                outcome=Outcome.SUCCESS,
                request=request,
                actor=actor,
                target=segment,
                detail={"old_speed_limit_kmh": old_speed, "new_speed_limit_kmh": new_speed},
            )
        log_audit_event(
            action=AuditAction.SEGMENT_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=segment,
            detail={"fields_changed": list(fields.keys())},
        )
        return segment

    @staticmethod
    def set_segment_active(actor, segment: RoadSegment,
                           is_active: bool, request=None) -> RoadSegment:
        segment.is_active = is_active
        segment.save(update_fields=["is_active", "updated_at"])
        action = (AuditAction.SEGMENT_ACTIVATED if is_active
                  else AuditAction.SEGMENT_DEACTIVATED)
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=segment,
            detail={"is_active": is_active},
        )
        return segment

    # ------------------------------------------------------------------
    # Lane
    # ------------------------------------------------------------------

    @staticmethod
    def create_lane(actor, segment: RoadSegment, lane_number: int,
                    lane_type: str = "travel", description: str = "",
                    request=None) -> Lane:
        if Lane.objects.filter(segment=segment, lane_number=lane_number).exists():
            raise InvalidLaneNumberError(
                f"Lane {lane_number} already exists on segment {segment.pk}."
            )
        lane = Lane.objects.create(
            segment=segment,
            lane_number=lane_number,
            lane_type=lane_type,
            description=description,
        )
        log_audit_event(
            action=AuditAction.LANE_CREATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=lane,
            detail={"segment_id": segment.pk, "lane_number": lane_number,
                    "lane_type": lane_type},
        )
        return lane

    @staticmethod
    def update_lane(actor, lane: Lane, request=None, **fields) -> Lane:
        for attr, value in fields.items():
            setattr(lane, attr, value)
        lane.save()
        log_audit_event(
            action=AuditAction.LANE_UPDATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=lane,
            detail={"fields_changed": list(fields.keys())},
        )
        return lane

    @staticmethod
    def set_lane_active(actor, lane: Lane, is_active: bool,
                        request=None) -> Lane:
        lane.is_active = is_active
        lane.save(update_fields=["is_active", "updated_at"])
        action = AuditAction.LANE_ACTIVATED if is_active else AuditAction.LANE_DEACTIVATED
        log_audit_event(
            action=action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=actor,
            target=lane,
            detail={"is_active": is_active},
        )
        return lane
