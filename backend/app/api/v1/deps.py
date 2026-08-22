# [WSL2]
from __future__ import annotations

import secrets
from collections import deque
from time import monotonic

from cachetools import TTLCache
from fastapi import Header, HTTPException, Request, status

from app.config import settings
from app.services import auth_service


# TTL Cache to prevent memory leaks from inactive IPs
_requests: TTLCache = TTLCache(maxsize=10000, ttl=300)
_login_attempts: TTLCache = TTLCache(maxsize=10000, ttl=300)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.backend_api_token and x_api_key != settings.backend_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_session_or_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    """Error.md #18/#27 — gate on either a real operator session (browser
    clients, via the login flow) or the service API key (unchanged, for any
    server-to-server callers). Every /api/v1/* route uses this now — reads
    included, since the original complaint was literally "anyone with app
    access can enter the dashboard," and an unauthenticated GET /graph would
    still leak the same security data around a real login gate."""
    if x_api_key and settings.backend_api_token and secrets.compare_digest(x_api_key, settings.backend_api_token):
        return
    token = auth_service.extract_bearer_token(authorization)
    if auth_service.validate_session(token):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def check_analyze_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = monotonic()
    window = 60.0
    
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

    if client not in _login_attempts:
        _login_attempts[client] = deque()

    queue = _login_attempts[client]
    while queue and now - queue[0] > window:
        queue.popleft()

    if len(queue) >= max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts — try again later")
    queue.append(now)

