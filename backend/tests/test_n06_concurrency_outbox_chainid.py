# backend/tests/test_n06_concurrency_outbox_chainid.py
"""
PHASE N — BRICK N-06 UNIT & INTEGRATION TESTS
Concurrency, Nonce Management, Atomic Outbox Claim, Pending Timeout & Chain ID Safety.

Tests cover:
- N06-SEC-01: Thread-safe nonce assignment and concurrent private-key signing.
- N06-SEC-02: Atomic outbox claim reservation, lease timeout recovery, duplicate prevention.
- N06-SEC-03: Pending transaction timeout expiry, bounded retries, permanent failure.
- N06-SEC-04: Configurable expected chain ID validation and fail-closed behavior.
"""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from web3 import Web3

# Ensure web3_bridge and backend are importable
bridge_path = (Path(__file__).resolve().parent.parent.parent / "blockchain" / "web3_bridge").resolve()
sys.path.insert(0, str(bridge_path))
backend_path = (Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(backend_path))

from web3_client import BlockchainClient
from app.config import settings
from app.database import SessionLocal
from app.models.incident import Incident
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.reconciliation import reconcile_blockchain_outbox
from app.services.threat_analyzer import ThreatAnalyzer


# ─── N06-SEC-01: Nonce Management & Concurrency ──────────────────────────────

def test_t1_concurrent_private_key_submissions_increment_nonces():
    """T1: Concurrent private-key submissions do not reuse the same nonce."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 1337
    client._nonce_lock = threading.Lock()
    client._managed_nonce = None

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 10
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337

    captured_nonces = []
    def mock_sign(tx_dict, private_key):
        captured_nonces.append(tx_dict["nonce"])
        mock_signed = MagicMock()
        mock_signed.raw_transaction = b"fake_raw"
        return mock_signed

    mock_w3.eth.account.sign_transaction = mock_sign
    mock_w3.eth.send_raw_transaction.return_value = b"\xaa\xbb\xcc\xdd"
    client.w3 = mock_w3

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 100000
    mock_fn.build_transaction.side_effect = lambda d: d

    # Run 5 concurrent transactions
    threads = []
    for _ in range(5):
        t = threading.Thread(target=client._send_contract_tx, args=(mock_fn,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    assert len(captured_nonces) == 5
    assert sorted(captured_nonces) == [10, 11, 12, 13, 14], f"Nonces were reused or misordered: {captured_nonces}"


def test_t2_two_concurrent_blockchain_transactions_both_succeed():
    """T2: Two concurrent transactions both sign and return distinct hashes."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 1337
    client._nonce_lock = threading.Lock()
    client._managed_nonce = None

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 42
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337

    tx_counter = 0
    def mock_send_raw(raw):
        nonlocal tx_counter
        tx_counter += 1
        return bytes([tx_counter] * 32)

    mock_w3.eth.send_raw_transaction = mock_send_raw
    mock_w3.eth.account.sign_transaction.side_effect = lambda tx, private_key: MagicMock(raw_transaction=b"raw")
    client.w3 = mock_w3

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 50000
    mock_fn.build_transaction.side_effect = lambda d: d

    res1 = client._send_contract_tx(mock_fn)
    res2 = client._send_contract_tx(mock_fn)

    assert res1 != res2
    assert client._managed_nonce == 44


def test_t3_nonce_error_resync_recovers_gracefully():
    """T3: Broadcast failure resyncs managed nonce from node on subsequent call."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 1337
    client._nonce_lock = threading.Lock()
    client._managed_nonce = 100

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 105
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337
    # First send fails, second succeeds
    mock_w3.eth.send_raw_transaction.side_effect = [RuntimeError("mempool reject"), b"\x01" * 32]
    mock_w3.eth.account.sign_transaction.side_effect = lambda tx, private_key: MagicMock(raw_transaction=b"raw")
    client.w3 = mock_w3

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 50000
    mock_fn.build_transaction.side_effect = lambda d: d

    with pytest.raises(RuntimeError, match="mempool reject"):
        client._send_contract_tx(mock_fn)

    # Subsequent transaction queries fresh node nonce (105) and succeeds
    tx_hash = client._send_contract_tx(mock_fn)
    assert tx_hash == b"\x01" * 32
    assert client._managed_nonce == 106


def test_t4_node_account_mode_passes_through_transact():
    """T4: In node_account mode, transact() is invoked directly without local raw nonce management."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "node_account"
    client.account = "0xNodeAccount000000000000000000000000000000"
    client.private_key = ""
    client.chain_id = 1337

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 80000
    mock_fn.transact.return_value = b"\x99" * 32

    tx_hash = client._send_contract_tx(mock_fn)
    assert tx_hash == b"\x99" * 32
    mock_fn.transact.assert_called_once()


# ─── N06-SEC-02: Outbox Atomic Claim & Duplicate Prevention ──────────────────

def test_t5_concurrent_outbox_workers_cannot_claim_same_incident():
    """T5: Atomic claim reservation ensures only one worker processes an incident."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.55",
            attack_type="PortScan",
            threat_score=0.9,
            severity=8,
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

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.store_incident.return_value = {
        "status": "confirmed",
        "tx_hash": "0xclaimtesttx00000000000000000000000000000000000000000000000000000001",
        "incident_id": 999,
        "chain_id": 1337,
        "contract_address": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
        "block_number": 500,
    }

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        # Run two outbox reconciliations concurrently
        res1 = []
        res2 = []
        t1 = threading.Thread(target=lambda: res1.append(reconcile_blockchain_outbox(max_batch=10)))
        t2 = threading.Thread(target=lambda: res2.append(reconcile_blockchain_outbox(max_batch=10)))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    # Total successful writes across both workers must be exactly 1
    total_retried = (res1[0].get("retried_success", 0) if res1 else 0) + (res2[0].get("retried_success", 0) if res2 else 0)
    assert total_retried == 1, f"Expected exactly 1 retry success, got {total_retried}"

    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "confirmed"
    assert row.blockchain_tx is not None
    db.close()


def test_t6_submitting_incident_not_selected_by_reconciliation_worker():
    """T6: An incident with blockchain_status='submitting' is skipped by reconciliation worker."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.56",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=True,
            blockchain_tx=None,
            blockchain_status="submitting",
            blockchain_claimed_at=datetime.now(timezone.utc),
            blockchain_retry_count=0,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        summary = reconcile_blockchain_outbox(max_batch=10)

    # Must not have attempted store_incident
    mock_adapter.store_incident.assert_not_called()
    assert summary["retried_success"] == 0


def test_t7_stale_claim_lease_is_recovered_after_timeout():
    """T7: An incident stuck in 'submitting' with an expired lease is reclaimed and processed."""
    db = SessionLocal()
    try:
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        inc = Incident(
            source_ip="192.168.1.57",
            attack_type="Botnet",
            threat_score=0.88,
            severity=8,
            is_blocked=True,
            blockchain_tx=None,
            blockchain_status="submitting",
            blockchain_claimed_at=stale_time,
            blockchain_retry_count=0,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.store_incident.return_value = {
        "status": "confirmed",
        "tx_hash": "0xstaleleaserecover00000000000000000000000000000000000000000000000001",
        "incident_id": 1001,
        "chain_id": 1337,
        "contract_address": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
        "block_number": 510,
    }

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        summary = reconcile_blockchain_outbox(max_batch=10)

    assert summary["retried_success"] >= 1
    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "confirmed"
    assert row.blockchain_incident_id == 1001
    db.close()


def test_t8_failed_submission_returns_incident_to_retry_state():
    """T8: Failed outbox store_incident sets blockchain_status='retry' and increments retry count."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.58",
            attack_type="PortScan",
            threat_score=0.9,
            severity=7,
            is_blocked=True,
            blockchain_tx=None,
            blockchain_status="no_tx",
            blockchain_retry_count=1,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.store_incident.return_value = {
        "status": "error",
        "error": "RPC connection refused",
    }

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        summary = reconcile_blockchain_outbox(max_batch=10)

    assert summary["retried_failed"] >= 1
    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "retry"
    assert row.blockchain_retry_count == 2
    assert "RPC connection refused" in row.blockchain_last_error
    db.close()


# ─── N06-SEC-03: Pending Transaction Timeout & Expiry ────────────────────────

def test_t9_pending_transaction_below_timeout_remains_pending():
    """T9: A pending transaction created recently stays pending if receipt is not yet available."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.59",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=True,
            blockchain_tx="0xpendingrecent0000000000000000000000000000000000000000000000000001",
            blockchain_status="pending",
            blockchain_pending_since=datetime.now(timezone.utc) - timedelta(seconds=30),
            blockchain_incident_id=None,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.client.w3.eth.get_transaction_receipt.return_value = None

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        reconcile_blockchain_outbox(max_batch=10)

    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "pending"
    assert row.blockchain_tx is not None
    db.close()


def test_t10_pending_transaction_beyond_timeout_transitions_to_retry():
    """T10: A pending transaction exceeding pending timeout is transitioned to retry with tx cleared."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.60",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=True,
            blockchain_tx="0xpendingold0000000000000000000000000000000000000000000000000000001",
            blockchain_status="pending",
            blockchain_pending_since=datetime.now(timezone.utc) - timedelta(seconds=300),
            blockchain_retry_count=0,
            blockchain_incident_id=None,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.client.w3.eth.get_transaction_receipt.return_value = None

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        reconcile_blockchain_outbox(max_batch=10)

    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "retry"
    assert row.blockchain_tx is None
    assert row.blockchain_retry_count == 1
    assert "timed out after" in (row.blockchain_last_error or "")
    db.close()


def test_t11_timed_out_pending_transaction_reaches_permanent_failure():
    """T11: When pending timeout occurs and max retries are reached, transitions to permanent_failure."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.61",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=True,
            blockchain_tx="0xpendingexhausted00000000000000000000000000000000000000000000000001",
            blockchain_status="pending",
            blockchain_pending_since=datetime.now(timezone.utc) - timedelta(seconds=300),
            blockchain_retry_count=4,
            blockchain_incident_id=None,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.client.w3.eth.get_transaction_receipt.return_value = None

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        reconcile_blockchain_outbox(max_batch=10)

    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_status == "permanent_failure"
    assert row.blockchain_retry_count >= 5
    db.close()


def test_t12_rpc_exception_during_receipt_poll_does_not_mark_dropped():
    """T12: If RPC raises connection error during receipt poll, status remains pending."""
    db = SessionLocal()
    try:
        inc = Incident(
            source_ip="192.168.1.62",
            attack_type="DDoS",
            threat_score=0.95,
            severity=9,
            is_blocked=True,
            blockchain_tx="0xpendingrpcerr0000000000000000000000000000000000000000000000000001",
            blockchain_status="pending",
            blockchain_pending_since=datetime.now(timezone.utc) - timedelta(seconds=300),
            blockchain_incident_id=None,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        inc_id = inc.id
    finally:
        db.close()

    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.client.w3 = MagicMock()
    mock_adapter.client.contract = MagicMock()
    mock_adapter.client.w3.eth.get_transaction_receipt.side_effect = ConnectionError("Node offline")

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        reconcile_blockchain_outbox(max_batch=10)

    db = SessionLocal()
    row = db.get(Incident, inc_id)
    assert row.blockchain_tx is not None
    assert "Node offline" in (row.blockchain_last_error or "")
    db.close()


# ─── N06-SEC-04: Expected Chain ID Validation ────────────────────────────────

def test_t13_matching_expected_chain_id_succeeds():
    """T13: When BLOCKCHAIN_EXPECTED_CHAIN_ID matches node chain ID, initialization succeeds."""
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 1337
    mock_w3.eth.accounts = ["0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"]

    with patch.dict(os.environ, {
        "BLOCKCHAIN_EXPECTED_CHAIN_ID": "1337",
        "CONTRACT_ADDRESS": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
    }), patch("web3_client.Web3", return_value=mock_w3):
        client = BlockchainClient()
        assert client.expected_chain_id == 1337
        assert client.chain_id == 1337


def test_t14_mismatched_expected_chain_id_fails_closed():
    """T14: When BLOCKCHAIN_EXPECTED_CHAIN_ID differs from node chain ID, initialization raises ValueError."""
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 1337
    mock_w3.eth.accounts = ["0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"]

    with patch.dict(os.environ, {
        "BLOCKCHAIN_EXPECTED_CHAIN_ID": "1",  # Mainnet
        "CONTRACT_ADDRESS": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
    }), patch("web3_client.Web3", return_value=mock_w3):
        with pytest.raises(ValueError, match="Chain ID mismatch: connected to chain 1337, expected 1"):
            BlockchainClient()


def test_t15_unset_expected_chain_id_preserves_compatibility():
    """T15: When BLOCKCHAIN_EXPECTED_CHAIN_ID is not configured, any chain ID is permitted."""
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 31337
    mock_w3.eth.accounts = ["0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"]

    with patch.dict(os.environ, {
        "BLOCKCHAIN_EXPECTED_CHAIN_ID": "",
        "CONTRACT_ADDRESS": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
    }), patch("web3_client.Web3", return_value=mock_w3):
        client = BlockchainClient()
        assert client.expected_chain_id is None
        assert client.chain_id == 31337


def test_t16_threat_analyzer_claim_prevents_reconciliation_duplicate():
    """T16: ThreatAnalyzer creates incident in submitting state, preventing duplicate outbox processing."""
    mock_adapter = MagicMock()
    mock_adapter._connected = True
    mock_adapter.client = MagicMock()
    mock_adapter.store_incident.return_value = {
        "status": "confirmed",
        "tx_hash": "0xingestiontx000000000000000000000000000000000000000000000000000001",
        "incident_id": 888,
        "chain_id": 1337,
        "contract_address": "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24",
        "block_number": 400,
    }

    with patch.object(BlockchainAdapter, "get_instance", return_value=mock_adapter):
        analyzer = ThreatAnalyzer()
        prediction = {"source_scores": {"10.0.0.99": 0.95}}
        flows = [{"src_ip": "10.0.0.99", "dst_ip": "10.0.0.1", "src_port": 1234, "dst_port": 80, "protocol": "TCP", "packet_count": 100, "byte_count": 5000, "duration": 1.0}]
        
        alerts, healing = analyzer.evaluate(prediction, flows)
        assert len(alerts) == 1
        incident_id = int(alerts[0]["id"].replace("alert-", ""))

    db = SessionLocal()
    row = db.get(Incident, incident_id)
    assert row.blockchain_status == "confirmed"
    assert row.blockchain_tx == "0xingestiontx000000000000000000000000000000000000000000000000000001"
    assert row.blockchain_claimed_at is None
    db.close()


def test_t17_high_concurrency_ten_threads_distinct_nonces():
    """T17: 10 concurrent threads in private-key mode strictly assign sequential distinct nonces 100..109."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 1337
    client._nonce_lock = threading.Lock()
    client._managed_nonce = None

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 100
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337

    used_nonces = []
    def mock_sign(tx_dict, private_key):
        used_nonces.append(tx_dict["nonce"])
        mock_signed = MagicMock()
        mock_signed.raw_transaction = b"fake_raw"
        return mock_signed

    mock_w3.eth.account.sign_transaction = mock_sign
    mock_w3.eth.send_raw_transaction.return_value = b"\x01" * 32
    client.w3 = mock_w3

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 40000
    mock_fn.build_transaction.side_effect = lambda d: d

    threads = [threading.Thread(target=client._send_contract_tx, args=(mock_fn,)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(used_nonces) == 10
    assert sorted(used_nonces) == list(range(100, 110))
    assert client._managed_nonce == 110


def test_t18_signed_transaction_includes_validated_chain_id():
    """T18: Transaction dict submitted to sign_transaction strictly contains the validated chain_id."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 42161  # Arbitrum One
    client._nonce_lock = threading.Lock()
    client._managed_nonce = 5

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 5
    mock_w3.eth.gas_price = 100000000
    mock_w3.eth.chain_id = 42161

    captured_tx = {}
    def mock_sign(tx_dict, private_key):
        captured_tx.update(tx_dict)
        mock_signed = MagicMock()
        mock_signed.raw_transaction = b"fake_raw"
        return mock_signed

    mock_w3.eth.account.sign_transaction = mock_sign
    mock_w3.eth.send_raw_transaction.return_value = b"\x01" * 32
    client.w3 = mock_w3

    mock_fn = MagicMock()
    mock_fn.estimate_gas.return_value = 30000
    mock_fn.build_transaction.side_effect = lambda d: d

    client._send_contract_tx(mock_fn)
    assert captured_tx.get("chainId") == 42161
    assert captured_tx.get("nonce") == 5


def test_t19_claim_survives_separate_sqlalchemy_sessions():
    """T19: A claim written in session 1 is visible as claimed in session 2."""
    db1 = SessionLocal()
    inc = Incident(
        source_ip="192.168.1.70",
        attack_type="PortScan",
        threat_score=0.9,
        severity=7,
        is_blocked=True,
        blockchain_tx=None,
        blockchain_status="submitting",
        blockchain_claimed_at=datetime.now(timezone.utc),
    )
    db1.add(inc)
    db1.commit()
    inc_id = inc.id
    db1.close()

    db2 = SessionLocal()
    row = db2.get(Incident, inc_id)
    assert row.blockchain_status == "submitting"
    assert row.blockchain_claimed_at is not None
    db2.close()


def test_t20_release_node_uses_nonce_lock():
    """T20: release_node() in private-key mode acquires nonce lock and increments nonce."""
    client = BlockchainClient.__new__(BlockchainClient)
    client.mode = "private_key"
    client.account = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
    client.private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    client.chain_id = 1337
    client._nonce_lock = threading.Lock()
    client._managed_nonce = 20

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 20
    mock_w3.eth.gas_price = 20000000000
    mock_w3.eth.chain_id = 1337
    mock_w3.eth.send_raw_transaction.return_value = b"\x77" * 32
    
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_receipt.transactionHash = b"\x77" * 32
    mock_receipt.blockNumber = 888
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
    mock_w3.eth.account.sign_transaction.side_effect = lambda tx, private_key: MagicMock(raw_transaction=b"raw")
    client.w3 = mock_w3

    mock_contract = MagicMock()
    mock_contract.functions.releaseNode.return_value.estimate_gas.return_value = 35000
    mock_contract.functions.releaseNode.return_value.build_transaction.side_effect = lambda d: d
    client.contract = mock_contract

    res = client.release_node("192.168.1.70", "MANUAL_OVERRIDE")
    assert res["status"] == "confirmed"
    assert client._managed_nonce == 21


def test_t21_adapter_propagates_expected_chain_id():
    """T21: BlockchainAdapter._connect propagates blockchain_expected_chain_id to env."""
    adapter = BlockchainAdapter.__new__(BlockchainAdapter)
    adapter._connected = False
    adapter.client = None
    adapter.error = None

    with patch.object(settings, "blockchain_expected_chain_id", 1337):
        with patch.dict(os.environ, {}, clear=False):
            # Run _connect with mock bridge
            with patch("web3_client.BlockchainClient") as mock_client_cls:
                adapter._connect()
                assert os.environ.get("BLOCKCHAIN_EXPECTED_CHAIN_ID") == "1337"

