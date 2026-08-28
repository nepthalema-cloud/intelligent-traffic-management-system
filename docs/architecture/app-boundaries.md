# Django App Boundaries

## Status

Phase 4A — Architecture design. No business models implemented yet.

---

## Design Principles

1. **One app per primary bounded context.** Each app owns a coherent set of models and is the single authority for writing to them.
2. **Dependency direction is explicit.** Apps at lower layers must not import from apps at higher layers.
3. **Avoid micro-apps.** Related concepts that share a lifecycle and ownership should live in the same app.
4. **Separate operational from analytical.** High-volume time-series data must not block transactional writes.
5. **Role isolation follows app boundaries.** Each app maps to a primary actor role.

---

## Current Apps

```
apps/
├── accounts/     ← User, JWT auth, RBAC                      [Implemented]
├── audit/        ← AuditEvent (append-only)                  [Implemented]
├── common/       ← Shared utilities, pagination, responses   [Implemented]
├── core/         ← Health, system checks                     [Implemented]
├── cameras/      ← Camera, Sensor, health data               [Stub]
├── roads/        ← Road, RoadSegment, Intersection, Lane      [Stub]
└── traffic/      ← Signals, measurements, events, incidents  [Stub]
```

---

## Proposed Future Apps

```
apps/
├── violations/   ← Vehicle, TrafficViolation, Evidence, Citation  [Future]
├── payments/     ← Fine, Payment, PaymentMethod                   [Future]
├── analytics/    ← Pre-aggregated summaries, reports              [Future]
└── notifications/← Outbound alerts, templates                     [Future]
```

---

## Why These Boundaries?

### `roads` — Infrastructure Reference Data
- Road/segment/intersection data is reference data used by many other apps.
- Changes are infrequent and authoritative (comes from GIS/mapping systems).
- Primary actor: System Administrator.
- Separating it avoids coupling traffic operational data to GIS maintenance.

### `cameras` — Device Management
- Camera and Sensor devices have a distinct lifecycle (procurement → deployment → maintenance → decommission).
- The Camera/Sensor Technician role owns this domain exclusively.
- Health monitoring data is high-frequency operational noise — it must not pollute the core traffic domain.
- Separating cameras from traffic keeps the Traffic Control Officer's view clean.

### `traffic` — Operational Traffic State
- Traffic signals, live measurements, events, and incidents are tightly coupled by the Traffic Control Officer's workflow.
- `TrafficMeasurement` is time-series data; it should be partitioned or archived separately but logically belongs to the traffic domain.
- This is the highest-traffic (writes/reads) app in the system.

### `violations` — Enforcement Records
- Violation records have legal significance: they are append-only, evidence-linked, and access-restricted.
- Combining violations with traffic would couple enforcement access controls to operational controls.
- The Law Enforcement role is the primary actor here.

### `payments` — Financial Records
- Payments are financial records requiring PCI DSS-aware handling.
- Separating from violations allows independent audit and access control (Payment/Fines Officer).
- Payment data must never be readable by Traffic Control Officers or Analysts.

### `analytics` — Read Replicas and Aggregates
- Analytical summaries are populated by background jobs from source data.
- Keeping them separate prevents long-running analytical queries from locking operational tables.
- Future: can be pointed at a read replica or a data warehouse.

### `notifications` — Outbound Messaging
- Notifications are a side-effect of other domains, not a primary entity.
- Separating them allows the notification system to be swapped (email → push → SMS) without touching domain logic.

---

## Dependency Graph

```
accounts ←── (all apps reference User for actor/ownership)
   │
   ▼
audit ←──────── (all apps call log_audit_event)
   │
common ←──────── (all apps use pagination, responses, exceptions)
   │
roads ←────────── cameras, traffic, violations
   │
cameras ──────────────────────► traffic (provides measurement inputs)
   │
traffic ──────────────────────► violations (violation references segment/event)
   │                            analytics (reads traffic data)
violations ────────────────────► payments (fine references citation)
   │
payments ──────────────────────► analytics (reads payment data)
   │
notifications ←──────────────── traffic, violations (trigger notifications)
```

**Rule**: Arrows indicate allowed import direction. Reverse imports are forbidden.

---

## Apps NOT to Create

| Rejected concept | Reason |
|---|---|
| `apps.signals` | Traffic signals logically belong in `apps.traffic` — same actor, same lifecycle |
| `apps.vehicles` | Vehicles are enforcement reference data; they belong in `apps.violations` |
| `apps.drivers` | Driver identity is PII managed through violations; not a standalone domain |
| `apps.events` (generic) | Too broad; traffic events live in `apps.traffic`, system events in `apps.audit` |
| `apps.ai` | AI is a service boundary, not a data domain; see `ai-integration.md` |
| `apps.reports` | Reports are views into analytics data; not a separate model domain |
