"""
Custom exceptions for the AI-Powered Smart Traffic Management System.

These exception classes are used across multiple apps to provide
consistent error handling and HTTP response codes.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class ServiceUnavailableError(APIException):
    """Raised when an external service or dependency is unavailable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable. Please try again later."
    default_code = "service_unavailable"


class ValidationError(APIException):
    """Raised when input validation fails at the service layer."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input data."
    default_code = "validation_error"


class NotFoundError(APIException):
    """Raised when a requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource was not found."
    default_code = "not_found"


class ConflictError(APIException):
    """Raised when a request conflicts with the current state of a resource."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "A conflict occurred with the current state of the resource."
    default_code = "conflict"


class PermissionDeniedError(APIException):
    """Raised when a user does not have permission to perform an action."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"
