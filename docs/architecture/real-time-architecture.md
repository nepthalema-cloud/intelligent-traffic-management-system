# Real-Time Architecture

## Status

Phase 4A — Analysis and recommendation. Not yet implemented.

---

## Requirements Analysis

| Use Case | Update Frequency | Consumer | Latency Requirement |
|---|---|---|---|
| Live traffic signal state | Per phase change (seconds) | Traffic Control Officers, dashboards | < 2s |
| Sensor measurement ingestion | Every 30–60s per sensor | Backend storage | < 30s |
| Camera event ingestion | Per detection event (seconds) | Backend, AI services | < 5s |
| Traffic incident alerts | On incident creation/update | Officers, public (selected) | < 10s |
| System health monitoring | Every 60s | Technicians, admins | < 60s |

---

## Current Architecture Capabilities

The current Django request/response architecture (DRF + PostgreSQL) handles:
- ✅ REST API reads and writes
- ✅ JWT authentication
- ✅ Role-based access control
- ✅ Synchronous audit logging
- ❌ Push notifications to connected clients
- ❌ Sub-second event streaming
- ❌ High-throughput bulk sensor ingestion

---

## Recommendation by Use Case

### Sensor and Camera Data Ingestion

**Recommended approach: REST ingest endpoint with async write**

For Phase 4B (initial domain model implementation):
- Simple `POST /api/v1/traffic/measurements/` endpoint.
- Use bulk insert (`bulk_create`) rather than per-row saves.
- Run synchronously for now; add Celery task queue when ingestion volume exceeds ~1,000 writes/second.

For production scale:
- Introduce a lightweight message broker (Redis Streams or RabbitMQ) between AI services and Django.
- Django consumes from the queue asynchronously, decoupling ingestion latency from write throughput.
- This avoids modifying the AI service interface (it still POSTs to REST).

### Live Traffic Signal and Incident Updates

**Recommended approach: Django Channels (WebSocket)**

- Traffic Control Officers require push updates without polling.
- Django Channels adds WebSocket support to Django with minimal architecture change.
- A `signals` and `incidents` channel group per geographic zone broadcasts updates.
- Implementation deferred to Phase 5+ (after domain models are stable).
- Until then, polling (`GET /api/v1/traffic/signals/` every 5s) is acceptable for the dashboard.

### Outbound Incident Notifications

**Recommended approach: Celery task + notification service**

- When a `TrafficIncident` is created or its state changes, a Celery task sends outbound notifications (email, SMS, push).
- Celery + Redis is the standard Django choice; it is already in the infrastructure plan (Redis is referenced in `.env.example`).
- The `apps.notifications` domain handles template rendering and delivery tracking.

### Public Traffic Alerts

**Recommended approach: REST polling + CDN caching**

- Public users need read-only access to selected traffic advisories.
- No authentication required; data is non-sensitive.
- A CDN (Cloudflare, CloudFront) can cache `GET /api/v1/traffic/events/?public=true` for 30–60 seconds.
- This eliminates read load from the Django application tier entirely for public consumers.

---

## Infrastructure Phases

| Phase | Capability | Technology |
|---|---|---|
| Phase 4B–4D | REST ingestion, REST polling | Django + PostgreSQL (current) |
| Phase 5 | Push updates to Officers | Django Channels + Redis |
| Phase 5 | Async ingest queue | Celery + Redis |
| Phase 6 | High-throughput measurements | PostgreSQL partitioning or TimescaleDB |
| Future | Public CDN caching | CloudFront / Cloudflare |

---

## Technology Decisions Deferred

The following decisions are deferred until Phase 5:

1. **WebSocket vs Server-Sent Events**: WebSocket is bidirectional (needed for signal control). SSE is sufficient for read-only dashboards. Choose based on dashboard requirements.
2. **Redis vs RabbitMQ**: Redis Streams is simpler and already in the stack. RabbitMQ provides stronger delivery guarantees. Choose when ingest volume is known.
3. **Django Channels vs separate WebSocket service**: Django Channels adds complexity to the Django process. A separate Node.js or Go WebSocket gateway may be preferable at scale.
4. **TimescaleDB vs partitioned PostgreSQL**: Partitioned PostgreSQL is zero-dependency. TimescaleDB adds a PostgreSQL extension. Decide when measurement volume is characterized.

---

## Current Action

No changes to the current architecture are required in Phase 4A or 4B.
The existing synchronous REST + PostgreSQL stack is correct for the initial domain model implementation.
Real-time infrastructure will be added incrementally as traffic volume is characterized in testing.
