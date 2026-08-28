"""
Custom validators for the AI-Powered Smart Traffic Management System.

Reusable validation functions and classes used across multiple apps.
"""

import re

from django.core.exceptions import ValidationError


def validate_non_empty_string(value: str) -> None:
    """Raise ValidationError if the value is an empty or whitespace-only string."""
    if not value or not value.strip():
        raise ValidationError("This field may not be blank.")


def validate_positive_integer(value: int) -> None:
    """Raise ValidationError if the value is not a positive integer."""
    if value is None or value <= 0:
        raise ValidationError("This field must be a positive integer.")


def validate_non_negative_number(value) -> None:
    """Raise ValidationError if the value is negative."""
    if value is None or value < 0:
        raise ValidationError("This field must be zero or a positive number.")


def validate_latitude(value: float) -> None:
    """Raise ValidationError if the value is not a valid latitude (-90 to 90)."""
    if value is None or not (-90.0 <= value <= 90.0):
        raise ValidationError("Latitude must be between -90 and 90 degrees.")


def validate_longitude(value: float) -> None:
    """Raise ValidationError if the value is not a valid longitude (-180 to 180)."""
    if value is None or not (-180.0 <= value <= 180.0):
        raise ValidationError("Longitude must be between -180 and 180 degrees.")


def validate_slug_format(value: str) -> None:
    """Raise ValidationError if the value contains characters not allowed in a slug."""
    pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    if not pattern.match(value):
        raise ValidationError(
            "Enter a valid slug consisting of lowercase letters, numbers, and hyphens."
        )
