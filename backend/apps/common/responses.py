"""
Standardised API response helpers for the AI-Powered Smart Traffic Management System.

All API views should use these helpers to produce consistent response envelopes.
"""

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK,
) -> Response:
    """
    Return a standardised success response.

    Shape::

        {
            "success": true,
            "message": "...",
            "data": { ... }
        }
    """
    payload = {
        "success": True,
        "message": message,
        "data": data,
    }
    return Response(payload, status=status_code)


def created_response(data: Any = None, message: str = "Created successfully") -> Response:
    """Convenience wrapper for HTTP 201 Created responses."""
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def error_response(
    message: str = "An error occurred",
    errors: Any = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """
    Return a standardised error response.

    Shape::

        {
            "success": false,
            "message": "...",
            "errors": { ... }
        }
    """
    payload = {
        "success": False,
        "message": message,
        "errors": errors,
    }
    return Response(payload, status=status_code)


def not_found_response(message: str = "Resource not found") -> Response:
    """Convenience wrapper for HTTP 404 Not Found responses."""
    return error_response(message=message, status_code=status.HTTP_404_NOT_FOUND)


def no_content_response() -> Response:
    """Return HTTP 204 No Content (e.g. after a successful DELETE)."""
    return Response(status=status.HTTP_204_NO_CONTENT)
