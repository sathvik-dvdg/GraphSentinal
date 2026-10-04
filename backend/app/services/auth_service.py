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
import os
from threading import Lock

from cachetools import TTLCache
from fastapi import Request

# pyrefly: ignore [missing-import]
from clerk_backend_api import Clerk, authenticate_request, AuthenticateRequestOptions

from app.config import settings

_sessions: dict[str, dict[str, any]] = {}
_lock = Lock()
_clerk_role_cache = TTLCache(maxsize=1000, ttl=300)


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

    # 1. Check Clerk session first
    clerk_secret = os.environ.get("CLERK_SECRET_KEY")
    if clerk_secret:
        # Create a mock FastAPI Request to use Clerk's middleware
        req = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))]})
        try:
            state = authenticate_request(req, AuthenticateRequestOptions(secret_key=clerk_secret))
            if state.is_signed_in:
                user_id = state.payload["sub"]
                
                # Check if role is baked into the JWT directly (if user configured a custom JWT template)
                metadata = state.payload.get("public_metadata")
                if metadata is not None:
                    role = metadata.get("role", "operator")
                else:
                    # Otherwise, use cached API fetch to avoid requiring Clerk Dashboard JWT template changes
                    if user_id in _clerk_role_cache:
                        role = _clerk_role_cache[user_id]
                    else:
                        try:
                            clerk = Clerk(bearer_auth=clerk_secret)
                            user = clerk.users.get(user_id)
                            role = user.public_metadata.get("role", "operator") if user.public_metadata else "operator"
                            _clerk_role_cache[user_id] = role
                        except Exception:
                            role = "operator"
                            
                return {"username": user_id, "role": role}
        except Exception as e:
            pass # fallback to local session

    # 2. Local fallback
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

