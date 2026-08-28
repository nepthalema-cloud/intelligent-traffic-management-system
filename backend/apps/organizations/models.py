from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Region(models.Model):
    """Administrative region for traffic operations and reporting."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "organizations"
        verbose_name = "Region"
        verbose_name_plural = "Regions"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    """City within a region, used for scope restriction and operational assignment."""

    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="cities",
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, default="")
    latitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "organizations"
        verbose_name = "City"
        verbose_name_plural = "Cities"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["region", "code"], name="uniq_city_code_per_region"),
            models.UniqueConstraint(fields=["region", "name"], name="uniq_city_name_per_region"),
        ]

    def __str__(self) -> str:
        return self.name


class TrafficControlCenter(models.Model):
    """Operational authority scope: city, regional, or central coordination point."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=80, unique=True)
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="control_centers",
        null=True,
        blank=True,
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="control_centers",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "organizations"
        verbose_name = "Traffic Control Center"
        verbose_name_plural = "Traffic Control Centers"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ScopeAssignedMixin(models.Model):
    """Reusable mixin for objects that belong to a geographic/administrative scope."""

    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s",
        null=True,
        blank=True,
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s",
        null=True,
        blank=True,
    )
    control_center = models.ForeignKey(
        TrafficControlCenter,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class UserScope(models.Model):
    """Optional user scope assignment to support geographic authorization constraints."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scope_assignment",
    )
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_assignments")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_assignments")
    control_center = models.ForeignKey(TrafficControlCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_assignments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "organizations"
        verbose_name = "User Scope"
        verbose_name_plural = "User Scopes"

    def __str__(self) -> str:
        return f"Scope for {self.user}"
