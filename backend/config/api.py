"""
Centralized API router for the traffic management backend.

Routing hierarchy
-----------------
    api/              <- config/urls.py
      v1/             <- this file
        health/       <- apps/core/urls.py  (system health)
        auth/         <- apps/accounts/urls.py  (authentication, Phase 3B+)

Adding new app routes
---------------------
Register new application URL modules here under the ``v1/`` prefix.
Do not add routes directly in ``config/urls.py``.
"""

from django.urls import include, path

urlpatterns = [
    # Core: system health endpoint
    path("v1/", include("apps.core.urls")),
    # Accounts: authentication endpoints (namespace: accounts)
    path("v1/auth/", include("apps.accounts.urls")),
    # Audit: audit event endpoints (namespace: audit)
    path("v1/audit/", include("apps.audit.urls")),
    # Roads: road infrastructure endpoints (namespace: roads)
    path("v1/roads/", include("apps.roads.urls")),
    # Cameras: camera and sensor endpoints (namespace: cameras)
    path("v1/cameras/", include("apps.cameras.urls")),
    # Traffic: signal configuration endpoints (namespace: traffic)
    path("v1/traffic/", include("apps.traffic.urls")),
    # Violations: enforcement domain endpoints (namespace: violations)
    path("v1/violations/", include("apps.violations.urls")),
    # Analytics: pre-aggregated summaries (namespace: analytics)
    path("v1/analytics/", include("apps.analytics.urls")),
    # Organizations: regions, cities, traffic control centers
    path("v1/organizations/", include("apps.organizations.urls")),
    # Drivers: driver registry
    path("v1/drivers/", include("apps.drivers.urls")),
    # Fines: fine and payment lifecycle
    path("v1/fines/", include("apps.fines.urls")),
    # Notifications: in-app notification templates and messages
    path("v1/notifications/", include("apps.notifications.urls")),
]
