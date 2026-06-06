# [WSL2]
from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import Header, HTTPException, Request, status

from app.config import settings


_requests: dict[str, deque[float]] = defaultdict(deque)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.backend_api_token and x_api_key != settings.backend_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def check_analyze_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = monotonic()
    window = 60.0
    queue = _requests[client]
    while queue and now - queue[0] > window:
        queue.popleft()
    if len(queue) >= settings.analyze_rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Analyze rate limit exceeded")
    queue.append(now)

