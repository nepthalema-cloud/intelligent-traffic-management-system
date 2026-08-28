"""
Django REST API client for the vehicle detection AI service.

Authenticates via JWT (dedicated service account).
Posts measurements and violations through the Django API — NO direct DB access.
"""

import logging
import os
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

API_URL  = os.getenv("DJANGO_API_URL", "http://localhost:8000")
USERNAME = os.getenv("AI_SERVICE_USERNAME", "ai_service")
PASSWORD = os.getenv("AI_SERVICE_PASSWORD", "AiService2026!")

MODEL_NAME    = "YOLOv8n"
MODEL_VERSION = "8.0"


class DjangoIngestClient:
    """Authenticated REST client for posting AI results to Django."""

    def __init__(self):
        self._access  = None
        self._refresh = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Authentication ────────────────────────────────────────────────

    def login(self) -> bool:
        try:
            resp = self._session.post(
                f"{API_URL}/api/v1/auth/login/",
                json={"username": USERNAME, "password": PASSWORD},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()["data"]
                self._access  = data["access"]
                self._refresh = data["refresh"]
                self._session.headers["Authorization"] = f"Bearer {self._access}"
                logger.info("AI service authenticated as %s", USERNAME)
                return True
            logger.error("AI service login failed: %s %s", resp.status_code, resp.text)
            return False
        except Exception as exc:
            logger.error("AI service login error: %s", exc)
            return False

    def _refresh_token(self) -> bool:
        if not self._refresh:
            return self.login()
        try:
            resp = self._session.post(
                f"{API_URL}/api/v1/auth/refresh/",
                json={"refresh": self._refresh},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()["data"]
                self._access = data["access"]
                if "refresh" in data:
                    self._refresh = data["refresh"]
                self._session.headers["Authorization"] = f"Bearer {self._access}"
                return True
            return self.login()
        except Exception:
            return self.login()

    def _post(self, path: str, payload: dict, retry: bool = True) -> dict | None:
        try:
            resp = self._session.post(f"{API_URL}{path}", json=payload, timeout=10)
            if resp.status_code == 401 and retry:
                if self._refresh_token():
                    return self._post(path, payload, retry=False)
            if resp.status_code in (200, 201):
                return resp.json()
            logger.warning("POST %s → %s: %s", path, resp.status_code, resp.text[:200])
            return None
        except Exception as exc:
            logger.error("POST %s failed: %s", path, exc)
            return None

    # ── Data ingestion ────────────────────────────────────────────────

    def post_measurement(
        self,
        camera_id: int,
        vehicle_count: int,
        measured_at,
        segment_id=None,
        avg_speed_kmh=None,
        occupancy_pct=None,
    ):
        """
        POST a real TrafficMeasurement to Django.
        source=ai so the system knows this came from the AI pipeline.
        """
        payload = {
            "camera":        camera_id,
            "segment":       segment_id,
            "measured_at":   measured_at.isoformat(),
            "vehicle_count": vehicle_count,
            "avg_speed_kmh": avg_speed_kmh,
            "occupancy_pct": occupancy_pct,
            "data_source":   "ai",
        }
        result = self._post("/api/v1/traffic/measurements/", payload)
        if result:
            logger.debug(
                "Measurement posted: camera=%d vehicles=%d speed=%s",
                camera_id, vehicle_count, avg_speed_kmh,
            )
        return result

    def get_camera(self, camera_id: int) -> dict | None:
        """Fetch camera metadata from Django."""
        try:
            resp = self._session.get(
                f"{API_URL}/api/v1/cameras/{camera_id}/",
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("data")
        except Exception as exc:
            logger.error("get_camera(%d) failed: %s", camera_id, exc)
        return None

    def post_violation(
        self,
        camera_id: int,
        violation_type: str,
        confidence: float,
        occurred_at,
        description: str = "",
        vehicle_id: int | None = None,
    ) -> dict | None:
        """
        POST a real AI-detected violation.
        Only called when actual rule logic fires, never hardcoded.
        Confidence determines review_status on the backend.
        """
        payload = {
            "violation_type": violation_type,
            "description":    description,
            "occurred_at":    occurred_at.isoformat(),
            "camera":         camera_id,
            "source":         "ai",
            "confidence":     confidence,
            "model_name":     MODEL_NAME,
            "model_version":  MODEL_VERSION,
        }
        if vehicle_id:
            payload["vehicle"] = vehicle_id
        result = self._post("/api/v1/violations/", payload)
        if result:
            logger.info(
                "Violation posted: type=%s confidence=%.3f camera=%d",
                violation_type, confidence, camera_id,
            )
        return result

    def post_evidence(
        self,
        violation_id: int,
        evidence_url: str,
        confidence: float,
        description: str = "",
    ) -> dict | None:
        """Attach an evidence frame reference to a violation."""
        payload = {
            "violation":    violation_id,
            "evidence_type":"image",
            "evidence_url": evidence_url,
            "description":  description,
            "confidence":   confidence,
        }
        return self._post(f"/api/v1/violations/{violation_id}/evidence/", payload)

    def get_calibration(self, camera_id: int) -> dict | None:
        """
        Fetch per-camera calibration data for speed estimation.
        Returns None if no valid calibration exists.
        """
        try:
            resp = self._session.get(
                f"{API_URL}/api/v1/cameras/{camera_id}/calibration/",
                timeout=10,
            )
            if resp.status_code == 200:
                d = resp.json().get("data", {})
                if d.get("is_valid") and d.get("meters_per_pixel"):
                    return d
        except Exception as exc:
            logger.debug("get_calibration(%d) failed: %s", camera_id, exc)
        return None

    def report_camera_health(
        self,
        camera_id: int,
        connected: bool,
        detail: str = "",
    ) -> None:
        """Report camera connectivity state from the AI service perspective."""
        payload = {
            "health_status":       "healthy" if connected else "offline",
            "connectivity_status": "connected" if connected else "disconnected",
            "detail":              detail,
        }
        try:
            self._session.patch(
                f"{API_URL}/api/v1/cameras/{camera_id}/health/",
                json=payload,
                timeout=8,
            )
        except Exception:
            pass  # Health reporting failure must never stop AI processing
