# RBAC Permission Matrix

## Status

Phase 4A — Proposed permissions. No DRF permission classes implemented for business domains yet.

---

## Roles

| Role | Primary Responsibility |
|---|---|
| System Administrator | Full system access — user management, configuration, all data |
| Traffic Control Officer | Real-time traffic monitoring and signal control |
| Traffic Analyst | Read-only access to traffic data and analytics |
| Law Enforcement / Authorized Officer | Access to violation records and enforcement tools |
| Camera/Sensor Technician | Device management — cameras and sensors |
| Payment/Fines Officer | Fine management and payment processing |
| Public User | Public-facing data only (future: e.g. traffic advisories) |

---

## Permission Matrix

Legend: `C` = Create, `R` = Read, `U` = Update, `D` = Deactivate/Delete, `—` = No access

### Infrastructure (roads app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Road | CRUD | R | R | — | — | — | — |
| Road Segment | CRUD | R | R | — | — | — | — |
| Intersection | CRUD | R | R | — | — | — | — |
| Lane | CRUD | R | R | — | — | — | — |

### Devices (cameras app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Camera | CRUD | R | R | — | CRUD | — | — |
| Camera Health | CRUD | R | R | — | CRUD | — | — |
| Sensor | CRUD | R | R | — | CRUD | — | — |
| Sensor Health | CRUD | R | R | — | CRUD | — | — |

### Traffic Operations (traffic app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Traffic Signal config | CRUD | CRU | R | — | R | — | — |
| Signal Phase | CRUD | CRU | R | — | R | — | — |
| Traffic Measurement | CRUD | R | R | — | R | — | — |
| Traffic Event | CRUD | CRU | R | R | — | — | R (selected) |
| Traffic Incident | CRUD | CRUD | R | R | — | — | R (selected) |

### Violations & Enforcement (violations app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Vehicle record | CRUD | — | — | CRUD | — | R | — |
| Traffic Violation | CRUD | — | R (aggregated) | CRUD | — | R | — |
| Violation Evidence | CRUD | — | — | CR | — | — | — |
| Citation | CRUD | — | — | CRUD | — | R | — |

### Payments (payments app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Fine | CRUD | — | — | R | — | CRU | — |
| Payment | CRUD | — | — | R | — | CR | — |
| Payment Method | CRUD | — | — | — | — | R | — |

### Analytics (analytics app)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Traffic Flow Summary | CRUD | R | R | — | — | — | R (public) |
| Incident Report | CRUD | R | R | R | — | — | — |
| Violation Summary | CRUD | — | R | R | — | R | — |

### Audit (audit app — already implemented)

| Resource | Sys Admin | TCO | Analyst | Law Enf | Cam Tech | Pay/Fines | Public |
|---|---|---|---|---|---|---|---|
| Audit Events | R | — | — | — | — | — | — |

---

## Permission Implementation Strategy

Permissions will be implemented using:

1. **Role-based DRF permission classes** (existing `IsSystemAdmin`, `IsTrafficControlOfficer`, etc.) for coarse-grained view access.
2. **Django model-level permissions** (`add_X`, `change_X`, `delete_X`, `view_X`) for fine-grained row-level checks where needed.
3. **Custom `has_object_permission()` checks** for cases where a user can read a resource list but not individual sensitive fields.

### Sensitive-Field Filtering

Some roles may read a record but not all fields. For example:
- A Traffic Analyst may see aggregated violation counts but not individual plate numbers.
- A Payment/Fines Officer may see payment amounts but not violation evidence images.

This will be enforced via **role-aware serializer field sets** rather than multiple serializer classes where practical.

---

## Privilege Escalation Controls

Existing (implemented):
- Users cannot modify their own role membership (`SelfElevationError` in `RoleService`).
- Role names are validated against `ALL_ROLES` — arbitrary group names are rejected.

Future domains must follow the same pattern:
- Service methods that change sensitive state must accept an `actor` parameter.
- Service methods must verify the actor is not the same as the target where self-modification is a risk.
- Audit events must be emitted for all privilege-sensitive operations.
