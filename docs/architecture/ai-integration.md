# AI/ML Integration Architecture

## Status

Phase 4A — Design. AI services exist as separate microservice stubs (`ai-services/`).
Integration boundary defined here; not yet implemented.

---

## Core Principle

**AI/ML logic must never be embedded in Django domain models.**

The Django backend is the **system of record** for structured data. AI services are **producers and consumers** of that data. They communicate via the Django REST API, not via direct database access.

This boundary ensures:
- Domain models remain simple and testable without AI dependencies.
- AI models can be replaced or retrained without touching business logic.
- The Django backend remains operational when AI services are unavailable.

---

## AI Service Inventory

The project already contains AI service stubs under `ai-services/`:

| Service | Capability | Output |
|---|---|---|
| `vehicle_detection` | Detect and classify vehicles in camera frames | Vehicle type, bounding box, confidence |
| `tracking` | Track vehicle movement across frames | Vehicle trajectory, speed estimate |
| `ocr` | Read licence plates from images | Plate number string, confidence |
| `face_recognition` | Identify persons of interest (Law Enforcement only) | Match result, confidence |
| `prediction` | Predict future traffic conditions | Flow forecast, congestion probability |

---

## Integration Pattern

### Pattern A: AI Service → Django (event ingestion)

Used when AI generates structured output that must be stored as business records.

```
AI Service
    │
    │  POST /api/v1/traffic/measurements/
    │  POST /api/v1/violations/          (plate + violation type)
    │  POST /api/v1/cameras/{id}/events/ (detection event)
    │
    ▼
Django REST API (authenticated AI service account)
    │
    ▼
Database (TrafficMeasurement / TrafficViolation / CameraEvent)
```

**Authentication**: AI services authenticate with a dedicated service-account JWT token, assigned the minimum necessary role (e.g. a `system.ingest` internal role or a restricted user account).

**Validation**: Django validates all AI-submitted data exactly as it would human-submitted data. AI confidence scores below a threshold are stored but flagged for human review; they are not auto-accepted.

### Pattern B: Django → AI Service (synchronous query)

Used for on-demand AI inference triggered by user actions.

```
Law Enforcement Officer
    │  POST /api/v1/violations/{id}/identify-vehicle/
    ▼
Django View (IsLawEnforcement permission)
    │  HTTP call to AI OCR/face-recognition service
    ▼
AI Service returns result
    │
    ▼
Django stores result + creates AuditEvent (sensitive data access)
    │
    ▼
Response to officer
```

**Important**: Sensitive AI queries (face recognition, plate lookup) must generate audit events. This is already listed in `audit-logging.md` under "Sensitive data access."

### Pattern C: Background AI Processing

Used for non-time-critical analysis (traffic prediction, historical analytics).

```
Celery Beat (scheduled task)
    │  Fetches recent measurements from DB
    ▼
AI Prediction Service
    │  Returns forecast
    ▼
Celery Task writes TrafficFlowSummary / PredictionResult to DB
```

---

## Data Ownership Rules

| Data Type | Owner | AI Access |
|---|---|---|
| Raw camera frames | `apps.cameras` | Read-only via object storage |
| Processed measurements | `apps.traffic` | Write via REST API (Pattern A) |
| Violation evidence | `apps.violations` | Read via authenticated API |
| Model outputs / scores | `apps.analytics` | Write via REST API (Pattern A) |
| Training datasets | Object storage (S3) | Direct read — outside Django scope |

---

## AI Service Communication

All AI-to-Django communication uses the existing authenticated REST API.

- AI services obtain a JWT token via `POST /api/v1/auth/login/` using a dedicated service account.
- Service accounts are assigned the minimum necessary role.
- Tokens are rotated on the 15-minute expiry cycle using refresh tokens.
- If an AI service cannot authenticate, it fails gracefully — no business data is corrupted.

**No AI service has direct database access.** This is an absolute rule.

---

## Confidence Score Handling

AI outputs include a `confidence` field (0.0–1.0).

| Confidence | Handling |
|---|---|
| ≥ 0.95 | Auto-accepted; stored as verified |
| 0.70–0.94 | Stored as pending; flagged for human review |
| < 0.70 | Stored as low-confidence; human review required before any legal action |

Thresholds are configurable per detection type via a future `SystemConfiguration` model in `apps.core` or `apps.common`.

---

## Privacy and Legal Compliance

- **Face recognition** results must never be stored unless explicitly authorized by Law Enforcement and system configuration.
- **Plate number data** is PII in many jurisdictions — access is restricted to Law Enforcement and audited.
- AI training on live system data requires explicit data governance approval (out of scope for Phase 4A).

---

## Future AI Considerations

- **Model versioning**: Each AI result should reference the model version that produced it. Store `model_name` and `model_version` in AI-generated records.
- **Explainability**: For legal actions (violations), the AI evidence chain must be preserved — frames, confidence, model version.
- **Drift detection**: Background monitoring of AI output quality should alert Camera/Sensor Technicians to degraded camera feeds.
