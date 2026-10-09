"""Audit B05: a chain write that outlives the adapter's timeout must not be submitted twice.

The adapter waits `blockchain_tx_timeout_seconds` for a write; the client waits
longer than that for the receipt, in a thread that cannot be stopped. A write
that was broadcast and then timed out used to come back with no hash, the
incident went to "retry", and the reconciler submitted it again: two on-chain
incidents for one detection.

The decision taken: the client reports the hash as soon as it has broadcast,
before any receipt wait; the adapter returns that hash with `pending`; the
reconciler looks it up.
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from web3.exceptions import TransactionNotFound

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.incident import BlockedIP, Incident
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.reconciliation import reconcile_blockchain_outbox

bridge_path = Path(__file__).resolve().parent.parent.parent / "blockchain" / "web3_bridge"
if str(bridge_path) not in sys.path:
    sys.path.insert(0, str(bridge_path))

from web3_client import BlockchainClient  # noqa: E402

TX = "0x" + "ab" * 32


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(bind=engine)
    for when in ("before", "after"):
        db = SessionLocal()
        try:
            db.query(BlockedIP).delete()
            db.query(Incident).delete()
            db.commit()
        finally:
            db.close()
        if when == "before":
            yield


class SlowChain:
    """Broadcasts at once, then takes longer than the adapter will wait."""

    def __init__(self, receipt_wait: float = 0.8):
        self.receipt_wait = receipt_wait
        self.submissions = 0
        self.w3 = MagicMock()
        self.w3.eth.get_transaction_receipt.side_effect = TransactionNotFound("not mined yet")
        self.contract = MagicMock()

    def log_incident(self, source_ip, attack_type, severity, is_blocked, sqlite_incident_id, on_broadcast=None):
        self.submissions += 1
        if on_broadcast is not None:
            on_broadcast(TX)
        time.sleep(self.receipt_wait)
        return {"tx_hash": TX, "block_number": 7, "incident_id": 1, "status": "confirmed"}

    def get_chain_id(self):
        return 1337


def _adapter(client) -> BlockchainAdapter:
    with patch.object(BlockchainAdapter, "__init__", lambda self: None):
        adapter = BlockchainAdapter()
    adapter.client, adapter._connected, adapter.error = client, True, None
    return adapter


def test_the_client_reports_the_hash_before_it_waits_for_the_receipt():
    order = []
    tx_hash = MagicMock()
    tx_hash.hex.return_value = TX
    with patch.object(BlockchainClient, "__init__", lambda self: None):
        client = BlockchainClient()
    client.contract = MagicMock()
    client.private_key = ""
    client.w3 = MagicMock()
    client._send_contract_tx = MagicMock(side_effect=lambda fn: order.append("broadcast") or tx_hash)

    def wait(*args, **kwargs):
        order.append("receipt wait")
        raise TimeoutError("no receipt")

    client.w3.eth.wait_for_transaction_receipt.side_effect = wait
    result = client.log_incident("10.0.0.2", "PortScan", 7, True, 1,
                                 on_broadcast=lambda h: order.append(f"reported {h}"))
    assert order == ["broadcast", f"reported {TX}", "receipt wait"]
    assert result["status"] == "pending" and result["tx_hash"] == TX


def test_a_timeout_after_broadcast_returns_the_hash_as_pending(monkeypatch):
    monkeypatch.setattr(settings, "blockchain_tx_timeout_seconds", 0.2)
    chain = SlowChain()
    result = _adapter(chain).store_incident("10.0.0.2", "PortScan", 7, True, 1)
    assert result["status"] == "pending"
    assert result["tx_hash"] == TX, "the write was broadcast; without its hash it is submitted again"
    assert chain.submissions == 1


def test_a_write_that_timed_out_after_broadcast_is_looked_up_not_resubmitted(monkeypatch):
    """The double write itself: one incident, a slow chain, two reconciler cycles."""
    monkeypatch.setattr(settings, "blockchain_tx_timeout_seconds", 0.2)
    db = SessionLocal()
    try:
        incident = Incident(source_ip="10.0.0.2", attack_type="PortScan", threat_score=0.9, severity=7,
                            is_blocked=True, blockchain_tx=None, blockchain_status="retry",
                            blockchain_retry_count=0)
        db.add(incident)
        db.commit()
        incident_id = incident.id
    finally:
        db.close()

    chain = SlowChain()
    with patch.object(BlockchainAdapter, "get_instance", return_value=_adapter(chain)):
        reconcile_blockchain_outbox(max_batch=10)   # submits; the adapter gives up waiting
        reconcile_blockchain_outbox(max_batch=10)   # must look the hash up, not submit again

    db = SessionLocal()
    try:
        row = db.get(Incident, incident_id)
        assert chain.submissions == 1, "the incident was written to the chain twice"
        assert row.blockchain_tx == TX
        assert row.blockchain_status == "pending"
        assert chain.w3.eth.get_transaction_receipt.called, "the reconciler never looked the hash up"
    finally:
        db.close()
