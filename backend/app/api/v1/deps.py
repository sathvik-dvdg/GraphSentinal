# [WSL2]
from __future__ import annotations

import os
import secrets
from collections import deque
from time import monotonic


from cachetools import TTLCache
from fastapi import Depends, Header, HTTPException, Request, status
from clerk_backend_api import authenticate_request, AuthenticateRequestOptions

from app.config import settings
from app.services import auth_service


# TTL Cache to prevent memory leaks from inactive IPs
_requests: TTLCache = TTLCache(maxsize=10000, ttl=300)
_login_attempts: TTLCache = TTLCache(maxsize=10000, ttl=300)


def get_current_identity(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict:
    # 1. API Key Authentication
    if x_api_key:
        if settings.admin_api_token and secrets.compare_digest(x_api_key, settings.admin_api_token):
            return {"type": "api_key", "role": "admin", "identity": "admin_api"}
        if settings.backend_api_token and secrets.compare_digest(x_api_key, settings.backend_api_token):
            return {"type": "api_key", "role": "operator", "identity": "backend_api"}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # 2. Session Bearer Token Authentication (Clerk natively)
    clerk_secret = os.environ.get("CLERK_SECRET_KEY")
    if not clerk_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clerk secret key not configured")

    try:
        # Proper dependency injection: pass real FastAPI Request to Clerk SDK
        state = authenticate_request(
            request,
            AuthenticateRequestOptions(secret_key=clerk_secret)
        )
    except Exception:
        # Stop swallowing exceptions: fail closed
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    if not state.is_signed_in:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = state.payload["sub"]
    
    # Check JWT public metadata first, fallback to cached API fetch
    metadata = state.payload.get("public_metadata")
    if metadata is not None:
        role = metadata.get("role")
    else:
        role = auth_service.get_role_from_clerk(user_id, clerk_secret)

    if role is None:
        # Fail closed on role validation
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role could not be determined")

    return {
        "type": "session",
        "role": role,
        "identity": user_id,
    }


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    admin_match = bool(settings.admin_api_token) and secrets.compare_digest(x_api_key, settings.admin_api_token)
    backend_match = bool(settings.backend_api_token) and secrets.compare_digest(x_api_key, settings.backend_api_token)
    if not (admin_match or backend_match):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_session_or_api_key(
    identity: dict = Depends(get_current_identity),
) -> dict:
    """Allows any authenticated identity (operator, admin, or API key)."""
    return identity


def require_write_privilege(
    identity: dict = Depends(get_current_identity),
) -> dict:
    """Any authenticated identity except the 'readonly' role. For routes that
    change state but are not admin-only: /analyze blocks hosts and writes to
    the chain, so a read-only session must not reach it."""
    if identity.get("role") == "readonly":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only role cannot perform this action",
        )
    return identity


def require_admin_privilege(
    identity: dict = Depends(get_current_identity),
) -> dict:
    """Restricts control-plane / settings mutations to identities with 'admin' role."""
    if identity.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privilege required",
        )
    return identity


def get_current_request_id(request: Request | None = None) -> str:
    """Return the active correlation/request ID from request state or contextvar."""
    from app.main import request_id_ctx_var
    if request is not None and hasattr(request, "state") and getattr(request.state, "request_id", None):
        return request.state.request_id
    return request_id_ctx_var.get() or ""




def _prune_rate_limit_map(rate_map: dict[str, deque[float]], now: float, window: float, max_entries: int = 2000) -> None:
    """R-05 (M11-F01) — Evict stale client entries to prevent memory accumulation in rate-limiting maps."""
    if len(rate_map) <= max_entries:
        return
    stale_keys = [k for k, q in rate_map.items() if not q or now - q[-1] > window]
    for k in stale_keys:
        rate_map.pop(k, None)


def check_analyze_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = monotonic()
    window = 60.0

    _prune_rate_limit_map(_requests, now, window)

    if client not in _requests:
        _requests[client] = deque()

    queue = _requests[client]
    while queue and now - queue[0] > window:
        queue.popleft()

    if len(queue) >= settings.analyze_rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Analyze rate limit exceeded")
    queue.append(now)


def check_login_rate_limit(request: Request) -> None:
    """A single static operator password is more brute-forceable than a
    rotating API key — cap attempts per source IP."""
    client = request.client.host if request.client else "unknown"
    now = monotonic()
    window = 300.0
    max_attempts = 10

    _prune_rate_limit_map(_login_attempts, now, window)

    if client not in _login_attempts:
        _login_attempts[client] = deque()

    queue = _login_attempts[client]
    while queue and now - queue[0] > window:
        queue.popleft()

    if len(queue) >= max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts — try again later")
    queue.append(now)

