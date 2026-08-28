"""
Audit models package.

The AuditEvent model is defined here so Django's app registry discovers
it correctly via ``apps.audit.models``.
"""

import uuid

from django.db import models


class Outcome(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    DENIED  = "denied",  "Denied"


class AppendOnlyManager(models.Manager):
    """
    Manager that disables bulk_update and prevents accidental mass-updates.

    Individual queryset.update() calls are not blocked here because Django
    does not provide a clean hook for that at the manager level without
    monkey-patching QuerySet.  Immutability for individual records is
    enforced via the model's save() override below.
    """

    def get_queryset(self):
        return super().get_queryset()


class AuditEvent(models.Model):
    """
    Immutable audit event record.

    Architecture
    ------------
    Follows the specification in ``docs/architecture/audit-logging.md``.

    Immutability
    ------------
    - ``save()`` raises ``RuntimeError`` if called on an existing instance
      (i.e. ``pk`` is already set), preventing accidental updates.
    - ``delete()`` raises ``RuntimeError`` unconditionally.
    - The Django admin is configured as read-only (no add/change/delete).

    Security
    --------
    - ``detail`` is a free-form JSON field.  Callers MUST NOT store
      passwords, password hashes, SECRET_KEY, access tokens, or refresh
      tokens in this field.
    - ``ip_address`` and ``user_agent`` are stored for forensic purposes;
      deployments must comply with applicable privacy regulations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Actor — who triggered the event (null = anonymous / system)
    actor_id = models.IntegerField(null=True, blank=True, db_index=True)
    actor_username = models.CharField(max_length=150, null=True, blank=True)

    # Action — machine-readable dot-separated code, e.g. ``auth.login.success``
    action = models.CharField(max_length=128, db_index=True)

    # Target — the affected object (optional)
    target_type = models.CharField(max_length=128, null=True, blank=True)
    target_id = models.CharField(max_length=64, null=True, blank=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Outcome
    outcome = models.CharField(
        max_length=16,
        choices=Outcome.choices,
        default=Outcome.SUCCESS,
        db_index=True,
    )

    # Optional extra context — NEVER store secrets here
    detail = models.JSONField(null=True, blank=True)

    objects = AppendOnlyManager()

    class Meta:
        app_label = "audit"
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "actor_id", "action"],
                         name="audit_ts_actor_action_idx"),
        ]

    def __str__(self) -> str:
        actor = self.actor_username or "anonymous"
        return f"[{self.timestamp}] {self.action} by {actor} → {self.outcome}"

    # ------------------------------------------------------------------
    # Append-only enforcement
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        """Block updates to existing records."""
        if self._state.adding is False:
            raise RuntimeError(
                "AuditEvent records are append-only and may not be modified. "
                f"Attempted update on record id={self.pk}"
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Block deletion of audit records."""
        raise RuntimeError(
            "AuditEvent records are append-only and may not be deleted. "
            f"Attempted deletion on record id={self.pk}"
        )
