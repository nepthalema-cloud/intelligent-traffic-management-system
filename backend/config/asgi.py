"""
ASGI configuration — Phase 5 with Django Channels WebSocket support.

HTTP  → Django REST API (Daphne)
WS /ws/dashboard/ → DashboardConsumer (JWT auth, any authenticated user)
WS /ws/cameras/   → CameraConsumer

Development: AllowedHostsOriginValidator bypassed — Channels' JwtAuthMiddleware
handles authentication.  Re-enable origin validation for production.
"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

# Ensure legacy persistent WEBCAM-001 record is removed on startup.
try:
    from django.db import OperationalError
    from apps.cameras.models import Camera
    try:
        Camera.objects.filter(name='WEBCAM-001').delete()
    except OperationalError:
        # DB not ready or migrations not applied yet — skip cleanup
        pass
except Exception:
    # Import errors or missing app — do not block ASGI startup
    pass
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

from apps.core.ws_middleware import JwtAuthMiddleware
from apps.core.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # JwtAuthMiddleware handles all auth — AllowedHostsOriginValidator
    # is omitted here for dev simplicity; re-add for production with
    # explicit ALLOWED_HOSTS containing the production domain.
    "websocket": JwtAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
