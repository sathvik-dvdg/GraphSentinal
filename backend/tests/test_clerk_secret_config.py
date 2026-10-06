"""CLERK_SECRET_KEY must reach the backend from backend/.env, not only os.environ.

Before this, deps.py and auth_service.py read os.environ["CLERK_SECRET_KEY"].
pydantic-settings loads backend/.env into `settings` but never exports it, so a
key placed in backend/.env was ignored and every /api/v1 route answered 500.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import deps
from app.config import Settings, settings


def test_env_file_value_reaches_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("CLERK_SECRET_KEY=sk_test_from_file\n", encoding="utf-8")

    assert Settings(_env_file=str(env)).clerk_secret_key == "sk_test_from_file"


def test_missing_key_says_which_setting(monkeypatch):
    monkeypatch.setattr(settings, "clerk_secret_key", "")

    with pytest.raises(HTTPException) as exc:
        deps.get_current_identity(request=None, authorization=None, x_api_key=None)

    assert exc.value.status_code == 500
    assert "CLERK_SECRET_KEY" in exc.value.detail


def test_session_is_verified_with_the_configured_key(monkeypatch):
    monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_configured")
    seen = {}

    def fake_authenticate(request, options):
        seen["secret"] = options.secret_key
        return SimpleNamespace(is_signed_in=True, payload={"sub": "user_1", "public_metadata": {"role": "admin"}})

    monkeypatch.setattr(deps, "authenticate_request", fake_authenticate)

    identity = deps.get_current_identity(request=None, authorization="Bearer t", x_api_key=None)

    assert seen["secret"] == "sk_test_configured"
    assert identity == {"type": "session", "role": "admin", "identity": "user_1"}
