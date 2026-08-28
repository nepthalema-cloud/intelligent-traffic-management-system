"""
AI violation ingestion service helpers.

These are called by the AI service (via ingest.py) when a violation is
detected from real video analysis. They enforce confidence thresholds
per the architecture document (ai-integration.md).

Confidence thresholds:
  >= 0.95  → AUTO_ACCEPTED
  0.70–0.94 → PENDING (human review required)
  < 0.70   → LOW_CONFIDENCE (human review required before legal action)

All AI violations must include:
  - source = "ai"
  - confidence (from YOLO or rule confidence)
  - model_name and model_version
  - review_status derived from confidence
  - camera FK
  - evidence frame reference (external URL or local path)
"""

from django.conf import settings

MODEL_NAME    = "YOLOv8n"
MODEL_VERSION = "8.0"


def confidence_to_review_status(confidence: float) -> str:
    from apps.violations.models import TrafficViolation
    if confidence >= 0.95:
        return TrafficViolation.ReviewStatus.AUTO_ACCEPTED
    if confidence >= 0.70:
        return TrafficViolation.ReviewStatus.PENDING_REVIEW
    return TrafficViolation.ReviewStatus.LOW_CONFIDENCE
