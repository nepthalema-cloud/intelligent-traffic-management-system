from django.core.validators import MinValueValidator
from django.db import models


class Fine(models.Model):
    """Fine issued from a recorded violation. The underlying violation remains append-only."""

    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    VALID_TRANSITIONS = {
        Status.UNPAID: [Status.PENDING, Status.CANCELLED, Status.PAID],
        Status.PENDING: [Status.PAID, Status.FAILED, Status.CANCELLED],
        Status.PAID: [Status.REFUNDED],
        Status.FAILED: [Status.PENDING, Status.CANCELLED],
        Status.CANCELLED: [],
        Status.REFUNDED: [],
    }

    violation = models.OneToOneField(
        "violations.TrafficViolation",
        on_delete=models.PROTECT,
        related_name="fine",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID, db_index=True)
    reference = models.CharField(max_length=80, unique=True, db_index=True)
    notes = models.TextField(blank=True, default="")
    issued_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "fines"
        verbose_name = "Fine"
        verbose_name_plural = "Fines"
        ordering = ["-issued_at"]

    def transition_to(self, new_status: str):
        if new_status not in self.Status.values:
            raise ValueError(f"Invalid fine status: {new_status}")
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        return self

    def __str__(self) -> str:
        return f"Fine #{self.pk} - {self.status}"


class Payment(models.Model):
    """Payment record created for a fine. Status transitions are validated internally."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    VALID_TRANSITIONS = {
        Status.PENDING: [Status.PAID, Status.FAILED, Status.CANCELLED],
        Status.PAID: [Status.REFUNDED],
        Status.FAILED: [Status.PENDING, Status.CANCELLED],
        Status.CANCELLED: [],
        Status.REFUNDED: [],
    }

    fine = models.ForeignKey(Fine, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_reference = models.CharField(max_length=120, unique=True, db_index=True)
    payment_method = models.CharField(max_length=40, blank=True, default="")
    provider = models.CharField(max_length=80, blank=True, default="")
    provider_reference = models.CharField(max_length=160, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "fines"
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def transition_to(self, new_status: str):
        if new_status not in self.Status.values:
            raise ValueError(f"Invalid payment status: {new_status}")
        # Business rule: only allow marking a payment as PAID when the
        # associated fine is already in PENDING state. This prevents
        # payments being applied before a fine has been issued/approved.
        if new_status == self.Status.PAID and getattr(self.fine, "status", None) != Fine.Status.PENDING:
            raise ValueError("Cannot mark payment as paid when fine is not pending")

        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        return self

    def __str__(self) -> str:
        return f"Payment {self.payment_reference} - {self.status}"
