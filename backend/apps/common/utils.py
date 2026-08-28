"""
Common utility functions for the AI-Powered Smart Traffic Management System.

Shared helper functions used across multiple apps.
"""

import uuid
from datetime import datetime, timezone


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return the current UTC datetime as a timezone-aware object."""
    return datetime.now(tz=timezone.utc)


def format_datetime(dt: datetime) -> str:
    """Format a datetime object to ISO 8601 string with UTC timezone."""
    if dt is None:
        return None
    return dt.isoformat()


def truncate_string(value: str, max_length: int = 255) -> str:
    """Truncate a string to a maximum length, appending ellipsis if truncated."""
    if not value or len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def build_absolute_uri(request, path: str) -> str:
    """Build an absolute URI from a request object and a relative path."""
    return request.build_absolute_uri(path)
