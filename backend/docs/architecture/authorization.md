# Authorization Architecture

## Status

Implemented and verified in Phase 3C.

---

## Two-Layer Authorization Model

All role-management and user-administration operations are protected by
**two independent authorization layers**.  Both must pass for a privileged
operation to succeed.

### Layer 1 — View-level permission check (`IsSystemAdmin`)

Every admin view declares:

```python
permission_classes = [IsAuthenticated, IsSystemAdmin]
```

`IsSystemAdmin` (defined in `apps.accounts.permissions`) rejects any caller
who is not a verified System Administrator or Django superuser **before any
business logic runs**.  Unauthenticated callers receive HTTP 401; authenticated
non-admins receive HTTP 403.

### Layer 2 — Service-level validation (`RoleService`)

`RoleService` (defined in `apps.accounts.services`) enforces two additional
invariants regardless of who calls it:

| Guard | Exception raised | Effect |
|---|---|---|
| Role name must be in `ALL_ROLES` | `InvalidRoleError` | Rejects arbitrary group names |
| Actor and target must be different users | `SelfElevationError` | Prevents self-privilege-escalation |

---

## Why Both Layers?

### "Why not just rely on the view layer?"

The view layer is correct today, but **it is not the final enforcement
boundary**.  If a future background task, management command, or test fixture
calls `RoleService` directly without going through a view, there is no
automatic guarantee that the caller passed through `IsSystemAdmin`.

The service layer provides a **defence-in-depth** backstop:

- Self-modification is always blocked at the service layer, even if called
  from a context that has no concept of HTTP permissions.
- Arbitrary group names are always rejected, preventing SQL injection via
  `Group.objects.get(name=...)` with an attacker-controlled string.

### "Why not just rely on the service layer?"

The service layer does **not** check whether the actor has the
System Administrator role.  That check belongs at the boundary (the view),
because the service operates on the assumption that the *caller has already
been authorized*.  Duplicating role-membership checks in the service would
couple business logic to the permission model unnecessarily.

---

## Decision

**Maintain the two-layer model.**

- Layer 1 (view): checks *who* is calling.
- Layer 2 (service): checks *what* is being requested.

This is a standard separation of concerns:
- Authorization (who) at the boundary.
- Validation and invariants (what) in the domain layer.

---

## Superuser Behavior

Django superusers pass `IsSystemAdmin` implicitly (the permission class
checks `request.user.is_superuser` before checking group membership).
Superusers are therefore able to access all admin endpoints without being
explicitly assigned the `System Administrator` group.

This behavior is tested in `test_admin_users.py`.

---

## Future Considerations

When audit logging is implemented (Phase 3E+), role-change events should be
recorded **inside `RoleService`** rather than in the view.  This ensures that
every code path that mutates role membership — including future management
commands — produces an audit trail automatically.
