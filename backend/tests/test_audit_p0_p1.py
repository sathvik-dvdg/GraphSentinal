# [WSL2]
"""Regression tests for the 2026-10-04 integration audit: B01, B02, B03, B04,
B06, B07 and B12. Each one fails on the code as it stood before the fix.

B03 and B12 are tested as a pair on purpose: B12 left the inference mode stuck
on "degraded" after one exception and B03 meant nothing read the mode, so
together a single transient error made every later block a mislabelled one.
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident


def _flow(src: str, dst_port: int = 80, packets: int = 100, byte_count: int = 10_000) -> dict:
    return {
        "src_ip": src,
        "dst_ip": "10.0.0.1",
        "src_port": 40000,
        "dst_port": dst_port,
        "protocol": "TCP",
        "packet_count": packets,
        "byte_count": byte_count,
        "duration_sec": 1.0,
        "data_source": "manual",
    }


@pytest.fixture
def simulated_enforcement(monkeypatch):
    """The local backend/.env may set ENFORCEMENT_MODE=ovs; these tests must not
    depend on a daemon being reachable."""
    monkeypatch.setattr(settings, "enforcement_mode", "simulated")


@pytest.fixture
def offline_chain(monkeypatch):
    from app.services.blockchain_adapter import BlockchainAdapter

    adapter = MagicMock()
    adapter.store_incident.return_value = {"status": "retry", "tx_hash": None, "error": "offline"}
    monkeypatch.setattr(BlockchainAdapter, "get_instance", classmethod(lambda cls: adapter))
    return adapter


# ─── B01: the readonly role must not mutate state ─────────────────────────────

def _login(client, username: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_b01_readonly_cannot_analyze_triage_or_write_chain(client):
    headers = _login(client, settings.readonly_username, settings.readonly_password)
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "readonly"

    analyze = client.post("/api/v1/analyze", json={"flows": [_flow("10.0.0.201")]}, headers=headers)
    triage = client.patch("/api/v1/incidents/1/status", json={"status": "acknowledged"}, headers=headers)
    store = client.post(
        "/api/v1/blockchain/store",
        json={"source_ip": "10.0.0.201", "attack_type": "DDoS", "severity": 5, "is_blocked": True, "sqlite_incident_id": 1},
        headers=headers,
    )
    assert (analyze.status_code, triage.status_code, store.status_code) == (403, 403, 403)

    db = SessionLocal()
    try:
        assert db.query(BlockedIP).filter(BlockedIP.ip_address == "10.0.0.201").count() == 0
    finally:
        db.close()


def test_b01_demo_login_can_still_analyze(client, simulated_enforcement, offline_chain):
    """The Simulate button posts to /analyze with the operator session. The
    default operator role is 'admin'; it must keep working."""
    headers = _login(client, settings.operator_username, settings.operator_password)
    resp = client.post("/api/v1/analyze", json={"flows": [_flow("10.0.0.202")]}, headers=headers)
    assert resp.status_code == 200, resp.text


# ─── B02: an already-blocked host is not re-processed ─────────────────────────

class _Clock(datetime):
    minute_offset = 0

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 4, 12, 0 + cls.minute_offset, 0, tzinfo=tz or timezone.utc)


def test_b02_same_flow_in_two_minutes_creates_one_incident(simulated_enforcement, offline_chain):
    from app.services import threat_analyzer
    from app.services.threat_analyzer import ThreatAnalyzer

    ip = "10.0.0.203"
    prediction = {"source_scores": {ip: 0.93}, "mode": "model"}
    with patch.object(threat_analyzer, "datetime", _Clock):
        _Clock.minute_offset = 0
        ThreatAnalyzer().evaluate(prediction, [_flow(ip)])
        _Clock.minute_offset = 1
        alerts, healing = ThreatAnalyzer().evaluate(prediction, [_flow(ip)])

    db = SessionLocal()
    try:
        assert db.query(Incident).filter(Incident.source_ip == ip).count() == 1
    finally:
        db.close()
    assert alerts == [] and healing == []
    assert offline_chain.store_incident.call_count == 1


# ─── B04: one out-of-range source does not abort the batch ────────────────────

def test_b04_out_of_range_source_is_skipped_not_fatal(simulated_enforcement, offline_chain):
    from app.services.threat_analyzer import ThreatAnalyzer

    prediction = {
        "source_scores": {"10.0.0.204": 0.91, "192.168.77.5": 0.99, "10.0.0.205": 0.92},
        "mode": "model",
    }
    flows = [_flow("10.0.0.204"), _flow("192.168.77.5"), _flow("10.0.0.205")]
    alerts, healing = ThreatAnalyzer().evaluate(prediction, flows)

    assert sorted(event["ip"] for event in healing) == ["10.0.0.204", "10.0.0.205"]
    db = SessionLocal()
    try:
        assert db.query(Incident).filter(Incident.source_ip == "192.168.77.5").count() == 0
    finally:
        db.close()


# ─── B03 + B12: detection provenance survives one transient inference error ───

def test_b03_b12_mode_recovers_and_each_block_is_labelled_by_what_scored_it(
    simulated_enforcement, offline_chain, monkeypatch
):
    from app.models.schemas import FlowRecord
    from app.services.inference_service import InferenceService
    from app.services.threat_analyzer import ThreatAnalyzer

    inference = InferenceService.get_instance()
    if inference.model is None or inference.torch is None:
        pytest.skip("GraphSAGE weights or torch unavailable; the model path cannot be exercised")
    torch = inference.torch

    # 1. One inference exception: this batch is scored by the heuristic.
    def boom(x, edge_index):
        raise RuntimeError("transient inference failure")

    monkeypatch.setattr(inference.model, "predict_proba", boom, raising=False)
    heuristic_ip = "10.0.0.206"
    loud = [FlowRecord(**_flow(heuristic_ip, packets=20_000, byte_count=50_000_000))]
    degraded = inference.predict(loud)
    assert degraded["mode"] == "degraded"
    ThreatAnalyzer().evaluate(degraded, loud)

    # 2. The model works again. Only its output is stubbed; the prediction dict
    #    is whatever InferenceService.predict builds.
    monkeypatch.setattr(
        inference.model, "predict_proba", lambda x, edge_index: torch.full((x.shape[0],), 0.97), raising=False
    )
    model_ip = "10.0.0.207"
    quiet = [FlowRecord(**_flow(model_ip))]
    recovered = inference.predict(quiet)
    assert recovered["mode"] == "model", "B12: one exception left the mode stuck on degraded"
    assert inference.health()["degraded_reason"] is None
    ThreatAnalyzer().evaluate(recovered, quiet)

    db = SessionLocal()
    try:
        reasons = {
            row.ip_address: row.reason
            for row in db.query(BlockedIP).filter(BlockedIP.ip_address.in_([heuristic_ip, model_ip]))
        }
    finally:
        db.close()
    assert reasons == {heuristic_ip: "HEURISTIC_DEGRADED", model_ip: "GNN_DETECTED"}


# ─── B06: unblock rows must not starve the pending-transaction reconciler ─────

def test_b06_pending_tx_is_reconciled_behind_many_unblock_rows():
    from web3.exceptions import TransactionNotFound

    from app.services.reconciliation import reconcile_blockchain_outbox

    db = SessionLocal()
    try:
        # What blocked.py writes for a confirmed manual unblock: a tx, no
        # on-chain incident id (releaseNode creates none), attack_type "Manual".
        for n in range(12):
            db.add(Incident(
                source_ip=f"10.0.0.{120 + n}", attack_type="Manual", threat_score=0.0, severity=1,
                is_blocked=False, blockchain_tx=f"0x{n:064x}", blockchain_incident_id=None,
                blockchain_status="confirmed", data_source="manual",
            ))
        db.commit()
        pending = Incident(
            source_ip="10.0.0.208", attack_type="DDoS", threat_score=0.9, severity=9, is_blocked=True,
            blockchain_tx="0x" + "ab" * 32, blockchain_incident_id=None, blockchain_status="pending",
            data_source="manual",
        )
        db.add(pending)
        db.commit()
        pending_id = pending.id
    finally:
        db.close()

    adapter = MagicMock()
    adapter._connected = True

    def receipt_for(tx_hash):
        if tx_hash == "0x" + "ab" * 32:
            return {"status": 1, "blockNumber": 7}
        raise TransactionNotFound(tx_hash)

    adapter.client.w3.eth.get_transaction_receipt.side_effect = receipt_for
    adapter.client.contract.events.IncidentLogged.return_value.process_receipt.return_value = [{"args": {"id": 41}}]

    with patch("app.services.reconciliation.BlockchainAdapter.get_instance", return_value=adapter):
        reconcile_blockchain_outbox(max_batch=10)

    db = SessionLocal()
    try:
        row = db.get(Incident, pending_id)
        assert (row.blockchain_status, row.blockchain_incident_id) == ("confirmed", 41)
    finally:
        db.close()


# ─── B07: the monitor thread's pushes reach a real socket client ──────────────

def test_b07_monitor_thread_emit_reaches_a_live_socket_client():
    """A real uvicorn server, a real Socket.IO client, and the emit made from a
    thread that is not the server's -- which is what MininetMonitor._run is.
    The other tests mock `sio`, which is how this defect survived."""
    import socket as pysocket

    import socketio
    import uvicorn

    from app.main import sio, socket_app
    from app.mininet_monitor.monitor import MininetMonitor

    with pysocket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(socket_app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"))
    loop = asyncio.new_event_loop()
    server_thread = threading.Thread(target=lambda: loop.run_until_complete(server.serve()), daemon=True)
    server_thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"

    received: dict[str, object] = {}
    got_all = threading.Event()
    client = socketio.Client(reconnection=False)

    def _record(name):
        def handler(data):
            received[name] = data
            if {"graph_update", "alert", "healing_triggered"} <= received.keys():
                got_all.set()
        return handler

    for event in ("graph_update", "alert", "healing_triggered"):
        client.on(event, _record(event))

    try:
        client.connect(
            f"http://127.0.0.1:{port}",
            headers={"X-API-Key": settings.admin_api_token or settings.backend_api_token},
            wait_timeout=10,
        )
        monitor = MininetMonitor(sio=sio, loop=loop)
        result = {
            "graph_snapshot": {"nodes": [], "links": [], "metadata": {}},
            "alerts": [{"id": "alert-b07", "source_ip": "10.0.0.209"}],
            "healing_events": [{"ip": "10.0.0.209"}],
        }
        started = time.monotonic()
        monitor._emit(result)  # this thread is not the server's loop thread
        delivered = got_all.wait(timeout=3.0)
        elapsed = time.monotonic() - started
        assert delivered, f"only {sorted(received)} arrived within {elapsed:.1f}s"
        assert received["alert"]["id"] == "alert-b07"
    finally:
        if client.connected:
            client.disconnect()
        server.should_exit = True
        server_thread.join(timeout=10)
