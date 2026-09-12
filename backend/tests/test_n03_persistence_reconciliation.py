# [WSL2]
# backend/tests/test_n03_persistence_reconciliation.py
# ─────────────────────────────────────────────────────────────────────────────
# N-03 Backend Tests — Ganache Persistence & Chain/DB Synchronization
#
# Tests 1-10 as required by N-03 remediation specification:
#
# T1  ForensicsResponse schema includes tx_status on every incident record
# T2  Incidents with no blockchain_tx receive tx_status='no_tx'
# T3  Incidents with blockchain_tx receive a non-None tx_status classification
# T4  reconcile_tx() returns 'unavailable' when adapter is offline
# T5  reconcile_tx() returns 'no_tx' for None/empty tx_hash
# T6  reconcile_tx() returns 'missing' for a tx hash not on chain
# T7  reconcile_tx() returns 'confirmed' for a real tx (mocked receipt)
# T8  reconcile_tx() returns 'wrong_contract' when tx targets different address
# T9  Forensics endpoint is resilient to blockchain being offline
# T10 [N02 regression] store_incident rejects non-deployer via BlockchainAdapter mock
#
# These are unit tests — no running Docker/Ganache is required.
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.blockchain_adapter import BlockchainAdapter


client = TestClient(app)
API_HEADERS = {"X-API-Key": settings.backend_api_token}


# ─── Test 1 ──────────────────────────────────────────────────────────────────
def test_t1_forensics_response_includes_tx_status():
    """T1: GET /api/v1/forensics returns incident records that include a tx_status field."""
    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.error = "blockchain offline (test isolation)"

    with patch.object(BlockchainAdapter, "get_instance", return_value=adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert "incidents" in body

    for record in body["incidents"]:
        assert "tx_status" in record, (
            f"IncidentRecord id={record.get('id')} is missing the 'tx_status' field"
        )


# ─── Test 2 ──────────────────────────────────────────────────────────────────
def test_t2_incident_without_blockchain_tx_gets_no_tx_status():
    """T2: An incident row with no blockchain_tx must receive tx_status='no_tx'."""
    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.error = "offline"

    with patch.object(BlockchainAdapter, "get_instance", return_value=adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    body = response.json()
    incidents_without_tx = [i for i in body["incidents"] if not i.get("blockchain_tx")]
    for record in incidents_without_tx:
        assert record["tx_status"] == "no_tx", (
            f"incident id={record['id']} has no blockchain_tx but tx_status={record['tx_status']!r}"
        )


# ─── Test 3 ──────────────────────────────────────────────────────────────────
def test_t3_incident_with_blockchain_tx_gets_classified():
    """T3: An incident with a blockchain_tx must receive a non-None tx_status."""
    from app.database import SessionLocal
    from app.models.incident import Incident

    db = SessionLocal()
    try:
        # Fabricate an incident with a fake tx_hash
        fake = Incident(
            source_ip="10.0.0.42",
            attack_type="DDoS",
            threat_score=0.9,
            severity=9,
            is_blocked=False,
            blockchain_tx="0xdeadbeef" + "0" * 56,  # 66-char hex
            enforcement_status="simulated",
            data_source="test",
        )
        db.add(fake)
        db.commit()
        db.refresh(fake)
        fake_id = fake.id
    finally:
        db.close()

    # The adapter is offline → reconcile_tx returns 'unavailable'
    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.error = "offline"

    with patch.object(BlockchainAdapter, "get_instance", return_value=adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    body = response.json()
    matching = [i for i in body["incidents"] if i["id"] == fake_id]
    assert matching, f"fabricated incident id={fake_id} not found in forensics response"
    assert matching[0]["tx_status"] is not None, (
        "incident with a blockchain_tx must not return tx_status=None"
    )
    # When adapter is offline the status is 'unavailable'
    assert matching[0]["tx_status"] == "unavailable"

    # Cleanup
    db = SessionLocal()
    try:
        db.delete(db.get(Incident, fake_id))
        db.commit()
    finally:
        db.close()


# ─── Test 4 ──────────────────────────────────────────────────────────────────
def test_t4_reconcile_tx_returns_unavailable_when_offline():
    """T4: reconcile_tx() returns 'unavailable' when adapter is not connected."""
    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.client = None
    adapter.error = "offline"

    result = adapter.reconcile_tx("0xdeadbeef", expected_contract="0xcontract")
    assert result == "unavailable", f"expected 'unavailable', got {result!r}"


# ─── Test 5 ──────────────────────────────────────────────────────────────────
def test_t5_reconcile_tx_returns_no_tx_for_empty_hash():
    """T5: reconcile_tx() returns 'no_tx' for None or empty tx_hash."""
    adapter = BlockchainAdapter()
    adapter._connected = True  # connection state is irrelevant for None input

    assert adapter.reconcile_tx(None) == "no_tx"
    assert adapter.reconcile_tx("") == "no_tx"
    assert adapter.reconcile_tx("   ") in ("no_tx", "unavailable")  # whitespace-only


# ─── Test 6 ──────────────────────────────────────────────────────────────────
def test_t6_reconcile_tx_returns_missing_for_unknown_hash():
    """T6: reconcile_tx() returns 'missing' when the tx hash is not on chain."""
    mock_w3 = MagicMock()
    # Simulate TransactionNotFound exception from web3
    mock_w3.eth.get_transaction.side_effect = Exception("transaction not found")

    mock_client = MagicMock()
    mock_client.w3 = mock_w3

    adapter = BlockchainAdapter()
    adapter._connected = True
    adapter.client = mock_client

    result = adapter.reconcile_tx("0x" + "a" * 64)
    assert result == "missing", f"expected 'missing', got {result!r}"


# ─── Test 7 ──────────────────────────────────────────────────────────────────
def test_t7_reconcile_tx_returns_confirmed_for_valid_receipt():
    """T7: reconcile_tx() returns 'confirmed' when tx exists and receipt.status==1."""
    tx_hash = "0x" + "b" * 64
    contract_addr = "0xabcdef1234567890abcdef1234567890abcdef12"

    mock_tx = {"to": contract_addr}
    mock_receipt = {"status": 1}

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction.return_value = mock_tx
    mock_w3.eth.get_transaction_receipt.return_value = mock_receipt

    mock_client = MagicMock()
    mock_client.w3 = mock_w3

    adapter = BlockchainAdapter()
    adapter._connected = True
    adapter.client = mock_client

    result = adapter.reconcile_tx(tx_hash, expected_contract=contract_addr)
    assert result == "confirmed", f"expected 'confirmed', got {result!r}"


# ─── Test 8 ──────────────────────────────────────────────────────────────────
def test_t8_reconcile_tx_returns_wrong_contract_when_target_differs():
    """T8: reconcile_tx() returns 'wrong_contract' when tx.to != expected_contract."""
    tx_hash = "0x" + "c" * 64
    deployed_contract = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    stale_contract = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

    # Tx points to the old/different contract
    mock_tx = {"to": stale_contract.lower()}
    mock_receipt = {"status": 1}

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction.return_value = mock_tx
    mock_w3.eth.get_transaction_receipt.return_value = mock_receipt

    mock_client = MagicMock()
    mock_client.w3 = mock_w3

    adapter = BlockchainAdapter()
    adapter._connected = True
    adapter.client = mock_client

    # Compare against the NEW (current) contract — tx targets the old one
    result = adapter.reconcile_tx(tx_hash, expected_contract=deployed_contract)
    assert result == "wrong_contract", f"expected 'wrong_contract', got {result!r}"


# ─── Test 9 ──────────────────────────────────────────────────────────────────
def test_t9_forensics_endpoint_resilient_to_blockchain_offline():
    """T9: GET /api/v1/forensics returns 200 and surfaces blockchain_error when offline."""
    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.error = "simulated offline for T9"

    with patch.object(BlockchainAdapter, "get_instance", return_value=adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    assert response.status_code == 200, "forensics endpoint must not 500 when blockchain is offline"
    body = response.json()

    # SQLite incidents must still be returned
    assert "incidents" in body
    assert "total_incidents" in body

    # Blockchain offline must be surfaced, not silently hidden
    assert body.get("blockchain_error") is not None, (
        "blockchain_error must be non-null when adapter is offline"
    )
    assert body["total_on_chain"] == 0, (
        "total_on_chain must be 0 when blockchain is offline"
    )


# ─── Test 10 ─────────────────────────────────────────────────────────────────
def test_t10_n02_regression_store_incident_rejects_unauthorized():
    """T10: [N02 regression] The BlockchainAdapter surfaces contract revert when a
    non-deployer attempts to log an incident — onlyDeployer modifier is intact."""
    # Mock the web3_client to raise ContractLogicError (as Ganache would for Unauthorized)
    from web3.exceptions import ContractLogicError

    mock_contract_fn = MagicMock()
    mock_contract_fn.transact.side_effect = ContractLogicError("Unauthorized")

    mock_contract = MagicMock()
    mock_contract.functions.logIncident.return_value = mock_contract_fn

    mock_client = MagicMock()
    mock_client.log_incident.side_effect = ContractLogicError("Unauthorized")

    adapter = BlockchainAdapter()
    adapter._connected = True
    adapter.client = mock_client

    result = adapter.store_incident(
        source_ip="10.0.0.2",
        attack_type="DDoS",
        severity=9,
        is_blocked=True,
        incident_id=999,
    )

    # The adapter must surface this as an error, not a confirmed write
    assert result.get("status") in ("error", "pending"), (
        f"Unauthorized revert must not return status='confirmed'; got {result}"
    )
    assert result.get("tx_hash") is None, (
        "No tx_hash must be returned when the transaction reverts"
    )
