from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Driver(models.Model):
    """Minimal driver registry used to link violations to an identified driver when available."""

    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    driver_identifier = models.CharField(max_length=120, blank=True, default="")
    license_number = models.CharField(max_length=80, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(max_length=254, blank=True, default="")
    license_status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
            ("pending", "Pending"),
        ],
        default="active",
        db_index=True,
    )
    license_issue_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    registration_status = models.CharField(
        max_length=20,
        choices=[
            ("registered", "Registered"),
            ("unregistered", "Unregistered"),
            ("pending", "Pending"),
        ],
        default="registered",
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "drivers"
        verbose_name = "Driver"
        verbose_name_plural = "Drivers"
        ordering = ["last_name", "first_name"]
        # Some runtime environments may use older Django versions where
        # CheckConstraint signature differs. Use an empty constraints list
        # here to preserve compatibility across developer machines while
        # keeping the logical validation in unit tests or service layer.
        constraints = []

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_name, self.last_name] if part).strip()

    def __str__(self) -> str:
        return self.full_name or self.license_number
