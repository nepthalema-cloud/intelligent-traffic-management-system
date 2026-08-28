"""
JWT authentication middleware for Django Channels WebSocket connections.

Clients connect with:
  ws://localhost:8000/ws/dashboard/?token=<access_token>

The token is validated using Simple JWT. If invalid, the scope's user
is set to AnonymousUser and the consumer can reject the connection.
"""

from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_from_token(token_str: str):
    """Validate a JWT access token and return the associated user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        token = AccessToken(token_str)
        user_id = token.get("user_id")
        return User.objects.get(pk=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JwtAuthMiddleware:
    """
    ASGI middleware that authenticates WebSocket connections via JWT query param.
    Falls back to AnonymousUser if no/invalid token.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope.get("query_string", b"").decode())
        token_list = qs.get("token", [])
        if token_list:
            scope["user"] = await get_user_from_token(token_list[0])
        else:
            scope["user"] = AnonymousUser()
        return await self.inner(scope, receive, send)
