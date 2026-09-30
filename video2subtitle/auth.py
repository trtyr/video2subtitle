"""Bearer token auth — constant-time compare, single static token."""

import secrets

from fastapi import Request

from .errors import api_error, Codes


def require_token(request: Request) -> None:
    settings = request.app.state.settings
    expected = settings.token
    auth = request.headers.get("authorization", "")
    if expected and auth.startswith("Bearer "):
        supplied = auth[len("Bearer "):].strip()
        if supplied and secrets.compare_digest(supplied, expected):
            return
    raise api_error(Codes.UNAUTHORIZED, "missing or invalid bearer token")
