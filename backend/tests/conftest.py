# [WSL2]
"""Shared fixtures for the Error.md regression suite.

Isolated from the real dev database on purpose: `app.config.settings` is a
process-wide singleton loaded at import time, so `SQLITE_PATH` is overridden
via environment variable here, before any `app.*` module is imported by a
test file. Without this, tests would read/write `backend/graphsentinel.db` —
the same database the live app and this session's manual verification passes
have been accumulating real rows in all along.
"""
import os
from pathlib import Path

_TEST_DB = Path(__file__).resolve().parent / "test_regressions.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except (PermissionError, OSError):
        pass
os.environ["SQLITE_PATH"] = str(_TEST_DB)
os.environ.setdefault("DEMO_FALLBACK_FLOWS", "false")
os.environ.setdefault("DAEMON_TOKEN", "test-token-for-pytest")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import init_db  # noqa: E402


init_db()


@pytest.fixture(scope="session")
def client():
    return TestClient(app=__import__("app.main", fromlist=["app"]).app)


@pytest.fixture(scope="session")
def auth_headers():
    return {"X-API-Key": settings.backend_api_token}


@pytest.fixture(autouse=True)
def _reset_module_singletons():
    """Several services are process-wide singletons (`InferenceService`,
    `BlockchainAdapter`) that individual tests reset/monkeypatch. Reset them
    back to a clean, real state after each test so one test's mocked state
    can't bleed into the next. Also clear module-level rate-limit caches
    so concurrency tests do not pollute subsequent tests (O-F06)."""
    from app.api.v1.deps import _login_attempts, _requests

    _requests.clear()
    _login_attempts.clear()
    yield
    from app.services.blockchain_adapter import BlockchainAdapter
    from app.services.inference_service import InferenceService

    InferenceService._instance = None
    BlockchainAdapter._instance = None
    _requests.clear()
    _login_attempts.clear()
