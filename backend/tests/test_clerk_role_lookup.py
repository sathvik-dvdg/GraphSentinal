"""get_role_from_clerk must actually reach Clerk and return the user's role.

It called `clerk.users.get(user_id)`; clerk-backend-api takes `user_id` as a
keyword only, so that raised TypeError, the blanket except turned it into None,
and every browser request got 403 "Role could not be determined" -- for every
user, whatever role their Clerk metadata held.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from cachetools import TTLCache
from clerk_backend_api import Clerk

from app.services import auth_service


class _FakeUsers:
    def __init__(self, metadata):
        self._metadata = metadata
        self.calls = 0

    def get(self, *, user_id):  # keyword-only, like the real SDK (checked below)
        self.calls += 1
        return SimpleNamespace(id=user_id, public_metadata=self._metadata)


@pytest.fixture
def clock(monkeypatch):
    """A controllable clock for the no-role cache's 30s TTL."""
    now = [0.0]
    monkeypatch.setattr(
        auth_service, "_clerk_no_role_cache",
        TTLCache(maxsize=1000, ttl=auth_service._clerk_no_role_cache.ttl, timer=lambda: now[0]),
    )
    return now


@pytest.fixture
def fake_clerk(monkeypatch, clock):
    auth_service._clerk_role_cache.clear()
    users = _FakeUsers({"role": "admin"})
    monkeypatch.setattr(auth_service, "Clerk", lambda bearer_auth: SimpleNamespace(users=users))
    yield users
    auth_service._clerk_role_cache.clear()


def test_real_sdk_takes_user_id_as_keyword_only():
    param = inspect.signature(Clerk(bearer_auth="sk_test_x").users.get).parameters["user_id"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_role_is_read_from_public_metadata(fake_clerk):
    assert auth_service.get_role_from_clerk("user_1", "sk_test_x") == "admin"


def test_role_is_cached(fake_clerk):
    auth_service.get_role_from_clerk("user_1", "sk_test_x")
    auth_service.get_role_from_clerk("user_1", "sk_test_x")
    assert fake_clerk.calls == 1


def test_missing_role_is_cached_briefly(fake_clerk, clock):
    fake_clerk._metadata = {}
    for _ in range(5):  # repeated requests from a user with no role
        assert auth_service.get_role_from_clerk("user_1", "sk_test_x") is None
    assert fake_clerk.calls == 1  # one Clerk call, not one per request

    fake_clerk._metadata = {"role": "operator"}  # role added in the Clerk dashboard
    clock[0] += auth_service._clerk_no_role_cache.ttl + 1
    assert auth_service.get_role_from_clerk("user_1", "sk_test_x") == "operator"


def test_lookup_failure_is_logged_and_fails_closed(monkeypatch, caplog):
    auth_service._clerk_role_cache.clear()

    def broken(bearer_auth):
        raise RuntimeError("clerk unreachable")

    monkeypatch.setattr(auth_service, "Clerk", broken)
    with caplog.at_level("WARNING", logger="graphsentinel.auth"):
        assert auth_service.get_role_from_clerk("user_1", "sk_test_x") is None
    assert "Clerk role lookup failed for user_1: RuntimeError" in caplog.text


def test_request_without_metadata_claim_gets_role_from_clerk(fake_clerk, monkeypatch):
    """Clerk's default session token carries no public_metadata, so this is the
    path every dashboard request takes."""
    from app.api.v1 import deps
    from app.config import settings

    monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_x")
    monkeypatch.setattr(
        deps, "authenticate_request",
        lambda request, options: SimpleNamespace(is_signed_in=True, payload={"sub": "user_1"}),
    )

    identity = deps.get_current_identity(request=None, authorization="Bearer t", x_api_key=None)

    assert identity == {"type": "session", "role": "admin", "identity": "user_1"}
