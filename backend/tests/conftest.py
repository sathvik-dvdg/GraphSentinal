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
    _TEST_DB.unlink()
os.environ["SQLITE_PATH"] = str(_TEST_DB)
os.environ.setdefault("DEMO_FALLBACK_FLOWS", "false")

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
    can't bleed into the next."""
    yield
    from app.services.inference_service import InferenceService
    from app.services.blockchain_adapter import BlockchainAdapter

    InferenceService._instance = None
    BlockchainAdapter._instance = None
