# Audit Logging Architecture

## Status

**Implemented** — Phase 3E complete.
Read-only audit API available at `/api/v1/audit/events/` (System Admin only).

---

## Purpose

The audit log records security-sensitive and operationally significant actions
performed by users or automated processes.  It provides a tamper-evident trail
for compliance, forensic investigation, and operational monitoring.

---

## Events to Record

| Category | Events |
|---|---|
| Authentication | Login (success), Login (failure), Logout, Token refresh |
| Account management | Password change, Email change, Account enable/disable |
| Role / permission changes | Group added to user, Group removed from user, Permission change |
| Sensitive data access | Violation record viewed, Payment record viewed, Face recognition query |
| Administrative actions | User created, User deleted, System configuration changed |
| Camera / sensor | Camera added, Camera deleted, Camera status changed |

---

## Minimum Audit Event Fields

Every event must capture:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique event identifier |
| `timestamp` | datetime (UTC) | When the event occurred |
| `actor_id` | int / null | User who triggered the event (null = system/anonymous) |
| `actor_username` | str / null | Snapshot of username at event time |
| `action` | str | Machine-readable action code, e.g. `auth.login.success` |
| `target_type` | str / null | Content type of the affected object, e.g. `accounts.user` |
| `target_id` | str / null | PK of the affected object |
| `ip_address` | str / null | Client IP (IPv4 or IPv6) |
| `user_agent` | str / null | Client user-agent string |
| `outcome` | enum | `success` \| `failure` \| `denied` |
| `detail` | JSON / null | Optional extra context (never store secrets) |

---

## Proposed Location

Audit logging will live in a dedicated app:

```
apps/audit/
  models/
    __init__.py    # AuditEvent model
  services/
    __init__.py    # log_event() helper
  admin.py         # Read-only admin view
  apps.py
  migrations/
```

The `apps.common` app will expose a lightweight `log_audit_event()` helper
that all other apps call — keeping the audit dependency one-directional
(`accounts` → `audit`, never `audit` → `accounts`).

---

## Integration Points

- **Authentication views** (Phase 3B): call `log_audit_event` on login, logout, failed login.
- **Django signals**: connect `user_logged_in`, `user_logged_out`, `user_login_failed` signals.
- **Admin actions**: override `save_model` / `delete_model` in admin classes.
- **Sensitive API views**: call `log_audit_event` in view or a DRF permission class hook.

---

## Storage Considerations

- Audit records are **append-only** — no update or delete operations.
- For the initial implementation, store in the primary PostgreSQL database.
- For high-volume deployments, consider routing audit writes to a separate
  database or to an external logging pipeline (e.g. ELK, CloudWatch).
- Index on `(timestamp, actor_id, action)` for typical query patterns.

---

## Security Considerations

- Never store plaintext passwords, tokens, or other secrets in `detail`.
- IP address logging must comply with applicable privacy regulations.
- Audit records must not be accessible via the public API.
- Admin UI for audit records must be read-only.
