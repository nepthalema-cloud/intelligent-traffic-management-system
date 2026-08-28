# Data Flow Architecture

## Status

Phase 4A — Design. No domain models implemented yet.

---

## Data Classification

| Category | Examples | Volume | Latency Tolerance | Storage Strategy |
|---|---|---|---|---|
| **Transactional** | Roads, cameras, users, violations, fines | Low–Medium | High | Primary PostgreSQL DB |
| **Real-time operational** | Signal state, live traffic measurements, sensor readings | Very High | Very Low | Primary DB (short window) + Time-series store (long-term) |
| **Historical/event** | Traffic measurements archive, incident records, audit log | High | Medium | Primary DB + partitioned tables or archival DB |
| **Analytical/aggregated** | Flow summaries, violation counts, congestion scores | Medium | High | Pre-computed views or separate analytics DB |
| **AI/ML data** | Training datasets, model outputs, confidence scores | High | Medium | Object storage (S3/blob) + lightweight DB references |

---

## Primary Data Flows

### 1. Traffic Sensor / Camera Ingestion

```
Physical Device
    │  (RTSP / REST / MQTT)
    ▼
AI Service (external micro-service)
    │  (HTTP POST to /api/v1/traffic/measurements/ — future ingest endpoint)
    ▼
TrafficMeasurement (append-only, high-volume)
    │  (background aggregation job)
    ▼
TrafficFlowSummary (analytics)
```

The AI service is a **separate process** (see `ai-services/` directory). It writes structured data to the Django API rather than accessing the database directly. This keeps the AI boundary clean.

### 2. Violation Detection Flow

```
Camera
    │  (image/video stream)
    ▼
AI Vehicle Detection Service
    │  (detected plate, speed, violation type → POST /api/v1/violations/)
    ▼
TrafficViolation (append-only)
    │  associated with
    ├── ViolationEvidence (images/video refs)
    └── Vehicle (looked up or created)
         │  (Law Enforcement review)
         ▼
        Citation (issued)
             │
             ▼
           Fine (created by Payment/Fines Officer)
                │
                ▼
             Payment (received)
```

### 3. Authentication Flow (existing)

```
Client
    │  POST /api/v1/auth/login/
    ▼
Django (LoginView)
    ├── TokenObtainPairSerializer → JWT issued
    └── AuditEvent (auth.login.success / auth.login.failure)
```

### 4. Traffic Signal Control Flow

```
Traffic Control Officer
    │  PATCH /api/v1/traffic/signals/{id}/phase/
    ▼
Django (SignalPhaseView) — IsTrafficControlOfficer permission
    ├── TrafficSignal.phase updated
    ├── AuditEvent (traffic.signal.phase_changed)
    └── Notification (if configured)
         │
         ▼  (future: WebSocket push)
        Connected dashboards
```

### 5. Administrative Flow (existing)

```
System Administrator
    │  POST /api/v1/auth/users/{id}/roles/
    ▼
Django (UserRoleAssignView) — IsSystemAdmin permission
    ├── RoleService.assign_role()
    └── AuditEvent (admin.role.assigned)
```

---

## Write Paths

| Domain | Write Volume | Write Pattern | Notes |
|---|---|---|---|
| Authentication | Low | Interactive | Already implemented |
| Audit | Medium | Synchronous tail | Already implemented — consider async for high-load |
| Roads / Cameras | Very Low | Admin CRUD | Infrequent reference data changes |
| Traffic Signals | Low | Interactive | Officer-triggered or scheduled |
| Traffic Measurements | Very High | Bulk ingest | **Must be buffered/async for production** |
| Violations | Medium | AI-generated + human | Idempotent write with deduplication key recommended |
| Payments | Low | Interactive | Financial integrity rules — use DB transactions |
| Analytics | Low | Background jobs | Written by cron/Celery tasks, never by web requests |

---

## Read Paths

| Consumer | Primary Data | Pattern |
|---|---|---|
| Traffic Control Officer | Live signal state, current incidents | Polling or future WebSocket |
| Traffic Analyst | Historical measurements, flow summaries | REST pagination |
| Law Enforcement | Violation list, citation status | REST pagination with strict ACL |
| Payment/Fines Officer | Outstanding fines, payment history | REST pagination |
| Public API (future) | Traffic advisories, incident alerts | REST, possibly CDN-cached |
| AI Services | Camera feeds, road geometry | Direct DB read via service account |

---

## Transaction Boundaries

- Road/camera/signal configuration changes: **single DB transaction**, audited.
- Violation creation with evidence: **single DB transaction** (violation + evidence atomically).
- Fine + payment: **single DB transaction** (payment recorded atomically, fine status updated).
- Traffic measurement ingest: **bulk insert without per-row transaction** (for throughput).
- Audit event writes: **best-effort** — audit failures must never roll back the business transaction.

---

## Future Infrastructure Considerations

### Time-series measurements
- At production scale, `TrafficMeasurement` rows will number in the billions.
- Recommendation: use PostgreSQL table partitioning (by `timestamp`, monthly partitions) initially.
- Future migration path: TimescaleDB extension or a dedicated time-series store (InfluxDB, ClickHouse).

### Audit event volume
- Audit events grow linearly with user activity. At scale, consider:
  - PostgreSQL partitioning by month.
  - Offloading cold audit data to object storage (S3) after 90 days.

### Read performance
- Analytics queries on large measurement tables must use pre-aggregated summaries.
- Never run aggregate queries against `TrafficMeasurement` in the web request cycle.
