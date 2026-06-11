"""Authentication classes for the Ninja API.

`KeyAuth` looks up the bearer token in `APIKey`. On success it stashes
the key on `request.api_key` and the owner on `request.auth_user`, and
returns a truthy value so Ninja proceeds with the view. On failure it
returns None — Ninja then returns 401.
"""
from __future__ import annotations

from ninja.security import HttpBearer

from apps.api.models import APIKey


class KeyAuth(HttpBearer):
    """Authenticate via `Authorization: Bearer apex_<token>`.

    Use this on every endpoint that needs a logged-in caller. The
    matched `APIKey` is attached to the request as both `request.api_key`
    and `request.auth_user` (for convenience in handler signatures).
    """

    def authenticate(self, request, token):
        api_key = APIKey.lookup(token)
        if api_key is None:
            return None
        api_key.touch()
        request.api_key = api_key
        request.auth_user = api_key.user
        return api_key
