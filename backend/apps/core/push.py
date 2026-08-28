"""
Helper functions to push real-time events to WebSocket clients via Channel Layer.

Usage (from any Django app):
    from apps.core.push import push_measurement, push_camera_health, push_violation

Each function is a fire-and-forget async dispatch.  Callers should wrap in
    async_to_sync(push_measurement)(payload)
from synchronous Django views/services, or call directly from async code.
"""

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _push(group: str, message_type: str, payload: dict):
    """Synchronous wrapper — safe to call from synchronous Django code."""
    try:
        layer = get_channel_layer()
        if layer is None:
            return  # Channels not configured (e.g. unit tests)
        async_to_sync(layer.group_send)(group, {
            "type":    message_type,
            "payload": payload,
        })
    except Exception as exc:
        # Never let a push failure break the business operation
        logger.error("WebSocket push failed: group=%s type=%s error=%s", group, message_type, exc)


def push_measurement(payload: dict):
    """Push a new TrafficMeasurement to dashboard WebSocket clients."""
    _push("dashboard", "measurement_created", payload)


def push_incident_update(payload: dict):
    """Push an incident state change to dashboard WebSocket clients."""
    _push("dashboard", "incident_updated", payload)


def push_violation(payload: dict):
    """Push a new violation (non-PII summary) to dashboard WebSocket clients."""
    _push("dashboard", "violation_created", payload)


def push_system_status(payload: dict):
    """Push system mode/status to dashboard WebSocket clients."""
    _push("dashboard", "system_status", payload)


def push_camera_health(payload: dict):
    """Push camera health change to camera WebSocket clients."""
    _push("cameras", "camera_health_changed", payload)
