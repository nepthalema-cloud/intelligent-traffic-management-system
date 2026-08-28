"""
WebSocket consumers — Phase 5.

DashboardConsumer
-----------------
Group: "dashboard"
Pushes:
  - measurement_created  → new TrafficMeasurement from AI/sensor
  - incident_updated     → incident state change
  - violation_created    → new violation from AI
  - system_status        → periodic system state broadcast

CameraConsumer
--------------
Group: "cameras"
Pushes:
  - camera_health_changed → connectivity/health update

Authentication: JWT via query param (see ws_middleware.py)
Authorization:  Any authenticated user may connect.  Sensitive data
                (plate numbers, evidence URLs) is NOT pushed over WebSocket —
                clients must use the REST API with proper RBAC to retrieve it.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class DashboardConsumer(AsyncWebsocketConsumer):
    GROUP = "dashboard"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()
        logger.info("WS dashboard connected: user=%s", user.username)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Dashboard consumer is receive-only (server → client push)
        pass

    # ── Message handlers (called by channel_layer.group_send) ────────────

    async def measurement_created(self, event):
        await self.send(text_data=json.dumps({
            "type":    "measurement_created",
            "payload": event["payload"],
        }))

    async def incident_updated(self, event):
        await self.send(text_data=json.dumps({
            "type":    "incident_updated",
            "payload": event["payload"],
        }))

    async def violation_created(self, event):
        # Only push non-PII summary: violation_type, confidence, camera
        # Plate number / evidence NOT included
        payload = event["payload"]
        safe = {
            "id":             payload.get("id"),
            "violation_type": payload.get("violation_type"),
            "confidence":     payload.get("confidence"),
            "camera_id":      payload.get("camera_id"),
            "occurred_at":    payload.get("occurred_at"),
            "review_status":  payload.get("review_status"),
        }
        await self.send(text_data=json.dumps({
            "type":    "violation_created",
            "payload": safe,
        }))

    async def system_status(self, event):
        await self.send(text_data=json.dumps({
            "type":    "system_status",
            "payload": event["payload"],
        }))


class CameraConsumer(AsyncWebsocketConsumer):
    GROUP = "cameras"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def camera_health_changed(self, event):
        await self.send(text_data=json.dumps({
            "type":    "camera_health_changed",
            "payload": event["payload"],
        }))
