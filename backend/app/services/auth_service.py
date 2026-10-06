from __future__ import annotations

import logging
from threading import Lock

from cachetools import TTLCache
from clerk_backend_api import Clerk

from app.config import settings

_clerk_role_cache = TTLCache(maxsize=1000, ttl=300)
# Users with no role are cached too, briefly: long enough that a signed-in user
# without a role can't turn every request into a Clerk API call (rate limits),
# short enough that a role added in the Clerk dashboard works within 30s.
_clerk_no_role_cache = TTLCache(maxsize=1000, ttl=30)
_cache_lock = Lock()
_log = logging.getLogger("graphsentinel.auth")


def get_role_from_clerk(user_id: str, clerk_secret: str) -> str | None:
    """Fetch role securely from Clerk API with a thread-safe TTLCache. Fails closed."""
    with _cache_lock:
        if user_id in _clerk_role_cache:
            return _clerk_role_cache[user_id]
        if user_id in _clerk_no_role_cache:
            return None
            
    try:
        clerk = Clerk(bearer_auth=clerk_secret)
        # user_id is keyword-only in clerk-backend-api; passing it positionally
        # raised TypeError, which the except below turned into "no role" -- a
        # 403 on every request for every user, whatever their metadata said.
        user = clerk.users.get(user_id=user_id)
        role = user.public_metadata.get("role") if user.public_metadata else None
    except Exception as exc:
        # Fails closed on any Clerk API error (rate limits, timeouts), but says so:
        # a silent None is indistinguishable from a user who has no role.
        _log.warning("Clerk role lookup failed for %s: %s: %s", user_id, type(exc).__name__, exc)
        return None

    if role is None:
        _log.warning("Clerk user %s has no public_metadata.role -- requests will get 403", user_id)
        with _cache_lock:
            _clerk_no_role_cache[user_id] = True
        return None
    with _cache_lock:
        _clerk_role_cache[user_id] = role
    return role


def validate_session_for_socketio(token: str | None) -> dict[str, any] | None:
    """Used exclusively by the WebSocket endpoint since it lacks a FastAPI Request object."""
    if not token:
        return None
        
    clerk_secret = settings.clerk_secret_key
    if not clerk_secret:
        return None
        
    from fastapi import Request
    from clerk_backend_api import authenticate_request, AuthenticateRequestOptions
    
    # Websocket lacks FastAPI context. Mocking Request is the only native way 
    # to use Clerk's SDK authenticate_request without installing raw PyJWT.
    req = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))]})
    try:
        state = authenticate_request(req, AuthenticateRequestOptions(secret_key=clerk_secret))
        if not state.is_signed_in:
            return None
            
        user_id = state.payload["sub"]
        
        # Prefer JWT template claim if configured, otherwise fallback to cached API fetch
        metadata = state.payload.get("public_metadata")
        if metadata is not None:
            role = metadata.get("role")
        else:
            role = get_role_from_clerk(user_id, clerk_secret)
            
        if role is None:
            return None
            
        return {"username": user_id, "role": role}
    except Exception:
        # Fails closed if token is invalid or expired
        return None
