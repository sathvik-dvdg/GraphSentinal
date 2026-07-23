# [WSL2]
from __future__ import annotations

from collections import deque
from time import monotonic

from cachetools import TTLCache
from fastapi import Header, HTTPException, Request, status

from app.config import settings


# TTL Cache to prevent memory leaks from inactive IPs
_requests: TTLCache = TTLCache(maxsize=10000, ttl=300)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.backend_api_token:
        return
    valid_tokens = {settings.backend_api_token}
    if settings.admin_api_token:
        valid_tokens.add(settings.admin_api_token)
    if x_api_key not in valid_tokens:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_admin_key(x_api_key: str | None = Header(default=None)) -> None:
    expected_token = settings.admin_api_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key is not configured"
        )
    if x_api_key != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key required"
        )


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

