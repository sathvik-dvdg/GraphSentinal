# [WSL2]
# Error.md #18/#27 — single-operator session store. Deliberately in-memory,
# not a DB table: sessions are short-lived (default 8h) and losing them on a
# backend restart just means logging in again, which is the correct/expected
# behavior for a session, not a bug. A single-instance backend is assumed
# throughout this app already (see graph_state.py's in-memory state, #10).
from __future__ import annotations

import secrets
import time
from threading import Lock

from app.config import settings

_sessions: dict[str, float] = {}
_lock = Lock()


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = time.monotonic() + settings.session_ttl_hours * 3600
    return token


def validate_session(token: str | None) -> bool:
    if not token:
        return False
    with _lock:
        expiry = _sessions.get(token)
        if expiry is None:
            return False
        if time.monotonic() > expiry:
            del _sessions[token]
            return False
        return True


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None
