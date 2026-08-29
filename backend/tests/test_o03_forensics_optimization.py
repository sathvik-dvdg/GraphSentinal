# [WSL2] / [Windows]
"""Phase O / O-03 — Forensics Optimization & Resource Boundary Tests.

Validates that GET /api/v1/forensics reads authoritative persisted state
from SQLite without executing synchronous N+1 blockchain RPC calls per incident.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.incident import Incident
from app.services.blockchain_adapter import BlockchainAdapter

client = TestClient(app)
API_HEADERS = {"X-API-Key": settings.backend_api_token}


@pytest.fixture(autouse=True)
def clean_incidents():
    """Ensure clean incident state for each test in this module."""
    db = SessionLocal()
    try:
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()


# ─── TEST 1: FORENSICS DOES NOT CALL RPC PER INCIDENT ────────────────────────
def test_forensics_does_not_call_rpc_per_incident():
    """TEST 1: Creating multiple Incident rows with blockchain_tx must not trigger
    any per-incident RPC calls (reconcile_tx or web3 lookups) during GET /forensics.
    """
    db = SessionLocal()
    try:
        for idx in range(10):
            inc = Incident(
                source_ip=f"10.0.0.{idx + 1}",
                attack_type="DDoS",
                threat_score=0.95,
                severity=9,
                is_blocked=True,
                blockchain_tx=f"0x{'a' * 60}{idx:04d}",
                blockchain_status="confirmed",
                blockchain_incident_id=100 + idx,
                blockchain_block_number=1000 + idx,
                data_source="test",
            )
            db.add(inc)
        db.commit()
    finally:
        db.close()

    # Patch reconcile_tx to fail if called
    with patch.object(
        BlockchainAdapter,
        "reconcile_tx",
        side_effect=AssertionError("reconcile_tx MUST NOT be called in GET /forensics read path"),
    ):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["total_incidents"] == 10
    assert len(data["incidents"]) == 10
    for inc in data["incidents"]:
        assert inc["tx_status"] == "confirmed"
        assert inc["blockchain_status"] == "confirmed"


# ─── TEST 2: PERSISTED BLOCKCHAIN STATE IS RETURNED ──────────────────────────
def test_forensics_returns_persisted_blockchain_state_without_live_rpc():
    """TEST 2: Verify GET /forensics returns persisted blockchain fields accurately
    even when the blockchain adapter is disconnected or offline.
    """
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.5",
            attack_type="PortScan",
            threat_score=0.88,
            severity=8,
            is_blocked=True,
            blockchain_tx="0x9876543210abcdef000000000000000000000000000000000000000000000001",
            blockchain_chain_id=1337,
            blockchain_contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            blockchain_block_number=42,
            blockchain_incident_id=7,
            blockchain_status="confirmed",
            blockchain_retry_count=0,
            blockchain_last_error=None,
            data_source="test",
        )
        db.add(inc)
        db.commit()
        inc_id = inc.id
    finally:
        db.close()

    # Mock adapter as offline
    mock_adapter = MagicMock()
    mock_adapter._connected = False
    mock_adapter.error = "blockchain offline (isolated test)"
    mock_adapter.client = None

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["total_incidents"] == 1
    record = data["incidents"][0]
    assert record["id"] == inc_id
    assert record["source_ip"] == "10.0.0.5"
    assert record["blockchain_tx"] == "0x9876543210abcdef000000000000000000000000000000000000000000000001"
    assert record["blockchain_chain_id"] == 1337
    assert record["blockchain_contract_address"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    assert record["blockchain_block_number"] == 42
    assert record["blockchain_incident_id"] == 7
    assert record["blockchain_status"] == "confirmed"
    assert record["tx_status"] == "confirmed"


# ─── TEST 3: PENDING / FAILED STATE IS NOT FABRICATED ────────────────────────
def test_forensics_preserves_non_confirmed_states():
    """TEST 3: Incidents in pending, retry, failed, or permanent_failure states
    must reflect their stored state and not be fabricated as confirmed.
    """
    db = SessionLocal()
    try:
        states = [
            ("10.0.0.2", "pending", "0x" + "1" * 64, None),
            ("10.0.0.3", "retry", None, "Gas estimation failed"),
            ("10.0.0.4", "permanent_failure", None, "Max retries exceeded"),
            ("10.0.0.5", "confirmed", "0x" + "2" * 64, None),
        ]
        for ip, st, tx, err in states:
            inc = Incident(
                source_ip=ip,
                attack_type="DDoS",
                threat_score=0.9,
                severity=9,
                is_blocked=True,
                blockchain_tx=tx,
                blockchain_status=st,
                blockchain_last_error=err,
                data_source="test",
            )
            db.add(inc)
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/forensics", headers=API_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total_incidents"] == 4

    records_by_ip = {r["source_ip"]: r for r in data["incidents"]}

    assert records_by_ip["10.0.0.2"]["blockchain_status"] == "pending"
    assert records_by_ip["10.0.0.2"]["tx_status"] == "pending"

    assert records_by_ip["10.0.0.3"]["blockchain_status"] == "retry"
    assert records_by_ip["10.0.0.3"]["tx_status"] == "no_tx"  # no tx hash recorded

    assert records_by_ip["10.0.0.4"]["blockchain_status"] == "permanent_failure"
    assert records_by_ip["10.0.0.4"]["tx_status"] == "no_tx"

    assert records_by_ip["10.0.0.5"]["blockchain_status"] == "confirmed"
    assert records_by_ip["10.0.0.5"]["tx_status"] == "confirmed"


# ─── TEST 4: EMPTY DATABASE ──────────────────────────────────────────────────
def test_forensics_empty_database():
    """TEST 4: Empty database returns valid schema with 0 incidents."""
    response = client.get("/api/v1/forensics", headers=API_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["incidents"] == []
    assert data["total_incidents"] == 0
    assert isinstance(data["blockchain_records"], list)
    assert isinstance(data["total_on_chain"], int)


# ─── TEST 5: FRONTEND RESPONSE CONTRACT ──────────────────────────────────────
def test_forensics_response_contract_stability():
    """TEST 5: Verify all expected fields and types are present in ForensicsResponse."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.7",
            attack_type="SYN-Flood",
            threat_score=0.92,
            severity=9,
            is_blocked=True,
            blockchain_tx="0x" + "f" * 64,
            blockchain_chain_id=1337,
            blockchain_contract_address="0x" + "c" * 40,
            blockchain_block_number=100,
            blockchain_incident_id=12,
            blockchain_status="confirmed",
            blockchain_retry_count=0,
            blockchain_last_error=None,
            enforcement_status="enforced",
            data_source="ovs",
        )
        db.add(inc)
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/forensics", headers=API_HEADERS)
    assert response.status_code == 200
    body = response.json()

    # Top level fields
    top_keys = {"incidents", "blockchain_records", "blockchain_error", "total_incidents", "total_on_chain", "chain_id", "contract_address"}
    assert set(body.keys()) == top_keys

    # Incident record fields
    rec = body["incidents"][0]
    expected_rec_keys = {
        "id", "source_ip", "attack_type", "threat_score", "severity", "is_blocked",
        "blockchain_tx", "blockchain_chain_id", "blockchain_contract_address",
        "blockchain_block_number", "blockchain_incident_id", "blockchain_status",
        "blockchain_retry_count", "blockchain_last_error", "tx_status", "created_at",
        "enforcement_status", "data_source",
    }
    assert set(rec.keys()) == expected_rec_keys
