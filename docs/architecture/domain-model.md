# Domain Model

## Status

Phase 4A — Architecture design only. No models implemented yet.

---

## Existing Foundation (Implemented)

| App | Purpose | Status |
|---|---|---|
| `apps.accounts` | User model, JWT auth, RBAC | ✅ Implemented |
| `apps.audit` | Append-only audit event log | ✅ Implemented |
| `apps.common` | Shared utilities, pagination, responses | ✅ Implemented |
| `apps.core` | Health endpoint, system checks | ✅ Implemented |

---

## Proposed Domain Apps

### `apps.roads` (existing stub)

**Purpose**: Static infrastructure — the physical road network.

This is foundational reference data. Most other domains reference roads but do not own them.

**Core entities**:

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `Road` | A named road (e.g. "Main Street"). Metadata only. | Mutable | Yes — creation, name change |
| `RoadSegment` | A directed portion of a road between two intersections. Carries speed limits, lane counts, geometry. | Mutable | Yes — speed limit changes |
| `Intersection` | A point where two or more road segments meet. Named for operational reference. | Mutable | Yes — configuration changes |
| `Lane` | A single lane within a road segment. Includes type (travel, turn, bus, cycle). | Mutable | Yes |

**Key relationships**:
- `RoadSegment` belongs to one `Road`; connects two `Intersection` records (start/end)
- `Intersection` has many `RoadSegment` entries (incoming and outgoing)
- `Lane` belongs to one `RoadSegment`

**Ownership**: System Administrator creates/modifies. Traffic Analyst reads.

---

### `apps.traffic` (existing stub)

**Purpose**: Operational traffic state — signals, live measurements, events.

Subdivided conceptually into:

1. **Traffic signals** — configuration and real-time state
2. **Traffic measurements** — sensor/camera-derived flow data (high-volume, time-series)
3. **Traffic events** — human-created or AI-detected notable occurrences
4. **Traffic incidents** — verified incidents requiring active management

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `TrafficSignal` | A physical signal controller at an intersection or on a segment. | Mutable | Yes — config changes, enable/disable |
| `SignalPhase` | A configured timing phase (green/yellow/red durations) belonging to a signal. | Mutable | Yes |
| `TrafficMeasurement` | A single sensor reading (vehicle count, speed, occupancy). High-volume, time-series. | Append-only | No (volume too high) |
| `TrafficEvent` | An operator-created or AI-flagged notable event (e.g. congestion detected). | Mutable | Yes |
| `TrafficIncident` | A verified incident (accident, road closure) being actively managed. | Mutable with lifecycle | Yes — state transitions |

**Key relationships**:
- `TrafficSignal` is located at an `Intersection` or on a `RoadSegment`
- `SignalPhase` belongs to `TrafficSignal`
- `TrafficMeasurement` references the originating `Camera` or `Sensor` and the `RoadSegment`
- `TrafficEvent` may reference a `RoadSegment` or `Intersection`
- `TrafficIncident` may reference multiple `RoadSegment` records (closure span)

---

### `apps.cameras` (existing stub)

**Purpose**: Physical cameras and their configuration. Logically distinct from traffic data because camera management requires a separate role (Camera/Sensor Technician) and different lifecycle rules.

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `Camera` | A physical traffic camera. Location, model, IP, stream URL. | Mutable | Yes — add, remove, config change, enable/disable |
| `CameraHealth` | Latest health/status snapshot (online, offline, degraded). | Replace-latest | No (operational noise) |
| `Sensor` | A non-camera sensor (inductive loop, radar, LiDAR). | Mutable | Yes — add, remove, enable/disable |
| `SensorHealth` | Latest health/status snapshot for a sensor. | Replace-latest | No |

**Key relationships**:
- `Camera` and `Sensor` are associated with a `RoadSegment` or `Intersection`
- `Camera` feeds data to `TrafficMeasurement` and potentially to AI services
- `Sensor` feeds data to `TrafficMeasurement`

---

### `apps.violations` (not yet created)

**Purpose**: Traffic enforcement — violations detected by camera/sensor AI or entered by officers.

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `Vehicle` | A registered vehicle (plate number, type, registration data). | Mutable | Yes — data changes |
| `TrafficViolation` | A recorded violation (type, time, location, vehicle, evidence). | Append-only (legal record) | Yes — every access, dispute, status change |
| `ViolationEvidence` | Images, video clips, sensor readings attached to a violation. | Append-only | Yes |
| `Citation` | A formal citation issued for a violation. References a violation. | Mutable with lifecycle (issued → contested → adjudicated) | Yes — every state transition |

**Sensitive data**: Plate numbers, driver identity, evidence images. Access restricted to Law Enforcement and System Administrator.

---

### `apps.payments` (not yet created)

**Purpose**: Fine management and payment processing.

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `Fine` | A financial penalty associated with a `Citation`. | Mutable with lifecycle (pending → paid → waived → overdue) | Yes — every state transition |
| `Payment` | A recorded payment event. | Append-only (financial record) | Yes — creation, reversal |
| `PaymentMethod` | Payment channel metadata (reference only, no raw card data). | Mutable | Yes |

**Sensitive data**: Payment amounts, reference numbers. Access restricted to Payment/Fines Officer and System Administrator.

---

### `apps.analytics` (future, not yet created)

**Purpose**: Pre-aggregated analytics and reporting data. Populated by background jobs, not real-time writes.

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `TrafficFlowSummary` | Hourly/daily aggregated flow per segment. | Append-only | No |
| `IncidentReport` | Summarized incident statistics per area/period. | Append-only | No |
| `ViolationSummary` | Aggregated violation counts by type/location/period. | Append-only | No |

---

### `apps.notifications` (future, not yet created)

**Purpose**: Outbound notifications for operational events (incidents, signal faults, system alerts).

| Entity | Purpose | Mutability | Audit |
|---|---|---|---|
| `Notification` | An outbound message (email, SMS, push) sent to a user or group. | Append-only | Selected |
| `NotificationTemplate` | Configurable message templates. | Mutable | Yes |

---

## Entity Relationship Summary

```
Road
 └── RoadSegment (many)
       ├── Lane (many)
       ├── Camera (many)
       ├── Sensor (many)
       ├── TrafficMeasurement (many, time-series)
       └── TrafficEvent / TrafficIncident

Intersection
 ├── RoadSegment (many — incoming/outgoing)
 └── TrafficSignal (many)
       └── SignalPhase (many)

Camera / Sensor
 ├── CameraHealth / SensorHealth (one latest)
 └── TrafficMeasurement (many)

Vehicle
 └── TrafficViolation (many)
       ├── ViolationEvidence (many)
       └── Citation (one)
             └── Fine (one)
                   └── Payment (many)

User (accounts.User)
 ├── TrafficIncident (created_by)
 ├── TrafficEvent (created_by)
 └── AuditEvent (actor)
```
