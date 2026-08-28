"""
URL configuration for the accounts app.

All endpoints are mounted by ``config/api.py`` under:

    /api/v1/auth/

Current endpoints
-----------------
    POST   /api/v1/auth/login/                      Obtain JWT access + refresh token pair
    POST   /api/v1/auth/refresh/                    Rotate refresh token, obtain new access token
    POST   /api/v1/auth/logout/                     Blacklist the refresh token (requires auth)
    GET    /api/v1/auth/me/                         Authenticated user's own profile
    GET    /api/v1/auth/users/                      Admin: list all users (paginated)
    GET    /api/v1/auth/users/{id}/                 Admin: retrieve a single user
    POST   /api/v1/auth/users/{id}/roles/           Admin: assign a role to a user
    DELETE /api/v1/auth/users/{id}/roles/{role}/    Admin: remove a role from a user
    PATCH  /api/v1/auth/users/{id}/status/          Admin: activate or deactivate a user
"""

from django.urls import path

from apps.accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    UserDetailView,
    UserListView,
    UserRoleAssignView,
    UserRoleRemoveView,
    UserStatusView,
)

app_name = "accounts"

urlpatterns = [
    # JWT authentication
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Authenticated user's own profile
    path("me/", MeView.as_view(), name="me"),

    # Admin: user management
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:user_id>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:user_id>/roles/", UserRoleAssignView.as_view(), name="user-role-assign"),
    path("users/<int:user_id>/roles/<str:role>/", UserRoleRemoveView.as_view(), name="user-role-remove"),
    path("users/<int:user_id>/status/", UserStatusView.as_view(), name="user-status"),
]
