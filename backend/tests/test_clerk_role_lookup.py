"""get_role_from_clerk must actually reach Clerk and return the user's role.

It called `clerk.users.get(user_id)`; clerk-backend-api takes `user_id` as a
keyword only, so that raised TypeError, the blanket except turned it into None,
and every browser request got 403 "Role could not be determined" -- for every
user, whatever role their Clerk metadata held.
"""
from __future__ import annotations

import inspect
import threading
import time
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


@pytest.fixture(autouse=True)
def _empty_caches():
    """Every cache starts and ends empty, so one test's lookups cannot leak into
    the next (the failure cache would otherwise hold "user_1 failed" for 5 s)."""
    caches = (auth_service._clerk_role_cache, auth_service._clerk_no_role_cache,
              auth_service._clerk_failure_cache, auth_service._fetch_locks)
    for c in caches:
        c.clear()
    yield
    for c in caches:
        c.clear()


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


def test_concurrent_requests_for_one_user_make_one_clerk_call(fake_clerk):
    """The dashboard sends ~9 requests at once; on a cold cache each used to call Clerk."""
    real_get = fake_clerk.get

    def slow_get(*, user_id):
        time.sleep(0.2)  # a Clerk round trip
        return real_get(user_id=user_id)

    fake_clerk.get = slow_get
    roles = []
    threads = [threading.Thread(target=lambda: roles.append(auth_service.get_role_from_clerk("user_1", "sk_test_x")))
               for _ in range(9)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert roles == ["admin"] * 9
    assert fake_clerk.calls == 1


def test_a_failed_lookup_is_remembered_briefly(monkeypatch):
    """During a Clerk outage, one call per user per 5 s -- not one per request."""
    attempts = []

    def broken(bearer_auth):
        attempts.append(1)
        raise RuntimeError("clerk unreachable")

    monkeypatch.setattr(auth_service, "Clerk", broken)
    for _ in range(5):
        assert auth_service.get_role_from_clerk("user_1", "sk_test_x") is None   # fails closed
    assert len(attempts) == 1

    auth_service._clerk_failure_cache.clear()  # the 5 s have passed
    assert auth_service.get_role_from_clerk("user_1", "sk_test_x") is None
    assert len(attempts) == 2
