"""
Views for the accounts app.

Current endpoints
-----------------
POST   /api/v1/auth/login/                  Obtain JWT access + refresh token pair
POST   /api/v1/auth/refresh/                Rotate refresh token, obtain new access token
POST   /api/v1/auth/logout/                 Blacklist refresh token (requires auth)
GET    /api/v1/auth/me/                     Authenticated user's own profile
GET    /api/v1/auth/users/                  Admin: list all users (paginated)
GET    /api/v1/auth/users/{id}/             Admin: retrieve a single user
POST   /api/v1/auth/users/{id}/roles/       Admin: assign a role to a user
DELETE /api/v1/auth/users/{id}/roles/{role}/Admin: remove a role from a user
PATCH  /api/v1/auth/users/{id}/status/      Admin: activate or deactivate a user

Authorization architecture
--------------------------
Authorization is enforced at TWO layers:

1. **View layer** — ``IsSystemAdmin`` permission class rejects all callers
   who are neither a System Administrator nor a superuser before any
   business logic runs.

2. **Service layer** — ``RoleService`` enforces:
   - Only whitelisted role names (``ALL_ROLES``) are accepted.
   - An actor may never modify their own role/status (self-elevation guard).

See ``docs/architecture/authorization.md`` for the full security model.

Access-token behavior after logout
-----------------------------------
Blacklisting a refresh token does NOT immediately invalidate already-issued
access tokens.  Access tokens remain valid until their natural expiry
(configured as 15 minutes in ``SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']``).

This is a fundamental property of stateless JWTs and is consistent with
SimpleJWT's design.  The 15-minute lifetime was deliberately chosen (reduced
from the initial 1-hour default) because this system has sensitive roles
(System Administrator, Law Enforcement, Traffic Control Officer) that require
a short post-logout exposure window.
"""

from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import (
    TokenBlacklistSerializer,
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from apps.accounts.permissions import IsSystemAdmin
from apps.accounts.serializers import AdminUserSerializer, UserProfileSerializer
from apps.accounts.services import InvalidRoleError, RoleService, SelfElevationError
from apps.accounts.roles import ALL_ROLES
from apps.audit.services import AuditAction, Outcome, log_audit_event
from apps.common.pagination import StandardResultsPagination
from apps.common.responses import (
    error_response,
    no_content_response,
    not_found_response,
    success_response,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# JWT: Login
# ---------------------------------------------------------------------------

class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticate with username and password.  Returns a JWT access token
    and a JWT refresh token on success.

    Authentication
    --------------
    This endpoint is public (``AllowAny``); no token is required.

    Request body
    ------------
    ::

        { "username": "alice", "password": "s3cr3t" }

    Security
    --------
    - Delegates credential validation to ``TokenObtainPairSerializer``, which
      calls Django's ``authenticate()`` internally — no custom auth logic.
    - Returns the same generic error for wrong username, wrong password, and
      inactive account to prevent user enumeration.
    - Password is never included in any response.
    - The JWT signing key is never included in any response.

    Response (HTTP 200)
    -------------------
    ::

        {
            "success": true,
            "message": "Login successful.",
            "data": {
                "access":  "<access_token>",
                "refresh": "<refresh_token>"
            }
        }

    Access-token lifetime: 15 minutes (configured in ``SIMPLE_JWT``).
    Refresh-token lifetime: 1 day (configured in ``SIMPLE_JWT``).
    """

    permission_classes = [AllowAny]
    # Explicitly disable CSRF enforcement for this token-based endpoint.
    authentication_classes = []

    # Generic message returned for ALL authentication failures.
    # Using a single message prevents user-enumeration attacks.
    _AUTH_FAILURE_MESSAGE = "Invalid credentials."

    def post(self, request: Request) -> Response:
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            log_audit_event(
                action=AuditAction.AUTH_LOGIN_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                detail={"reason": "token_error"},
            )
            return error_response(
                message=self._AUTH_FAILURE_MESSAGE,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            # AuthenticationFailed and ValidationError from DRF/SimpleJWT
            # both surface here.  Return a uniform message in all cases.
            log_audit_event(
                action=AuditAction.AUTH_LOGIN_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                detail={"reason": "invalid_credentials"},
            )
            return error_response(
                message=self._AUTH_FAILURE_MESSAGE,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # Successful login — resolve the user to populate actor fields
        user = serializer.user if hasattr(serializer, "user") else None
        log_audit_event(
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=user,
        )
        return success_response(
            data={
                "access": serializer.validated_data["access"],
                "refresh": serializer.validated_data["refresh"],
            },
            message="Login successful.",
        )


# ---------------------------------------------------------------------------
# JWT: Token refresh
# ---------------------------------------------------------------------------

class RefreshView(APIView):
    """
    POST /api/v1/auth/refresh/

    Exchange a valid refresh token for a new access token.

    Authentication
    --------------
    This endpoint is public (``AllowAny``); only the refresh token itself
    is used to authenticate the request.

    Request body
    ------------
    ::

        { "refresh": "<refresh_token>" }

    Token rotation
    --------------
    Because ``ROTATE_REFRESH_TOKENS = True`` in settings, each successful
    call to this endpoint:

    1. Issues a **new** refresh token.
    2. Blacklists the **old** refresh token (``BLACKLIST_AFTER_ROTATION=True``).

    The old refresh token cannot be reused after this call.

    Response (HTTP 200)
    -------------------
    ::

        {
            "success": true,
            "message": "Token refreshed.",
            "data": {
                "access":  "<new_access_token>",
                "refresh": "<new_refresh_token>"
            }
        }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            log_audit_event(
                action=AuditAction.AUTH_REFRESH_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                actor=request.user if request.user.is_authenticated else None,
                detail={"reason": "invalid_or_blacklisted_token"},
            )
            return error_response(
                message="Token is invalid or expired.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            log_audit_event(
                action=AuditAction.AUTH_REFRESH_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                detail={"reason": "invalid_token"},
            )
            return error_response(
                message="Token is invalid or expired.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        log_audit_event(
            action=AuditAction.AUTH_REFRESH_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=request,
        )
        data = {"access": serializer.validated_data["access"]}
        if "refresh" in serializer.validated_data:
            data["refresh"] = serializer.validated_data["refresh"]
        return success_response(data=data, message="Token refreshed.")


# ---------------------------------------------------------------------------
# JWT: Logout
# ---------------------------------------------------------------------------

class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklist the provided refresh token, effectively ending the session.

    Authentication
    --------------
    Requires a valid JWT access token in the ``Authorization: Bearer`` header.
    Unauthenticated requests receive HTTP 401.

    Request body
    ------------
    ::

        { "refresh": "<refresh_token>" }

    Security
    --------
    - The refresh token is blacklisted via SimpleJWT's
      ``TokenBlacklistSerializer``; no custom blacklist logic is used.
    - After this call the refresh token can no longer be used to obtain
      new access tokens.
    - **Access tokens remain valid until their natural expiry** (15 minutes).
      This is a fundamental property of stateless JWTs.  Clients should
      discard the access token immediately upon logout.

    Response (HTTP 200)
    -------------------
    ::

        {
            "success": true,
            "message": "Logged out successfully.",
            "data": null
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = TokenBlacklistSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            log_audit_event(
                action=AuditAction.AUTH_LOGOUT_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                actor=request.user,
                detail={"reason": "invalid_or_blacklisted_token"},
            )
            return error_response(
                message="Token is invalid, expired, or already blacklisted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            log_audit_event(
                action=AuditAction.AUTH_LOGOUT_FAILURE,
                outcome=Outcome.FAILURE,
                request=request,
                actor=request.user,
                detail={"reason": "invalid_token"},
            )
            return error_response(
                message="Token is invalid, expired, or already blacklisted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        log_audit_event(
            action=AuditAction.AUTH_LOGOUT_SUCCESS,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
        )
        return success_response(data=None, message="Logged out successfully.")


# ---------------------------------------------------------------------------
# Authenticated user's own profile
# ---------------------------------------------------------------------------

class MeView(APIView):
    """
    GET /api/v1/auth/me/

    Return the profile of the currently authenticated user.

    - Unauthenticated → 401
    - Read-only; all write methods return 405.
    - Password and hash are never returned.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)


# ---------------------------------------------------------------------------
# Admin: user list
# ---------------------------------------------------------------------------

class UserListView(APIView):
    """
    GET /api/v1/auth/users/

    Return a paginated list of all users.

    - Unauthenticated → 401
    - Non-admin authenticated → 403
    - System Administrator / superuser → 200 (paginated)

    Query parameters
    ----------------
    page        : int  — page number (default 1)
    page_size   : int  — results per page (default 20, max 100)
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get(self, request: Request) -> Response:
        queryset = (
            User.objects.all()
            .prefetch_related("groups")
            .order_by("id")
        )
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminUserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Admin: user detail
# ---------------------------------------------------------------------------

class UserDetailView(APIView):
    """
    GET /api/v1/auth/users/{id}/

    Return a single user by primary key.

    - Unauthenticated → 401
    - Non-admin authenticated → 403
    - Non-existent user → 404
    - System Administrator / superuser → 200
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get(self, request: Request, user_id: int) -> Response:
        user = get_object_or_404(User.objects.prefetch_related("groups"), pk=user_id)
        serializer = AdminUserSerializer(user)
        return success_response(data=serializer.data)


# ---------------------------------------------------------------------------
# Admin: role assignment
# ---------------------------------------------------------------------------

class UserRoleAssignView(APIView):
    """
    POST /api/v1/auth/users/{id}/roles/

    Assign a role (Django Group) to the target user.

    Request body
    ------------
    ::

        { "role": "Traffic Analyst" }

    - Unauthenticated → 401
    - Non-admin → 403
    - Non-existent user → 404
    - Invalid role name → 400
    - Self-modification → 400
    - Success → 200 with updated user representation
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def post(self, request: Request, user_id: int) -> Response:
        target = get_object_or_404(User.objects.prefetch_related("groups"), pk=user_id)

        role_name = request.data.get("role", "").strip()
        if not role_name:
            return error_response(
                message="The 'role' field is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RoleService.assign_role(actor=request.user, target=target, role_name=role_name)
        except InvalidRoleError as exc:
            return error_response(
                message=str(exc),
                errors={"role": str(exc), "valid_roles": ALL_ROLES},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except SelfElevationError as exc:
            return error_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Re-fetch to ensure groups relation is fresh
        target.refresh_from_db()
        log_audit_event(
            action=AuditAction.ADMIN_ROLE_ASSIGNED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
            target=target,
            detail={"role": role_name},
        )
        serializer = AdminUserSerializer(target)
        return success_response(
            data=serializer.data,
            message=f"Role '{role_name}' assigned successfully.",
        )


# ---------------------------------------------------------------------------
# Admin: role removal
# ---------------------------------------------------------------------------

class UserRoleRemoveView(APIView):
    """
    DELETE /api/v1/auth/users/{id}/roles/{role}/

    Remove a role (Django Group) from the target user.

    The role name is URL-encoded in the path segment; spaces should be
    encoded as ``%20`` (e.g. ``Traffic%20Analyst``).

    - Unauthenticated → 401
    - Non-admin → 403
    - Non-existent user → 404
    - Invalid role name → 400
    - Self-modification → 400
    - Success → 204 No Content
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def delete(self, request: Request, user_id: int, role: str) -> Response:
        target = get_object_or_404(User, pk=user_id)

        try:
            RoleService.remove_role(actor=request.user, target=target, role_name=role)
        except InvalidRoleError as exc:
            return error_response(
                message=str(exc),
                errors={"role": str(exc), "valid_roles": ALL_ROLES},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except SelfElevationError as exc:
            return error_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        log_audit_event(
            action=AuditAction.ADMIN_ROLE_REMOVED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
            target=target,
            detail={"role": role},
        )
        return no_content_response()


# ---------------------------------------------------------------------------
# Admin: user active status
# ---------------------------------------------------------------------------

class UserStatusView(APIView):
    """
    PATCH /api/v1/auth/users/{id}/status/

    Activate or deactivate a user account.

    Request body
    ------------
    ::

        { "is_active": false }

    - Unauthenticated → 401
    - Non-admin → 403
    - Non-existent user → 404
    - Self-modification → 400
    - Missing / invalid body → 400
    - Success → 200 with updated user representation
    """

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def patch(self, request: Request, user_id: int) -> Response:
        target = get_object_or_404(User.objects.prefetch_related("groups"), pk=user_id)

        if "is_active" not in request.data:
            return error_response(
                message="The 'is_active' field is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        is_active = request.data["is_active"]
        if not isinstance(is_active, bool):
            return error_response(
                message="The 'is_active' field must be a boolean (true or false).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RoleService.set_active(
                actor=request.user, target=target, is_active=is_active
            )
        except SelfElevationError as exc:
            return error_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        target.refresh_from_db()
        audit_action = (
            AuditAction.ADMIN_USER_ACTIVATED if is_active
            else AuditAction.ADMIN_USER_DEACTIVATED
        )
        log_audit_event(
            action=audit_action,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
            target=target,
            detail={"is_active": is_active},
        )
        serializer = AdminUserSerializer(target)
        action = "activated" if is_active else "deactivated"
        return success_response(
            data=serializer.data,
            message=f"User '{target.username}' {action} successfully.",
        )
