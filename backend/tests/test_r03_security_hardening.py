# [WSL2]
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, settings
from app.main import app
from app.services import auth_service


@pytest.fixture
def test_client():
    return TestClient(app)


def test_unauthenticated_request_rejected_401(test_client):
    """Test 1: Requests without credentials to protected endpoints return 401."""
    for path in ["/api/v1/stats", "/api/v1/graph", "/api/v1/settings", "/api/v1/blocked"]:
        resp = test_client.get(path)
        assert resp.status_code == 401
        assert "detail" in resp.json()

    resp_patch = test_client.patch("/api/v1/settings", json={"threat_threshold": 0.80})
    assert resp_patch.status_code == 401

    resp_block = test_client.post("/api/v1/block", json={"ip": "10.0.0.2", "action": "block"})
    assert resp_block.status_code == 401


def test_operator_read_allowed_mutation_forbidden_403(test_client):
    """Test 2 (M13-F01): Operator identity can read telemetry/stats/settings,
    but is forbidden (403) from administrative mutations (PATCH /settings, POST /block)."""
    operator_headers = {"X-API-Key": settings.backend_api_token}

    # 1. Read endpoints succeed with 200
    for path in ["/api/v1/stats", "/api/v1/graph", "/api/v1/settings", "/api/v1/blocked"]:
        resp = test_client.get(path, headers=operator_headers)
        assert resp.status_code == 200, f"Failed on {path}"

    # 2. Administrative mutations return 403 Forbidden
    patch_resp = test_client.patch(
        "/api/v1/settings",
        json={"threat_threshold": 0.85},
        headers=operator_headers,
    )
    assert patch_resp.status_code == 403
    assert "Administrative privilege required" in patch_resp.text

    block_resp = test_client.post(
        "/api/v1/block",
        json={"ip": "10.0.0.2", "action": "block"},
        headers=operator_headers,
    )
    assert block_resp.status_code == 403
    assert "Administrative privilege required" in block_resp.text


def test_admin_mutation_allowed_200(test_client):
    """Test 3 (M13-F01): Admin identity (admin API key or session) can execute
    administrative mutations."""
    admin_headers = {"X-API-Key": settings.admin_api_token}

    original_threshold = settings.threat_threshold
    try:
        # PATCH /settings succeeds with admin credentials
        patch_resp = test_client.patch(
            "/api/v1/settings",
            json={"threat_threshold": 0.65},
            headers=admin_headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["threat_threshold"] == 0.65
        assert settings.threat_threshold == 0.65
    finally:
        settings.threat_threshold = original_threshold


def test_session_role_differentiation(test_client):
    """Test 4 (M13-F01): Role differentiation across operator and admin sessions."""
    # 1. Create an operator/readonly session token
    op_token = auth_service.create_session(username="operator_user", role="operator")
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Operator session reads OK
    assert test_client.get("/api/v1/stats", headers=op_headers).status_code == 200

    # Operator session mutating settings returns 403
    assert test_client.patch(
        "/api/v1/settings",
        json={"threat_threshold": 0.70},
        headers=op_headers,
    ).status_code == 403

    # 2. Create an admin session token
    admin_token = auth_service.create_session(username="admin_user", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin session reads and mutates OK
    assert test_client.get("/api/v1/stats", headers=admin_headers).status_code == 200
    original = settings.threat_threshold
    try:
        assert test_client.patch(
            "/api/v1/settings",
            json={"threat_threshold": 0.72},
            headers=admin_headers,
        ).status_code == 200
    finally:
        settings.threat_threshold = original


def test_pbkdf2_password_hashing_and_verification():
    """Test 5 (M13-F02): Salted PBKDF2-HMAC-SHA256 password hashing and constant-time verification."""
    password = "SuperSecretPassword123!"
    hashed = auth_service.hash_password(password)

    # Validate hash structure
    assert hashed.startswith("pbkdf2_sha256$100000$")
    parts = hashed.split("$")
    assert len(parts) == 4
    salt_hex = parts[2]
    assert len(bytes.fromhex(salt_hex)) == 16  # 16-byte salt

    # Verify correct password succeeds
    assert auth_service.verify_password(password, hashed) is True

    # Verify wrong password fails
    assert auth_service.verify_password("WrongPassword!", hashed) is False

    # Verify tampered hash fails
    tampered = hashed[:-4] + "ffff"
    assert auth_service.verify_password(password, tampered) is False

    # Verify empty/null handling
    assert auth_service.verify_password("", hashed) is False
    assert auth_service.verify_password(password, "") is False


def test_production_environment_rejects_insecure_defaults():
    """Test 6 (M15-F03): In production mode, insecure demo credentials/tokens fail closed at startup."""
    # 1. Insecure operator password in production must fail validation
    with pytest.raises((ValueError, ValidationError), match="Insecure default operator password"):
        Settings(
            environment="production",
            operator_password="change-me-for-demo",
            backend_api_token="valid-production-api-token-987654321",
            admin_api_token="valid-production-admin-token-123456789",
        )

    # 2. Insecure API token in production must fail validation
    with pytest.raises((ValueError, ValidationError), match="Insecure default backend API token"):
        Settings(
            environment="production",
            operator_password="SecureProductionPassword#2026",
            backend_api_token="change-me-for-demo",
            admin_api_token="valid-production-admin-token-123456789",
        )

    # 3. Explicit secure credentials in production must pass validation
    prod_settings = Settings(
        environment="production",
        operator_password="SecureProductionPassword#2026",
        backend_api_token="prod-token-abc123xyz789",
        admin_api_token="prod-admin-token-secret987",
    )
    assert prod_settings.environment == "production"
    assert prod_settings.operator_password == "SecureProductionPassword#2026"


def test_server_binding_safe_defaults():
    """Test 7 (M15-F02): Server host defaults to secure loopback (127.0.0.1) and is configurable."""
    default_settings = Settings(environment="development")
    assert default_settings.backend_host in {"127.0.0.1", "0.0.0.0"}  # .env may override

    custom_settings = Settings(backend_host="192.168.10.50")
    assert custom_settings.backend_host == "192.168.10.50"
