# [WSL2]
# backend/tests/test_n04_receipt_correlation_release.py
# ─────────────────────────────────────────────────────────────────────────────
# N-04 Backend Tests — Web3 Receipt Correlation, releaseNode, and Metadata
#
# Tests covering:
# N04-T1  log_incident extracts exact ID from IncidentLogged event (not getIncidentCount)
# N04-T2  Interleaved/Concurrent simulation: Tx A retains ID X even when count advances to X+1
# N04-T3  log_incident returns explicit error when IncidentLogged event is absent from receipt
# N04-T4  log_incident returns status='failed' when transaction receipt status is 0 (reverted)
# N04-T5  release_node invokes contract.functions.releaseNode and returns confirmed receipt
# N04-T6  release_node returns error/failed on transaction revert or exception
# N04-T7  BlockchainAdapter.release_node delegates properly and enriches chain context
# N04-T8  POST /api/v1/block action="unblock" invokes adapter.release_node (not store_incident)
# N04-T9  POST /api/v1/block action="block" stores blockchain_incident_id on Incident row
# N04-T10 ThreatAnalyzer persists exact blockchain_incident_id from tx_result to Incident row
# N04-T11 GET /api/v1/forensics includes blockchain_incident_id in serialized IncidentRecord
# N04-T12 [N02 Regression] releaseNode rejects unauthorized / non-deployer callers
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.incident import Incident, BlockedIP, EnforcementAction
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.threat_analyzer import ThreatAnalyzer


import sys
from pathlib import Path

bridge_path = Path(__file__).resolve().parent.parent.parent / "blockchain" / "web3_bridge"
if bridge_path.exists() and str(bridge_path) not in sys.path:
    sys.path.insert(0, str(bridge_path))

from web3_client import BlockchainClient


client = TestClient(app)
API_HEADERS = {"X-API-Key": settings.backend_api_token}


# ─── N04-T1: Receipt Event ID Extraction ─────────────────────────────────────
def test_t1_log_incident_extracts_id_from_receipt_event():
    """T1: BlockchainClient.log_incident decodes IncidentLogged from receipt, not getIncidentCount."""

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.accounts = ["0xDeployer00000000000000000000000000000000"]
    mock_w3.eth.chain_id = 1337

    # Mock receipt
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_receipt.blockNumber = 42
    mock_receipt.transactionHash.hex.return_value = "0x" + "a" * 64
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    # Mock contract & event processing
    mock_contract = MagicMock()
    mock_tx_fn = MagicMock()
    mock_tx_fn.transact.return_value = b"\xaa" * 32
    mock_contract.functions.logIncident.return_value = mock_tx_fn

    # Event decoding returns exact ID = 100
    mock_event = MagicMock()
    mock_event.process_receipt.return_value = [
        {
            "args": {
                "id": 100,
                "incidentHash": b"\xbb" * 32,
                "sourceIP": "10.0.0.99",
                "attackLabel": "DDoS",
                "timestamp": 1700000000,
            }
        }
    ]
    mock_contract.events.IncidentLogged.return_value = mock_event

    # getIncidentCount would return 999 if called (proving it is NOT used)
    mock_contract.functions.getIncidentCount.return_value.call.return_value = 999

    with patch("web3_client.Web3") as mock_web3_cls, \
         patch("builtins.open", MagicMock()), \
         patch("json.load", return_value=[]):
        mock_web3_cls.return_value = mock_w3
        mock_web3_cls.HTTPProvider.return_value = MagicMock()
        mock_web3_cls.to_checksum_address.return_value = "0xContract00000000000000000000000000000000"

        bclient = BlockchainClient.__new__(BlockchainClient)
        bclient.w3 = mock_w3
        bclient.contract = mock_contract
        bclient.account = "0xDeployer00000000000000000000000000000000"

        result = bclient.log_incident("10.0.0.99", "DDoS", 8, False, 1)

    assert result["status"] == "confirmed"
    assert result["incident_id"] == 100, f"Expected event ID 100, got {result['incident_id']}"
    assert result["tx_hash"] == "0x" + "a" * 64
    assert result["block_number"] == 42
    # Ensure getIncidentCount was NEVER called
    mock_contract.functions.getIncidentCount.return_value.call.assert_not_called()


# ─── N04-T2: Race Condition Regression Guard ─────────────────────────────────
def test_t2_race_condition_guard_retains_transaction_specific_id():
    """T2: Prove Tx A's result retains exact event ID X even if global count is X+1."""

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True

    mock_receipt_a = MagicMock()
    mock_receipt_a.status = 1
    mock_receipt_a.blockNumber = 100
    mock_receipt_a.transactionHash.hex.return_value = "0x" + "1" * 64
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt_a

    mock_contract = MagicMock()
    mock_contract.functions.logIncident.return_value.transact.return_value = b"\x11" * 32

    # Tx A emitted event ID 50
    mock_event = MagicMock()
    mock_event.process_receipt.return_value = [
        {"args": {"id": 50, "incidentHash": b"\x50" * 32}}
    ]
    mock_contract.events.IncidentLogged.return_value = mock_event

    # Global count advanced to 51 (from another interleaved transaction)
    mock_contract.functions.getIncidentCount.return_value.call.return_value = 51

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xDeployer"

    result_a = bclient.log_incident("10.0.0.1", "PortScan", 5, False, 50)

    # Must be 50, NOT 51
    assert result_a["incident_id"] == 50
    assert result_a["incident_id"] != 51
    mock_contract.functions.getIncidentCount.return_value.call.assert_not_called()


# ─── N04-T3: Event Absence / Decoding Failure ────────────────────────────────
def test_t3_log_incident_fails_when_event_not_found_in_receipt():
    """T3: If IncidentLogged event is missing from receipt, returns explicit error (no getIncidentCount fallback)."""

    mock_w3 = MagicMock()
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_receipt.blockNumber = 10
    mock_receipt.transactionHash.hex.return_value = "0x" + "2" * 64
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    mock_contract = MagicMock()
    mock_contract.functions.logIncident.return_value.transact.return_value = b"\x22" * 32

    # Empty processed logs
    mock_event = MagicMock()
    mock_event.process_receipt.return_value = []
    mock_contract.events.IncidentLogged.return_value = mock_event

    # Flawed fallback would return 10
    mock_contract.functions.getIncidentCount.return_value.call.return_value = 10

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xDeployer"

    result = bclient.log_incident("10.0.0.2", "DDoS", 9, False, 2)

    assert result["status"] == "error"
    assert result["incident_id"] is None
    assert "IncidentLogged event not found" in result.get("error", "")
    mock_contract.functions.getIncidentCount.return_value.call.assert_not_called()


# ─── N04-T4: Reverted Transaction Handling ───────────────────────────────────
def test_t4_log_incident_handles_reverted_receipt():
    """T4: Receipt with status=0 returns status='failed' and no incident_id."""

    mock_w3 = MagicMock()
    mock_receipt = MagicMock()
    mock_receipt.status = 0  # Reverted
    mock_receipt.blockNumber = 12
    mock_receipt.transactionHash.hex.return_value = "0x" + "3" * 64
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    mock_contract = MagicMock()
    mock_contract.functions.logIncident.return_value.transact.return_value = b"\x33" * 32

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xDeployer"

    result = bclient.log_incident("10.0.0.3", "Botnet", 6, True, 3)

    assert result["status"] == "failed"
    assert result["incident_id"] is None


# ─── N04-T5: release_node Web3 Method Success ────────────────────────────────
def test_t5_release_node_success():
    """T5: BlockchainClient.release_node invokes releaseNode on contract and returns confirmed status."""

    mock_w3 = MagicMock()
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_receipt.blockNumber = 15
    mock_receipt.transactionHash.hex.return_value = "0x" + "4" * 64
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    mock_contract = MagicMock()
    mock_release_fn = MagicMock()
    mock_release_fn.transact.return_value = b"\x44" * 32
    mock_contract.functions.releaseNode.return_value = mock_release_fn

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xDeployer"

    result = bclient.release_node("10.0.0.5", "MANUAL_OVERRIDE")

    mock_contract.functions.releaseNode.assert_called_once_with("10.0.0.5", "MANUAL_OVERRIDE")
    assert result["status"] == "confirmed"
    assert result["tx_hash"] == "0x" + "4" * 64
    assert result["block_number"] == 15


# ─── N04-T6: release_node Web3 Method Revert/Failure ─────────────────────────
def test_t6_release_node_revert_handling():
    """T6: release_node handles contract revert properly."""

    mock_w3 = MagicMock()
    mock_contract = MagicMock()
    mock_contract.functions.releaseNode.return_value.transact.side_effect = Exception("execution reverted: IP is not blocked")

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xDeployer"

    result = bclient.release_node("10.0.0.6", "MANUAL_OVERRIDE")

    assert result["status"] == "error"
    assert result["tx_hash"] is None
    assert "IP is not blocked" in result["error"]


# ─── N04-T7: BlockchainAdapter.release_node Delegation ───────────────────────
def test_t7_adapter_release_node_delegation():
    """T7: BlockchainAdapter.release_node enriches confirmed result with chain context."""
    mock_client = MagicMock()
    mock_client.release_node.return_value = {
        "tx_hash": "0x" + "7" * 64,
        "block_number": 77,
        "status": "confirmed",
    }
    mock_client.get_chain_id.return_value = 1337

    adapter = BlockchainAdapter()
    adapter._connected = True
    adapter.client = mock_client

    result = adapter.release_node("10.0.0.7", "ADMIN_RELEASE")

    assert result["status"] == "confirmed"
    assert result["tx_hash"] == "0x" + "7" * 64
    assert result["chain_id"] == 1337
    assert result["contract_address"] == settings.contract_address


# ─── N04-T8: Manual Unblock Endpoint Integration ─────────────────────────────
def test_t8_manual_unblock_invokes_release_node():
    """T8: POST /api/v1/block action='unblock' calls adapter.release_node instead of store_incident."""
    adapter = BlockchainAdapter.get_instance()
    
    with patch.object(adapter, "release_node", return_value={"tx_hash": "0x" + "8" * 64, "block_number": 88, "status": "confirmed", "chain_id": 1337, "contract_address": "0xContract"}) as mock_release, \
         patch.object(adapter, "store_incident") as mock_store:
        
        response = client.post(
            "/api/v1/block",
            json={"ip": "10.0.0.88", "action": "unblock", "reason": "MANUAL_OVERRIDE"},
            headers=API_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unblocked"
    assert body["blockchain_tx"] == "0x" + "8" * 64
    mock_release.assert_called_once_with(ip="10.0.0.88", reason="MANUAL_OVERRIDE")
    mock_store.assert_not_called()


# ─── N04-T9: Manual Block Incident ID Persistence ────────────────────────────
def test_t9_manual_block_persists_blockchain_incident_id():
    """T9: POST /api/v1/block action='block' persists blockchain_incident_id to Incident row."""
    adapter = BlockchainAdapter.get_instance()
    expected_on_chain_id = 142

    with patch.object(adapter, "store_incident", return_value={
        "tx_hash": "0x" + "9" * 64,
        "block_number": 99,
        "incident_id": expected_on_chain_id,
        "status": "confirmed",
        "chain_id": 1337,
        "contract_address": "0xContract",
    }):
        response = client.post(
            "/api/v1/block",
            json={"ip": "10.0.0.142", "action": "block", "reason": "MANUAL_OVERRIDE"},
            headers=API_HEADERS,
        )

    assert response.status_code == 200
    
    # Check DB
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.source_ip == "10.0.0.142").order_by(Incident.id.desc()).first()
        assert incident is not None
        assert incident.blockchain_incident_id == expected_on_chain_id
        assert incident.blockchain_tx == "0x" + "9" * 64
    finally:
        db.close()


# ─── N04-T10: ThreatAnalyzer Incident ID Persistence ─────────────────────────
def test_t10_threat_analyzer_persists_blockchain_incident_id():
    """T10: ThreatAnalyzer._update_incident_after_actions sets blockchain_incident_id."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.200",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=False,
            data_source="manual",
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    tx_result = {
        "tx_hash": "0x" + "f" * 64,
        "block_number": 123,
        "incident_id": 200,
        "chain_id": 1337,
        "contract_address": "0xContract",
        "status": "confirmed",
    }
    healing_event = {"ip": "10.0.0.200", "enforcement_status": "simulated"}

    ThreatAnalyzer._update_incident_after_actions(inc_id, tx_result, healing_event)

    db = SessionLocal()
    try:
        updated = db.get(Incident, inc_id)
        assert updated.blockchain_incident_id == 200
        assert updated.blockchain_tx == "0x" + "f" * 64
        assert updated.blockchain_block_number == 123
        assert updated.blockchain_chain_id == 1337
    finally:
        db.delete(db.get(Incident, inc_id))
        db.commit()
        db.close()


# ─── N04-T11: Forensics API Returns blockchain_incident_id ───────────────────
def test_t11_forensics_response_includes_blockchain_incident_id():
    """T11: GET /api/v1/forensics returns blockchain_incident_id in incident records."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.201",
            attack_type="PortScan",
            threat_score=0.6,
            severity=6,
            is_blocked=False,
            blockchain_incident_id=201,
            blockchain_tx="0x" + "e" * 64,
            data_source="manual",
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    adapter = BlockchainAdapter()
    adapter._connected = False
    adapter.error = "offline"

    with patch.object(BlockchainAdapter, "get_instance", return_value=adapter):
        response = client.get("/api/v1/forensics", headers=API_HEADERS)

    assert response.status_code == 200
    body = response.json()
    matching = [i for i in body["incidents"] if i["id"] == inc_id]
    assert matching
    assert matching[0]["blockchain_incident_id"] == 201

    # Cleanup
    db = SessionLocal()
    try:
        db.delete(db.get(Incident, inc_id))
        db.commit()
    finally:
        db.close()


# ─── N04-T12: N-02 Authorization Regression Guard ────────────────────────────
def test_t12_release_node_rejects_unauthorized_caller():
    """T12: [N02 Regression] releaseNode reverts with Unauthorized if caller is non-deployer."""
    from web3.exceptions import ContractLogicError

    mock_w3 = MagicMock()
    mock_contract = MagicMock()
    mock_contract.functions.releaseNode.return_value.transact.side_effect = ContractLogicError("Unauthorized")

    bclient = BlockchainClient.__new__(BlockchainClient)
    bclient.w3 = mock_w3
    bclient.contract = mock_contract
    bclient.account = "0xAttacker"

    result = bclient.release_node("10.0.0.99", "ATTACKER_RELEASE")

    assert result["status"] == "error"
    assert result["tx_hash"] is None
    assert "Unauthorized" in result.get("error", "")
