from __future__ import annotations

import os
from threading import Lock

from cachetools import TTLCache
from clerk_backend_api import Clerk

from app.config import settings

_clerk_role_cache = TTLCache(maxsize=1000, ttl=300)
_cache_lock = Lock()


def get_role_from_clerk(user_id: str, clerk_secret: str) -> str | None:
    """Fetch role securely from Clerk API with a thread-safe TTLCache. Fails closed."""
    with _cache_lock:
        if user_id in _clerk_role_cache:
            return _clerk_role_cache[user_id]
            
    try:
        clerk = Clerk(bearer_auth=clerk_secret)
        user = clerk.users.get(user_id)
        role = user.public_metadata.get("role") if user.public_metadata else None
        
        with _cache_lock:
            _clerk_role_cache[user_id] = role
        return role
    except Exception:
        # Fails closed on any Clerk API error (rate limits, timeouts)
        return None


def validate_session_for_socketio(token: str | None) -> dict[str, any] | None:
    """Used exclusively by the WebSocket endpoint since it lacks a FastAPI Request object."""
    if not token:
        return None
        
    clerk_secret = os.environ.get("CLERK_SECRET_KEY")
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
