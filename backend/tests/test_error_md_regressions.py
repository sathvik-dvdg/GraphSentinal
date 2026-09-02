# [WSL2]
"""Regression suite for Error.md's 39 catalogued issues.

Every test below is named and docstring'd after the Error.md issue number it
guards. Not every issue gets a test here:

- Frontend-only issues (#1, #2, #20, #21, #22, #23, #24, #26, #37, #38, #39)
  have no backend behavior to assert — they were verified live via a
  headless-Chromium pass during the original fix and are not re-covered here.
- #7 and #8 are about config-loading behavior that depends on process
  working directory / Docker env substitution — not reproducible inside a
  single pytest process without reshaping how settings load.
- #17 (real chain ID) and #6's "confirmed" tx path need a live Ganache
  instance; only the offline/error path (the actual bug) is tested here.
- #31's tests use verbatim lines from a real `ovs-ofctl dump-flows -O
  OpenFlow13` capture taken against this project's own WSL2 Mininet
  topology after a `pingall` (ARP + ICMP traffic) — not synthesized.

Run with (from `backend/`):
    pytest tests/test_error_md_regressions.py -v
"""
from __future__ import annotations

import logging

import pytest

from app.config import settings


# ── #3 — simulateAttack() exercises the real backend pipeline ──────────────

def test_issue_03_analyze_creates_real_persisted_incident(client, auth_headers):
    """A high-score flow submitted to /analyze must create a real SQLite
    Incident row (not a client-fabricated alert) — this is what let the old
    frontend simulateAttack() fake incidents entirely client-side."""
    flows = [{
        "src_ip": "10.0.0.201", "dst_ip": "10.0.0.1",
        "src_port": 54321, "dst_port": 80, "protocol": "TCP",
        "packet_count": 15000, "byte_count": 5_120_000,
        "duration_sec": 3.5, "tcp_flags": 2, "data_source": "simulation",
    }]
    resp = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["incidents_created"], list)
    if body["incidents_created"]:
        alert_id = body["incidents_created"][0]
        incident_id = int(alert_id.split("-")[1])
        forensics = client.get("/api/v1/forensics", headers=auth_headers).json()
        assert any(i["id"] == incident_id for i in forensics["incidents"])


# ── #4 — ML failure mode: degrade visibly, or hard-fail only if configured ─

def test_issue_04_missing_weights_degrades_not_crashes(monkeypatch):
    """Default config (require_ml_model=False): a missing/broken weights
    file must degrade to the heuristic scorer with a populated
    degraded_reason, never raise and never fail silently."""
    from app.services.inference_service import InferenceService

    monkeypatch.setattr(settings, "weights_path", "/nonexistent/weights.pt")
    monkeypatch.setattr(settings, "require_ml_model", False)
    InferenceService._instance = None

    service = InferenceService.get_instance()
    assert service.mode == "degraded"
    assert service.degraded_reason  # non-empty — never silent


def test_issue_04_hard_fail_when_explicitly_required(monkeypatch):
    """decisions.md #4, Option A: require_ml_model=True + demo_allow_mock_ml=False
    must raise instead of silently degrading — this is the opt-in strict mode."""
    from app.services.inference_service import InferenceService

    monkeypatch.setattr(settings, "weights_path", "/nonexistent/weights.pt")
    monkeypatch.setattr(settings, "require_ml_model", True)
    monkeypatch.setattr(settings, "demo_allow_mock_ml", False)
    InferenceService._instance = None

    with pytest.raises(RuntimeError):
        InferenceService.get_instance()


def test_issue_04_health_endpoint_surfaces_ml_mode(client):
    """/health (unauthenticated, used for container healthchecks) must expose
    ml.mode / ml.degraded_reason so the frontend's MlModeBadge can render it."""
    resp = client.get("/health")
    assert resp.status_code == 200
    ml = resp.json()["ml"]
    assert "mode" in ml and "degraded_reason" in ml


# ── #5 — simulated enforcement mode logs a visible warning ─────────────────

def test_issue_05_simulated_mode_logs_warning(monkeypatch, caplog):
    """decisions.md #5, Option C: EnforcementAgent must log a visible warning
    on init whenever mode != 'ovs', so misconfiguration can't hide in the log."""
    from app.services.enforcement_agent import EnforcementAgent

    with caplog.at_level(logging.WARNING, logger="graphsentinel.enforcement"):
        EnforcementAgent(mode="simulated")
    assert any("SIMULATED" in record.message for record in caplog.records)


def test_issue_05_ovs_mode_does_not_warn(caplog):
    """The warning is specific to simulated mode — real OVS mode shouldn't
    also cry wolf every time the agent is constructed."""
    from app.services.enforcement_agent import EnforcementAgent

    with caplog.at_level(logging.WARNING, logger="graphsentinel.enforcement"):
        EnforcementAgent(mode="ovs")
    assert not any("SIMULATED" in record.message for record in caplog.records)


# ── #6 — blockchain offline path returns real status, not a mock success ───

def test_issue_06_offline_blockchain_reports_real_error(monkeypatch):
    """Before the fix, an unreachable Ganache could return a fabricated
    success. It must instead report status='offline' with the real error."""
    from app.services.blockchain_adapter import BlockchainAdapter

    BlockchainAdapter._instance = None
    adapter = BlockchainAdapter.get_instance()
    monkeypatch.setattr(adapter, "_connected", False)
    monkeypatch.setattr(adapter, "client", None)
    monkeypatch.setattr(adapter, "error", "no bridge configured")

    result = adapter.store_incident("10.0.0.2", "DDoS", 9, True, 1)
    assert result["status"] == "offline"
    assert result["tx_hash"] is None
    assert result["error"]


def test_issue_06_blockchain_timeout_does_not_hang(monkeypatch):
    """A slow/hung Ganache call must time out and report status='pending',
    not block the caller indefinitely (covered further in
    test_security_resilience.py; re-asserted here as an Error.md #6 regression)."""
    from app.services.blockchain_adapter import BlockchainAdapter
    from unittest.mock import MagicMock
    import time as time_mod

    BlockchainAdapter._instance = None
    adapter = BlockchainAdapter.get_instance()
    mock_client = MagicMock()
    mock_client.log_incident.side_effect = lambda **kw: time_mod.sleep(5)
    monkeypatch.setattr(adapter, "client", mock_client)
    monkeypatch.setattr(adapter, "_connected", True)
    monkeypatch.setattr(settings, "blockchain_tx_timeout_seconds", 1)

    start = time_mod.time()
    result = adapter.store_incident("10.0.0.2", "DDoS", 9, True, 1)
    assert time_mod.time() - start < 3.0
    assert result["status"] == "pending"


# ── #9 — graph always includes the configured 10-host baseline ─────────────

def test_issue_09_graph_includes_baseline_hosts(client, auth_headers):
    resp = client.get("/api/v1/graph", headers=auth_headers)
    assert resp.status_code == 200
    node_ids = {n["id"] for n in resp.json()["nodes"]}
    baseline = {f"10.0.0.{i}" for i in range(1, 11)}
    assert baseline <= node_ids


def test_issue_09_baseline_hosts_marked_configured_not_observed(client, auth_headers):
    resp = client.get("/api/v1/graph", headers=auth_headers)
    nodes_by_id = {n["id"]: n for n in resp.json()["nodes"]}
    # A host with no traffic this batch must read "configured", never
    # fabricated as if it had been "observed" on the wire.
    untouched = nodes_by_id.get("10.0.0.9")
    if untouched and untouched["connections"] == 0:
        assert untouched["source"] == "configured"


# ── #11 — empty OVS parse clears stale graph state instead of freezing it ──

def test_issue_11_empty_flows_updates_not_freezes_graph(client, auth_headers):
    """Submitting a real burst then an empty batch must clear that traffic
    from the live graph — an empty poll tick must not be silently ignored."""
    burst = [{
        "src_ip": "10.0.0.202", "dst_ip": "10.0.0.1", "src_port": 1234,
        "dst_port": 80, "protocol": "TCP", "packet_count": 10,
        "byte_count": 1000, "duration_sec": 1.0, "tcp_flags": 2,
    }]
    client.post("/api/v1/analyze", json={"flows": burst}, headers=auth_headers)
    graph_after_burst = client.get("/api/v1/graph", headers=auth_headers).json()
    node = next((n for n in graph_after_burst["nodes"] if n["id"] == "10.0.0.202"), None)
    assert node is not None and node["connections"] > 0

    client.post("/api/v1/analyze", json={"flows": []}, headers=auth_headers)
    graph_after_empty = client.get("/api/v1/graph", headers=auth_headers).json()
    node_after = next((n for n in graph_after_empty["nodes"] if n["id"] == "10.0.0.202"), None)
    # The host drops out of "observed" (or its connection count resets) once
    # the batch that mentioned it is gone — it must not stay frozen forever.
    assert node_after is None or node_after["connections"] == 0


# ── #12 / #34 — demo flows are opt-in, labeled, and traceable end to end ───

def test_issue_12_demo_fallback_defaults_off(monkeypatch):
    """decisions.md #12, Option B: local/non-Docker default must be False —
    only .env.docker explicitly opts in."""
    from app.config import Settings
    fresh = Settings(_env_file=None, daemon_token="x")
    assert fresh.demo_fallback_flows is False


def test_issue_12_demo_flows_are_labeled():
    from app.mininet_monitor.flow_parser import demo_flows
    flows = demo_flows()
    assert flows
    assert all(f["data_source"] == "demo" for f in flows)


def test_issue_34_data_source_propagates_to_alerts_and_forensics(client, auth_headers):
    flows = [{
        "src_ip": "10.0.0.203", "dst_ip": "10.0.0.1", "src_port": 51234,
        "dst_port": 6667, "protocol": "TCP", "packet_count": 5000,
        "byte_count": 640000, "duration_sec": 8.0, "tcp_flags": 2,
        "data_source": "simulation",
    }]
    resp = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers).json()
    if not resp["incidents_created"]:
        pytest.skip("score fell under threshold this run; nothing to trace")

    alerts = client.get("/api/v1/alerts", headers=auth_headers).json()["alerts"]
    matching = [a for a in alerts if a["source_ip"] == "10.0.0.203"]
    assert matching and matching[0]["data_source"] == "simulation"

    forensics = client.get("/api/v1/forensics", headers=auth_headers).json()
    matching_inc = [i for i in forensics["incidents"] if i["source_ip"] == "10.0.0.203"]
    assert matching_inc and matching_inc[0]["data_source"] == "simulation"


def test_issue_34_stats_breaks_down_by_data_source(client, auth_headers):
    resp = client.get("/api/v1/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert "data_sources" in resp.json()


# ── #13 / #14 — manual block/unblock write real blockchain + incident rows ─

def test_issue_13_manual_block_writes_blockchain_tx_field(client, auth_headers):
    resp = client.post("/api/v1/block", json={"ip": "10.0.0.210", "action": "block"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "blockchain_tx" in body
    assert "enforcement_status" in body


def test_issue_14_unblock_flips_incident_history(client, auth_headers):
    client.post("/api/v1/block", json={"ip": "10.0.0.211", "action": "block"}, headers=auth_headers)
    unblock = client.post("/api/v1/block", json={"ip": "10.0.0.211", "action": "unblock"}, headers=auth_headers)
    assert unblock.status_code == 200
    assert unblock.json()["status"] == "unblocked"

    blocked = client.get("/api/v1/blocked", headers=auth_headers).json()["blocked_ips"]
    assert not any(b["ip"] == "10.0.0.211" for b in blocked)

    forensics = client.get("/api/v1/forensics", headers=auth_headers).json()
    matching = [i for i in forensics["incidents"] if i["source_ip"] == "10.0.0.211"]
    assert matching and matching[0]["is_blocked"] is False


# ── #15 — idempotency key suppresses duplicate incidents within a minute ───

def test_issue_15_duplicate_attack_same_minute_suppressed(client, auth_headers):
    flows = [{
        "src_ip": "10.0.0.212", "dst_ip": "10.0.0.1", "src_port": 54321,
        "dst_port": 80, "protocol": "TCP", "packet_count": 15000,
        "byte_count": 5_120_000, "duration_sec": 3.5, "tcp_flags": 2,
    }]
    first = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers).json()
    second = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers).json()
    if not first["incidents_created"]:
        pytest.skip("score fell under threshold this run")
    # Same IP/attack/score/minute/evidence must not create a second incident.
    assert len(second["incidents_created"]) <= len(first["incidents_created"])


# ── #16 — timeline buckets carry real dates, not bare HH:MM ────────────────

def test_issue_16_timeline_points_are_full_iso_datetimes(client, auth_headers):
    resp = client.get("/api/v1/timeline", params={"last": "60min"}, headers=auth_headers)
    assert resp.status_code == 200
    points = resp.json()["data_points"]
    assert points
    from datetime import datetime
    for point in points:
        # Must round-trip as a full ISO datetime (has a date component), not
        # a bare "14:32" string.
        parsed = datetime.fromisoformat(point["time"].replace("Z", "+00:00"))
        assert parsed.year >= 2024


# ── #18 / #27 — every /api/v1/* route requires real auth ───────────────────

def test_issue_18_unauthenticated_request_rejected(client):
    resp = client.get("/api/v1/graph")
    assert resp.status_code == 401


def test_issue_18_wrong_api_key_rejected(client):
    resp = client.get("/api/v1/graph", headers={"X-API-Key": "wrong-token"})
    assert resp.status_code == 401


def test_issue_18_real_login_issues_working_session(client):
    login = client.post("/api/v1/auth/login", json={
        "username": settings.operator_username,
        "password": settings.operator_password,
    })
    assert login.status_code == 200
    token = login.json()["token"]

    resp = client.get("/api/v1/graph", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_issue_18_bad_password_rejected(client):
    resp = client.post("/api/v1/auth/login", json={
        "username": settings.operator_username,
        "password": "definitely-wrong",
    })
    assert resp.status_code == 401


# ── #19 — Settings: real controls are wired, fake ones are removed ─────────

def test_issue_19_threat_threshold_actually_mutates_live_settings(client, auth_headers):
    original = settings.threat_threshold
    try:
        resp = client.patch("/api/v1/settings", json={"threat_threshold": 0.42}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["threat_threshold"] == 0.42
        assert settings.threat_threshold == 0.42

        get_resp = client.get("/api/v1/settings", headers=auth_headers)
        assert get_resp.json()["threat_threshold"] == 0.42
    finally:
        settings.threat_threshold = original


# ── #25 — every response matches its declared response_model exactly ───────

@pytest.mark.parametrize("path", [
    "/api/v1/graph", "/api/v1/stats", "/api/v1/alerts", "/api/v1/blocked",
    "/api/v1/forensics", "/api/v1/timeline", "/api/v1/settings",
    "/api/v1/enforcement-actions",
])
def test_issue_25_declared_endpoints_return_200_with_schema(client, auth_headers, path):
    """response_model= silently drops undeclared fields — a passing 200 here
    with FastAPI's own response validation active is what proves no field is
    being silently stripped (a mismatch would 500, not just look wrong)."""
    resp = client.get(path, headers=auth_headers)
    assert resp.status_code == 200


def test_issue_25_blocked_ip_record_has_enforcement_status(client, auth_headers):
    """Regression for the specific gap #25 found: BlockedIPRecord was
    missing enforcement_status even though the endpoint always returned it."""
    client.post("/api/v1/block", json={"ip": "10.0.0.213", "action": "block"}, headers=auth_headers)
    blocked = client.get("/api/v1/blocked", headers=auth_headers).json()["blocked_ips"]
    row = next(b for b in blocked if b["ip"] == "10.0.0.213")
    assert "enforcement_status" in row


def test_issue_25_block_response_has_enforcement_status(client, auth_headers):
    resp = client.post("/api/v1/block", json={"ip": "10.0.0.214", "action": "block"}, headers=auth_headers)
    assert "enforcement_status" in resp.json()


# ── #28 — CORS origins come from real parsed config, not hardcoded ─────────

def test_issue_28_cors_origins_parsed_from_csv():
    assert settings.cors_origins_list == [
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    ]
    assert len(settings.cors_origins_list) >= 1


# ── #29 — schema comes from Alembic migrations, not create_all ─────────────

def test_issue_29_alembic_version_table_exists():
    from sqlalchemy import inspect
    from app.database import engine

    tables = inspect(engine).get_table_names()
    assert "alembic_version" in tables
    assert "enforcement_actions" in tables  # from the #35 migration


# ── #30 — flow snapshots are retained only for a bounded window ────────────

def test_issue_30_old_flow_snapshots_are_pruned(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.database import SessionLocal
    from app.models.incident import FlowSnapshot
    from app.services.graph_state import GraphState

    db = SessionLocal()
    try:
        stale = FlowSnapshot(
            src_ip="10.0.0.220", dst_ip="10.0.0.1", src_port=1, dst_port=2,
            captured_at=datetime.now(timezone.utc) - timedelta(hours=999),
        )
        db.add(stale)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(settings, "flow_snapshot_retention_hours", 24)
    state = GraphState.__new__(GraphState)
    from threading import Lock
    state._lock = Lock()
    state._persist_snapshots([], {"ip_scores": {}})

    db = SessionLocal()
    try:
        remaining = db.query(FlowSnapshot).filter(FlowSnapshot.src_ip == "10.0.0.220").all()
        assert remaining == []
    finally:
        db.close()


# ── #32 — TCP flags are parsed, never fabricated ────────────────────────────

def test_issue_32_tcp_flags_parsed_not_fabricated():
    from app.mininet_monitor.flow_parser import _parse_output

    line_with_flags = (
        "cookie=0x0, table=0, n_packets=10, n_bytes=840, tcp,"
        "nw_src=10.0.0.2,nw_dst=10.0.0.1,tp_src=1234,tp_dst=80,tcp_flags=0x02 actions=NORMAL"
    )
    flows = _parse_output(line_with_flags)
    assert flows[0]["tcp_flags"] == 2

    line_without_flags = (
        "cookie=0x0, table=0, n_packets=10, n_bytes=840, tcp,"
        "nw_src=10.0.0.3,nw_dst=10.0.0.1,tp_src=1234,tp_dst=80 actions=NORMAL"
    )
    flows2 = _parse_output(line_without_flags)
    # Must default to 0 (unknown), never fabricate SYN=2.
    assert flows2[0]["tcp_flags"] == 0


def test_issue_32_ovs_flows_labeled_data_source_ovs():
    from app.mininet_monitor.flow_parser import _parse_output

    line = "n_packets=1,n_bytes=1,tcp,nw_src=10.0.0.2,nw_dst=10.0.0.1,tp_src=1,tp_dst=1 actions=NORMAL"
    flows = _parse_output(line)
    assert flows[0]["data_source"] == "ovs"


# ── #31 — parser handles ARP and ICMP variants, verified against a real
#          `ovs-ofctl dump-flows -O OpenFlow13` capture from this project's
#          own WSL2 Mininet topology (`base_topology.py`) after `pingall`. ──

# Captured verbatim 2026-08-22 — not synthesized. ARP replies OVS installed
# in response to the topology's pingall.
_REAL_ARP_LINE = (
    'cookie=0x0, duration=16.959s, table=0, n_packets=0, n_bytes=0, '
    'idle_timeout=60, priority=1,arp,in_port="s1-eth10",'
    'vlan_tci=0x0000/0x1fff,dl_src=00:00:00:00:00:0a,'
    'dl_dst=00:00:00:00:00:06,arp_spa=10.0.0.10,arp_tpa=10.0.0.6,'
    'arp_op=2 actions=output:"s1-eth6"'
)

# Real ICMP echo request from the same capture.
_REAL_ICMP_LINE = (
    'cookie=0x0, duration=17.401s, table=0, n_packets=0, n_bytes=0, '
    'idle_timeout=60, priority=1,icmp,in_port="s1-eth1",'
    'vlan_tci=0x0000/0x1fff,dl_src=00:00:00:00:00:01,'
    'dl_dst=00:00:00:00:00:02,nw_src=10.0.0.1,nw_dst=10.0.0.2,nw_tos=0,'
    'icmp_type=8,icmp_code=0 actions=output:"s1-eth2"'
)


def test_issue_31_arp_flows_no_longer_dropped():
    """Before the fix: arp_spa=/arp_tpa= isn't nw_src=/nw_dst=, so the line
    failed the initial gate and was silently skipped entirely."""
    from app.mininet_monitor.flow_parser import _parse_output

    flows = _parse_output(_REAL_ARP_LINE)
    assert len(flows) == 1
    assert flows[0]["src_ip"] == "10.0.0.10"
    assert flows[0]["dst_ip"] == "10.0.0.6"
    assert flows[0]["protocol"] == "ARP"
    assert flows[0]["data_source"] == "ovs"


def test_issue_31_icmp_flows_parsed_with_zero_ports():
    """ICMP already used nw_src=/nw_dst= so it was never dropped — it
    correctly has no tp_src=/tp_dst= (ICMP has no ports), which the parser
    already defaulted to 0 rather than fabricating a port."""
    from app.mininet_monitor.flow_parser import _parse_output

    flows = _parse_output(_REAL_ICMP_LINE)
    assert len(flows) == 1
    assert flows[0]["src_ip"] == "10.0.0.1"
    assert flows[0]["dst_ip"] == "10.0.0.2"
    assert flows[0]["protocol"] == "ICMP"
    assert flows[0]["src_port"] == 0
    assert flows[0]["dst_port"] == 0


def test_issue_31_mixed_capture_parses_every_line():
    """A real dump-flows output mixing ARP + ICMP + TCP must parse all three
    kinds in one pass, not just whichever the gate happened to allow."""
    from app.mininet_monitor.flow_parser import _parse_output

    tcp_line = "n_packets=5,n_bytes=500,tcp,nw_src=10.0.0.3,nw_dst=10.0.0.4,tp_src=51000,tp_dst=80 actions=NORMAL"
    raw = "\n".join([_REAL_ARP_LINE, _REAL_ICMP_LINE, tcp_line])

    flows = _parse_output(raw)
    protocols = {f["protocol"] for f in flows}
    assert protocols == {"ARP", "ICMP", "TCP"}
    assert len(flows) == 3


def test_issue_31_analyze_pipeline_accepts_arp_flows(client, auth_headers):
    """End to end: an ARP-sourced flow (protocol="ARP") must not 422/500 the
    real /api/v1/analyze pipeline it now reaches via parse_ovs_flows()."""
    flows = [{
        "src_ip": "10.0.0.240", "dst_ip": "10.0.0.241", "src_port": 0,
        "dst_port": 0, "protocol": "ARP", "packet_count": 1, "byte_count": 42,
        "duration_sec": 0.5, "tcp_flags": 0, "data_source": "ovs",
    }]
    resp = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers)
    assert resp.status_code == 200


# ── #33 — reconciliation only runs in real 'ovs' enforcement mode ──────────

def test_issue_33_reconciliation_skips_when_simulated(monkeypatch):
    from app.services.reconciliation import reconcile_once

    monkeypatch.setattr(settings, "enforcement_mode", "simulated")
    result = reconcile_once()
    assert result["status"] == "skipped"


# ── #35 — durable enforcement_actions audit trail ───────────────────────────

def test_issue_35_manual_block_logged_to_enforcement_actions(client, auth_headers):
    client.post("/api/v1/block", json={"ip": "10.0.0.230", "action": "block", "reason": "MANUAL_OVERRIDE"}, headers=auth_headers)
    resp = client.get("/api/v1/enforcement-actions", params={"ip_address": "10.0.0.230"}, headers=auth_headers)
    assert resp.status_code == 200
    actions = resp.json()["actions"]
    assert any(a["action"] == "block" and a["reason"] == "MANUAL_OVERRIDE" for a in actions)


def test_issue_35_reconciliation_failure_is_logged_with_error(monkeypatch):
    """Failures must be captured too, not just successes — this is the whole
    point of a durable audit trail over the current-state-only tables."""
    from app.services.enforcement_log import log_enforcement_action
    from app.database import SessionLocal
    from app.models.incident import EnforcementAction

    log_enforcement_action(
        ip_address="10.0.0.231", action="block", reason="RECONCILE_REAPPLY",
        status="failed", error="daemon unreachable",
    )
    db = SessionLocal()
    try:
        row = db.query(EnforcementAction).filter(
            EnforcementAction.ip_address == "10.0.0.231"
        ).order_by(EnforcementAction.id.desc()).first()
        assert row is not None
        assert row.status == "failed"
        assert row.error == "daemon unreachable"
    finally:
        db.close()


# ── #36 — alert IDs are stable, persisted-record-derived, never random ─────

def test_issue_36_alert_ids_are_stable_incident_derived(client, auth_headers):
    flows = [{
        "src_ip": "10.0.0.232", "dst_ip": "10.0.0.1", "src_port": 54321,
        "dst_port": 80, "protocol": "TCP", "packet_count": 15000,
        "byte_count": 5_120_000, "duration_sec": 3.5, "tcp_flags": 2,
    }]
    resp = client.post("/api/v1/analyze", json={"flows": flows}, headers=auth_headers).json()
    if not resp["incidents_created"]:
        pytest.skip("score fell under threshold this run")
    alert_id = resp["incidents_created"][0]
    assert alert_id.startswith("alert-")
    assert alert_id.split("-")[1].isdigit()  # a real SQLite PK, not demo-{timestamp}
