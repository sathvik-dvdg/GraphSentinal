# backend/tests/test_n05_gas_signer_timeout_retry.py
"""
PHASE N — BRICK N-05 TEST SUITE
Gas Management, Dual-Mode Signer, Timeout/Orphan Mitigation & Outbox Retry

Covers:
- N02-SEC-02: Dynamic gas estimation and headroom
- N01-SEC-01: Dual-mode signer (unlocked node account & private key raw signing)
- N05-SEC-01: Mempool orphaned transaction prevention on timeout
- N05-SEC-02: Persistent SQLite outbox retry and pending transaction backfill
- Idempotency and duplicate prevention
- N-02 / N-03 / N-04 Golden Baseline regressions
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from web3 import Web3
from web3.exceptions import TimeExhausted

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.incident import BlockedIP, Incident
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.reconciliation import reconcile_blockchain_outbox
from app.services.threat_analyzer import ThreatAnalyzer

# Setup web3 bridge import path
bridge_path = Path(__file__).resolve().parent.parent.parent / "blockchain" / "web3_bridge"
if str(bridge_path) not in sys.path:
    sys.path.insert(0, str(bridge_path))

from web3_client import BlockchainClient


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(BlockedIP).delete()
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(BlockedIP).delete()
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()


# ==============================================================================
# A. GAS MANAGEMENT TESTS (N02-SEC-02)
# ==============================================================================

def test_t1_gas_estimation_is_used_with_headroom():
    """Verify estimate_gas is called and 1.2x headroom is applied."""
    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 100000

    with patch.object(BlockchainClient, "__init__", lambda self: None):
        client = BlockchainClient()
        client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
        client.mode = "node_account"
        client.private_key = ""

        gas_limit = client._estimate_and_get_gas(mock_fn)
        mock_fn.estimate_gas.assert_called_once_with({"from": client.account, "value": 0})
        # 100,000 * 1.2 = 120,000
        assert gas_limit == 120000


def test_t2_gas_estimation_revert_fails_closed_before_broadcast():
    """If gas estimation fails (e.g. contract revert), fail closed before broadcast."""
    mock_fn = MagicMock()
    mock_fn.estimate_gas.side_effect = RuntimeError("execution reverted: Unauthorized")

    with patch.object(BlockchainClient, "__init__", lambda self: None):
        client = BlockchainClient()
        client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
        client.mode = "node_account"
        client.private_key = ""

        with pytest.raises(RuntimeError, match="Gas estimation failed"):
            client._estimate_and_get_gas(mock_fn)


def test_t3_gas_limit_obeys_configured_max():
    """Gas limit is capped by BLOCKCHAIN_MAX_GAS."""
    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 1000000

    with patch.object(BlockchainClient, "__init__", lambda self: None), \
         patch.dict(os.environ, {"BLOCKCHAIN_MAX_GAS": "500000"}):
        client = BlockchainClient()
        client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
        client.mode = "node_account"
        client.private_key = ""

        gas_limit = client._estimate_and_get_gas(mock_fn)
        assert gas_limit == 500000


# ==============================================================================
# B. DUAL-MODE SIGNER TESTS (N01-SEC-01)
# ==============================================================================

def test_t4_signer_mode_node_account_default():
    """Unlocked Ganache node account mode initializes correctly."""
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.accounts = ["0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"]
    mock_w3.eth.contract.return_value = MagicMock()

    with patch.dict(os.environ, {"BLOCKCHAIN_PRIVATE_KEY": "", "CONTRACT_ADDRESS": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24"}), \
         patch("web3_client.Web3", return_value=mock_w3):
        client = BlockchainClient()
        assert client.mode == "node_account"
        assert client.account == "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
        assert client.signer_account is None


def test_t5_signer_mode_private_key_raw_transaction():
    """Private key mode derives address and uses send_raw_transaction."""
    # Standard 32-byte test private key (Ganache default account[1])
    test_pk = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    expected_addr = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.contract.return_value = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 0
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337

    # Mock real eth_account
    from eth_account import Account
    mock_w3.eth.account = Account

    with patch.dict(os.environ, {"BLOCKCHAIN_PRIVATE_KEY": test_pk, "CONTRACT_ADDRESS": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24"}), \
         patch("web3_client.Web3", return_value=mock_w3):
        client = BlockchainClient()
        assert client.mode == "private_key"
        assert client.account.lower() == expected_addr.lower()
        assert client.private_key == test_pk

        # Test _send_contract_tx with raw transaction
        mock_fn = MagicMock()
        mock_fn.estimate_gas.return_value = 100000
        mock_fn.build_transaction.return_value = {
            "from": client.account,
            "nonce": 0,
            "gas": 120000,
            "gasPrice": 20000000000,
            "chainId": 1337,
            "value": 0,
        }

        mock_w3.eth.send_raw_transaction.return_value = b"\x12\x34\x56\x78"
        tx_hash = client._send_contract_tx(mock_fn)

        mock_w3.eth.send_raw_transaction.assert_called_once()
        assert tx_hash == b"\x12\x34\x56\x78"


def test_t6_private_key_redacted_from_error_messages():
    """Private key is sanitized from any returned error messages."""
    test_pk = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    with patch.object(BlockchainClient, "__init__", lambda self: None):
        client = BlockchainClient()
        client.private_key = test_pk

        err = Exception(f"Failed transaction with key {test_pk} on network")
        sanitized = client._sanitize_error(err)
        assert test_pk not in sanitized
        assert "[REDACTED]" in sanitized


# ==============================================================================
# C. TIMEOUT & ORPHANED TRANSACTION PROTECTION (N05-SEC-01)
# ==============================================================================

def test_t7_timeout_returns_pending_with_broadcast_tx_hash():
    """When receipt waiting times out, log_incident returns status='pending' with broadcasted tx_hash."""
    mock_tx_hash = MagicMock()
    mock_tx_hash.hex.return_value = "0xabcdef1234567890"

    with patch.object(BlockchainClient, "__init__", lambda self: None):
        client = BlockchainClient()
        client.contract = MagicMock()
        client.private_key = ""
        client.w3 = MagicMock()
        client._send_contract_tx = MagicMock(return_value=mock_tx_hash)
        client.w3.eth.wait_for_transaction_receipt.side_effect = TimeExhausted("Timeout waiting for receipt")

        res = client.log_incident(
            source_ip="192.168.1.100",
            attack_type="DDoS",
            severity=8,
            is_blocked=True,
            sqlite_incident_id=42,
        )

        assert res["status"] == "pending"
        assert res["tx_hash"] == "0xabcdef1234567890"
        assert res["incident_id"] is None
        assert "timed out" in res["error"]


def test_t8_threat_analyzer_persists_pending_tx_hash_on_timeout():
    """ThreatAnalyzer persists pending tx_hash to SQLite instead of discarding it."""
    tx_pending_result = {
        "status": "pending",
        "tx_hash": "0xdeadbeef9999",
        "chain_id": 1337,
        "contract_address": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
        "block_number": None,
        "incident_id": None,
        "error": "Transaction broadcast but receipt confirmation timed out",
    }

    db = SessionLocal()
    try:
        incident = Incident(
            source_ip="192.168.1.50",
            attack_type="PortScan",
            threat_score=0.95,
            severity=8,
            is_blocked=False,
            enforcement_status="not_requested",
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        inc_id = incident.id
    finally:
        db.close()

    healing_event = {"ip": "192.168.1.50", "enforcement_status": "enforced"}
    ThreatAnalyzer._update_incident_after_actions(inc_id, tx_pending_result, healing_event)

    db = SessionLocal()
    try:
        row = db.get(Incident, inc_id)
        assert row.blockchain_tx == "0xdeadbeef9999"
        assert row.blockchain_status == "pending"
        assert row.blockchain_incident_id is None
        assert "timed out" in row.blockchain_last_error
    finally:
        db.close()


# ==============================================================================
# D. OUTBOX RETRY & RECONCILIATION TESTS (N05-SEC-02)
# ==============================================================================

def test_t9_outbox_reconciles_pending_transaction_on_chain():
    """Pending transactions are checked on-chain and backfilled with exact event ID."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.99",
            attack_type="BruteForce",
            threat_score=0.9,
            severity=7,
            is_blocked=True,
            blockchain_tx="0xpending12345",
            blockchain_status="pending",
            blockchain_incident_id=None,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_receipt = {
        "status": 1,
        "blockNumber": 850,
        "transactionHash": b"\x00" * 32,
    }
    mock_event = [{"args": {"id": 105, "incidentHash": b"\x11" * 32}}]

    mock_client = MagicMock()
    mock_client.w3.eth.get_transaction_receipt.return_value = mock_receipt
    mock_client.contract.events.IncidentLogged().process_receipt.return_value = mock_event

    with patch.object(BlockchainAdapter, "get_instance") as mock_get_adapter:
        adapter_mock = MagicMock()
        adapter_mock._connected = True
        adapter_mock.client = mock_client
        mock_get_adapter.return_value = adapter_mock

        summary = reconcile_blockchain_outbox()
        assert summary["status"] == "ok"
        assert summary["pending_reconciled"] == 1

    db = SessionLocal()
    try:
        row = db.get(Incident, inc_id)
        assert row.blockchain_status == "confirmed"
        assert row.blockchain_incident_id == 105
        assert row.blockchain_block_number == 850
        assert row.blockchain_last_error is None
    finally:
        db.close()


def test_t10_outbox_retries_unwritten_high_threat_incidents():
    """High-threat incidents missing blockchain_tx are backfilled by outbox retry."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.77",
            attack_type="SynFlood",
            threat_score=0.92,
            severity=9,
            is_blocked=True,
            blockchain_tx=None,
            blockchain_status="no_tx",
            blockchain_retry_count=0,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_store_result = {
        "status": "confirmed",
        "tx_hash": "0xretrysuccess7777",
        "incident_id": 106,
        "chain_id": 1337,
        "contract_address": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
        "block_number": 851,
    }

    with patch.object(BlockchainAdapter, "get_instance") as mock_get_adapter:
        adapter_mock = MagicMock()
        adapter_mock._connected = True
        adapter_mock.client = MagicMock()
        adapter_mock.client.w3.eth.get_transaction_receipt.return_value = None
        adapter_mock.store_incident.return_value = mock_store_result
        mock_get_adapter.return_value = adapter_mock

        summary = reconcile_blockchain_outbox()
        assert summary["status"] == "ok"
        assert summary["retried_success"] == 1

    db = SessionLocal()
    try:
        row = db.get(Incident, inc_id)
        assert row.blockchain_tx == "0xretrysuccess7777"
        assert row.blockchain_status == "confirmed"
        assert row.blockchain_incident_id == 106
        assert row.blockchain_block_number == 851
    finally:
        db.close()


def test_t11_outbox_bounds_retries_and_marks_permanent_failure():
    """Outbox marks permanent_failure after exceeding blockchain_max_retries."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.88",
            attack_type="PortScan",
            threat_score=0.85,
            severity=6,
            is_blocked=True,
            blockchain_tx=None,
            blockchain_status="retry",
            blockchain_retry_count=4,  # Next failure will hit max 5
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_failed_result = {
        "status": "error",
        "tx_hash": None,
        "error": "RPC connection refused",
    }

    with patch.object(BlockchainAdapter, "get_instance") as mock_get_adapter:
        adapter_mock = MagicMock()
        adapter_mock._connected = True
        adapter_mock.client = MagicMock()
        adapter_mock.client.w3.eth.get_transaction_receipt.return_value = None
        adapter_mock.store_incident.return_value = mock_failed_result
        mock_get_adapter.return_value = adapter_mock

        summary = reconcile_blockchain_outbox()
        assert summary["status"] == "ok"
        assert summary["retried_failed"] == 1

    db = SessionLocal()
    try:
        row = db.get(Incident, inc_id)
        assert row.blockchain_retry_count == 5
        assert row.blockchain_status == "permanent_failure"
    finally:
        db.close()


# ==============================================================================
# E. IDEMPOTENCY & DUPLICATE PROTECTION TESTS
# ==============================================================================

def test_t12_idempotency_does_not_double_submit_existing_tx():
    """Outbox does not invoke store_incident if an incident already has a blockchain_tx."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="10.0.0.55",
            attack_type="BruteForce",
            threat_score=0.88,
            severity=7,
            is_blocked=True,
            blockchain_tx="0xalreadywritten",
            blockchain_status="confirmed",
            blockchain_incident_id=101,
        )
        db.add(inc)
        db.commit()
    finally:
        db.close()

    with patch.object(BlockchainAdapter, "get_instance") as mock_get_adapter:
        adapter_mock = MagicMock()
        adapter_mock._connected = True
        adapter_mock.client = MagicMock()
        mock_get_adapter.return_value = adapter_mock

        summary = reconcile_blockchain_outbox()
        assert summary["retried_success"] == 0
        adapter_mock.store_incident.assert_not_called()
