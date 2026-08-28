# System Architecture Diagrams

## Status

Phase 4A — Architecture design. Diagrams use ASCII/Mermaid notation.
Database ER diagrams are deferred until domain models are implemented.

---

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                    │
│  Browser Dashboard  │  Mobile App  │  AI Services  │  IoT Devices  │
└────────┬────────────┴──────┬───────┴──────┬────────┴──────┬────────┘
         │                  │              │               │
         │         HTTPS / REST API        │               │
         ▼                  ▼              │               │
┌────────────────────────────────────┐    │               │
│         NGINX / Load Balancer      │    │               │
└────────────────┬───────────────────┘    │               │
                 │                        │               │
         ┌───────▼────────────────────────▼───────────────▼──────────┐
         │              DJANGO APPLICATION TIER                       │
         │                                                            │
         │  config/urls.py → config/api.py → app urls                │
         │                                                            │
         │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
         │  │accounts │  │  audit   │  │  roads   │  │ cameras  │  │
         │  │  auth   │  │ (events) │  │ (infra)  │  │(devices) │  │
         │  └─────────┘  └──────────┘  └──────────┘  └──────────┘  │
         │                                                            │
         │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
         │  │ traffic │  │violations│  │ payments │  │analytics │  │
         │  │(ops)    │  │(enforc.) │  │(fines)   │  │(reports) │  │
         │  └─────────┘  └──────────┘  └──────────┘  └──────────┘  │
         │                                                            │
         │  ┌──────────────────────────────────────────────────────┐ │
         │  │  common (pagination, responses, validators, utils)   │ │
         │  └──────────────────────────────────────────────────────┘ │
         └───────────────────────────┬────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
   ┌──────────────────┐   ┌────────────────────┐  ┌────────────────┐
   │   PostgreSQL     │   │   Redis (future)   │  │ Object Storage │
   │  Primary DB      │   │ Cache + Task Queue │  │ (S3 / Blob)    │
   │                  │   │                    │  │ Camera frames  │
   │  - accounts_*    │   │  - Session cache   │  │ Evidence files │
   │  - audit_*       │   │  - Celery broker   │  │ AI datasets    │
   │  - roads_*       │   │  - Channel layer   │  │                │
   │  - traffic_*     │   │    (Phase 5)       │  │                │
   │  - cameras_*     │   │                    │  │                │
   │  - violations_*  │   └────────────────────┘  └────────────────┘
   │  - payments_*    │
   └──────────────────┘

                    EXTERNAL AI SERVICES (separate processes)
   ┌──────────────────────────────────────────────────────────────────┐
   │  vehicle_detection │ tracking │ ocr │ face_recognition │prediction│
   │                                                                  │
   │  ← communicate via Django REST API only (no direct DB access) → │
   └──────────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication and RBAC Flow

```
Client
  │
  │  POST /api/v1/auth/login/   { username, password }
  ▼
LoginView (AllowAny)
  │
  ├─[invalid]──► 401 + AuditEvent(auth.login.failure)
  │
  └─[valid]────► JWT(access=15min, refresh=1day)
                     + AuditEvent(auth.login.success)
                     │
                     ▼
               Client stores tokens

  │  GET /api/v1/auth/me/   Authorization: Bearer <access>
  ▼
JWTAuthentication middleware
  │
  ├─[invalid/expired]──► 401
  │
  └─[valid]────────────► request.user populated
                               │
                               ▼
                         IsAuthenticated ──[pass]──► MeView
                                                        │
                                                        ▼
                                                  UserProfileSerializer
                                                  (no password, no secrets)

  │  PATCH /api/v1/auth/users/{id}/status/   (admin action)
  ▼
JWTAuthentication → IsAuthenticated → IsSystemAdmin
  │
  ├─[not admin]──► 403
  │
  └─[admin]──────► UserStatusView
                        │
                        ├── RoleService.set_active()
                        │     └── SelfElevationError guard
                        └── AuditEvent(admin.user.deactivated)

  │  POST /api/v1/auth/refresh/   { refresh }
  ▼
RefreshView (AllowAny)
  │
  ├─[blacklisted/invalid]──► 401 + AuditEvent(auth.refresh.failure)
  │
  └─[valid]────────────────► new access + new refresh (rotation)
                               old refresh → token_blacklist
                               + AuditEvent(auth.refresh.success)
```

---

## 3. Domain Dependency Graph

```
                    ┌───────────┐
                    │  common   │  ← used by all apps
                    └─────▲─────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────┴───┐  ┌────┴────┐  ┌──┴──────┐
        │accounts │  │  audit  │  │  core   │
        └─────▲───┘  └────▲────┘  └─────────┘
              │           │  (all apps call log_audit_event)
              │           │
        ┌─────┴───────────┴──────────────────┐
        │              roads                 │ ← reference data
        └─────┬──────────────────────────────┘
              │  (cameras, traffic reference roads)
     ┌────────┼─────────┐
     │        │         │
┌────┴────┐   │   ┌─────┴────┐
│ cameras │   │   │ traffic  │
└────┬────┘   │   └─────┬────┘
     │        │         │  (violations reference traffic events)
     └────────┘         │
                  ┌─────┴──────┐
                  │ violations │
                  └─────┬──────┘
                        │  (payments reference violations/citations)
                  ┌─────┴──────┐
                  │  payments  │
                  └─────┬──────┘
                        │  (analytics reads all domains)
                  ┌─────┴──────┐
                  │ analytics  │
                  └────────────┘

         notifications ← triggered by traffic + violations
```

---

## 4. Violation Detection Data Flow

```
Physical Camera
    │  RTSP stream
    ▼
AI: vehicle_detection + ocr
    │  POST /api/v1/violations/
    │  {
    │    "plate": "ABC123",
    │    "violation_type": "speeding",
    │    "speed_kmh": 87,
    │    "limit_kmh": 60,
    │    "camera_id": 42,
    │    "segment_id": 7,
    │    "confidence": 0.97,
    │    "evidence_url": "s3://bucket/evidence/xyz.mp4"
    │  }
    ▼
Django (ViolationCreateView — AI service account)
    ├── Validate confidence ≥ threshold
    ├── Look up or create Vehicle(plate="ABC123")
    ├── Create TrafficViolation (pending review)
    ├── Create ViolationEvidence (reference to S3 URL)
    └── AuditEvent(violations.violation.created)

    │  (Law Enforcement review)
    ▼
Law Enforcement Officer
    │  POST /api/v1/violations/{id}/issue-citation/
    ▼
Django (CitationCreateView — IsLawEnforcement)
    ├── Create Citation (status=issued)
    ├── AuditEvent(violations.citation.issued)
    └── Trigger notification task → Fine created by Payment Officer
```

---

## 5. Audit Architecture (Implemented)

```
Any View (accounts, violations, traffic, etc.)
    │
    │  log_audit_event(
    │    action=AuditAction.X,
    │    outcome=Outcome.SUCCESS,
    │    request=request,
    │    actor=request.user,
    │    target=target_object,
    │    detail={...scrubbed...}
    │  )
    ▼
apps.audit.services.log_audit_event()
    ├── Extract IP from X-Forwarded-For / REMOTE_ADDR
    ├── Extract User-Agent (truncated to 512 chars)
    ├── _scrub_detail() — remove password/token/secret keys
    └── AuditEvent.save()  ← append-only (save() blocks updates)
              │
              ▼
       audit_auditevent table
              │
              ▼  (System Admin only)
       GET /api/v1/audit/events/
       GET /api/v1/audit/events/{id}/
       (read-only, paginated, filterable by action + outcome)
```

---

## Notes

- ER diagrams for individual domains will be added in their respective implementation phases.
- Sequence diagrams for real-time flows will be added in Phase 5.
- This document should be updated whenever a new app is added or an integration pattern changes.
