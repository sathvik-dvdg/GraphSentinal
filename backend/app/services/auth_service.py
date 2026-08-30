# [WSL2]
# Error.md #18/#27 — single-operator session store. Deliberately in-memory,
# not a DB table: sessions are short-lived (default 8h) and losing them on a
# backend restart just means logging in again, which is the correct/expected
# behavior for a session, not a bug. A single-instance backend is assumed
# throughout this app already (see graph_state.py's in-memory state, #10).
from __future__ import annotations

import hashlib
import secrets
import time
from threading import Lock

from app.config import settings

_sessions: dict[str, dict[str, any]] = {}
_lock = Lock()


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a 16-byte random salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, stored_hash_or_plain: str) -> bool:
    """Verify password against a PBKDF2 hash, with constant-time fallback for plaintext."""
    if not plain_password or not stored_hash_or_plain:
        return False
    if stored_hash_or_plain.startswith("pbkdf2_sha256$"):
        try:
            parts = stored_hash_or_plain.split("$")
            if len(parts) != 4:
                return False
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected_hash = parts[3]
            derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
            return secrets.compare_digest(derived.hex(), expected_hash)
        except Exception:
            return False
    # Plaintext comparison using constant-time comparison for dev fallback
    return secrets.compare_digest(plain_password, stored_hash_or_plain)


def create_session(username: str | None = None, role: str = "operator") -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {
            "expiry": time.monotonic() + settings.session_ttl_hours * 3600,
            "username": username or settings.operator_username,
            "role": role,
        }
    return token


def validate_session(token: str | None) -> dict[str, any] | None:
    if not token:
        return None
    with _lock:
        session = _sessions.get(token)
        if session is None:
            return None
        if time.monotonic() > session["expiry"]:
            del _sessions[token]
            return None
        return dict(session)


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None

