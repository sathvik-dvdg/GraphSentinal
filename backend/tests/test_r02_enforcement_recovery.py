# [WSL2]
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, EnforcementAction, Incident
from app.services.enforcement_agent import EnforcementAgent, EnforcementError
from app.services.reconciliation import _parse_blocked_from_ovs, reconcile_once
from app.services.self_healing import SelfHealingEngine
from app.services.threat_analyzer import ThreatAnalyzer


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    try:
        db.query(EnforcementAction).delete()
        db.query(BlockedIP).delete()
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(EnforcementAction).delete()
        db.query(BlockedIP).delete()
        db.query(Incident).delete()
        db.commit()
    finally:
        db.close()


def test_crash_before_enforcement_not_requested_retries_and_enforces():
    """Test A (M12-F01 / M17-F01): An incident stranded in 'not_requested' state
    due to a crash before block_ip() must be eligible for enforcement retry on the
    next analytical evaluation of the same event/idempotency key."""
    from app.services.threat_analyzer import infer_attack_type

    analyzer = ThreatAnalyzer()
    analyzer.threshold = 0.50

    flows = [{
        "src_ip": "10.0.0.4",
        "dst_ip": "10.0.0.1",
        "dst_port": 80,
        "packet_count": 1000,
        "byte_count": 50000,
        "protocol": "TCP",
        "tcp_flags": 2,
    }]
    attack_type = infer_attack_type("10.0.0.4", 0.95, flows)
    key = analyzer._idempotency_key("10.0.0.4", attack_type, 0.95, flows)

    # 1. Simulate process crash immediately after _create_incident:
    # Incident exists with enforcement_status='not_requested'
    db = SessionLocal()
    crashed_incident = Incident(
        source_ip="10.0.0.4",
        attack_type=attack_type,
        threat_score=0.95,
        severity=4,
        is_blocked=False,
        raw_flow_json=json.dumps(flows),
        idempotency_key=key,
        enforcement_status="not_requested",
    )
    db.add(crashed_incident)
    db.commit()
    crashed_id = crashed_incident.id
    db.close()

    # 2. Second analytical pass arrives with identical flow batch (same idempotency key)
    prediction = {
        "source_scores": {"10.0.0.4": 0.95},
        "flow_scores": [{"flow_index": 0, "src_ip": "10.0.0.4", "dst_ip": "10.0.0.1", "score": 0.95}],
    }

    mock_healer = MagicMock(spec=SelfHealingEngine)
    mock_healer.block_ip.return_value = {
        "id": "heal-recovered",
        "timestamp": "2026-08-30T12:00:00Z",
        "ip": "10.0.0.4",
        "action": "ISOLATED",
        "attack_type": attack_type,
        "trigger_score": 0.95,
        "edges_severed": 1,
        "duration_ms": 100,
        "network_stability_before": 88,
        "network_stability_after": 94,
        "enforcement_status": "enforced",
    }
    analyzer.healer = mock_healer

    alerts, healing = analyzer.evaluate(prediction, flows)

    # 3. Assertions:
    # - Enforcement was retried
    assert mock_healer.block_ip.call_count == 1
    assert len(healing) == 1
    assert healing[0]["enforcement_status"] == "enforced"

    # - Existing incident record was updated, NOT duplicated
    db = SessionLocal()
    all_incidents = db.query(Incident).filter(Incident.source_ip == "10.0.0.4").all()
    assert len(all_incidents) == 1
    assert all_incidents[0].id == crashed_id
    assert all_incidents[0].is_blocked is True
    assert all_incidents[0].enforcement_status == "enforced"
    db.close()


def test_pending_enforcement_idempotent_duplicate_retries():
    """Test B (M17-F02): An incident in 'pending_enforcement' state must retry
    enforcement on duplicate analytical event."""
    from app.services.threat_analyzer import infer_attack_type

    analyzer = ThreatAnalyzer()
    analyzer.threshold = 0.50

    flows = [{
        "src_ip": "10.0.0.5",
        "dst_ip": "10.0.0.1",
        "dst_port": 80,
        "packet_count": 2000,
        "byte_count": 80000,
        "protocol": "TCP",
        "tcp_flags": 2,
    }]
    attack_type = infer_attack_type("10.0.0.5", 0.90, flows)
    key = analyzer._idempotency_key("10.0.0.5", attack_type, 0.90, flows)

    # Seed incident with pending_enforcement
    db = SessionLocal()
    pending_incident = Incident(
        source_ip="10.0.0.5",
        attack_type=attack_type,
        threat_score=0.90,
        severity=4,
        is_blocked=True,
        raw_flow_json=json.dumps(flows),
        idempotency_key=key,
        enforcement_status="pending_enforcement",
    )
    db.add(pending_incident)
    db.commit()
    db.close()

    prediction = {
        "source_scores": {"10.0.0.5": 0.90},
        "flow_scores": [{"flow_index": 0, "src_ip": "10.0.0.5", "dst_ip": "10.0.0.1", "score": 0.90}],
    }

    mock_healer = MagicMock(spec=SelfHealingEngine)
    mock_healer.block_ip.return_value = {
        "id": "heal-retry-success",
        "ip": "10.0.0.5",
        "enforcement_status": "enforced",
    }
    analyzer.healer = mock_healer

    alerts, healing = analyzer.evaluate(prediction, flows)

    assert mock_healer.block_ip.call_count == 1
    assert len(healing) == 1
    assert healing[0]["enforcement_status"] == "enforced"

    db = SessionLocal()
    updated = db.query(Incident).filter(Incident.source_ip == "10.0.0.5").one()
    assert updated.enforcement_status == "enforced"
    db.close()


def test_already_enforced_or_simulated_skips_redundant_enforcement():
    """Test C: An incident in 'enforced', 'simulated', or 'already_blocked' state
    must NOT execute redundant enforcement agent calls on duplicate events."""
    from app.services.threat_analyzer import infer_attack_type

    analyzer = ThreatAnalyzer()
    analyzer.threshold = 0.50

    flows = [{
        "src_ip": "10.0.0.6",
        "dst_ip": "10.0.0.1",
        "dst_port": 80,
        "packet_count": 3000,
        "byte_count": 90000,
    }]
    attack_type = infer_attack_type("10.0.0.6", 0.92, flows)
    key = analyzer._idempotency_key("10.0.0.6", attack_type, 0.92, flows)

    for terminal_status in ["enforced", "simulated", "already_blocked"]:
        db = SessionLocal()
        db.query(Incident).delete()
        inc = Incident(
            source_ip="10.0.0.6",
            attack_type=attack_type,
            threat_score=0.92,
            severity=4,
            is_blocked=True,
            raw_flow_json=json.dumps(flows),
            idempotency_key=key,
            enforcement_status=terminal_status,
        )
        db.add(inc)
        db.commit()
        db.close()

        prediction = {
            "source_scores": {"10.0.0.6": 0.92},
            "flow_scores": [{"flow_index": 0, "src_ip": "10.0.0.6", "dst_ip": "10.0.0.1", "score": 0.92}],
        }

        mock_healer = MagicMock(spec=SelfHealingEngine)
        analyzer.healer = mock_healer

        alerts, healing = analyzer.evaluate(prediction, flows)

        # Must skip redundant enforcement call
        assert mock_healer.block_ip.call_count == 0
        assert len(healing) == 0


def test_enforcement_daemon_timeout_transitions_to_pending_enforcement():
    """Test D: When the enforcement daemon is unreachable or times out,
    SelfHealingEngine catches EnforcementError and transitions status to 'pending_enforcement'."""
    mock_agent = MagicMock(spec=EnforcementAgent)
    mock_agent.block_ip.side_effect = EnforcementError("Daemon connection timed out")

    healer = SelfHealingEngine(agent=mock_agent)
    result = healer.block_ip("10.0.0.7", reason="GNN_DETECTED", attack_type="SYNFlood", threat_score=0.88)

    assert result["enforcement_status"] == "pending_enforcement"

    db = SessionLocal()
    blocked_row = db.query(BlockedIP).filter(BlockedIP.ip_address == "10.0.0.7").one_or_none()
    assert blocked_row is not None
    assert blocked_row.enforcement_status == "pending_enforcement"
    db.close()


def test_enforcement_and_reconciliation_ovs_priority_alignment():
    """Test E (M10-F02): Verify that OVS drop rule parsing and enforcement daemon expectations
    are aligned on priority=1000."""
    sample_ovs_output = (
        "cookie=0x0, duration=10.5s, table=0, n_packets=50, n_bytes=3000, "
        "priority=1000,ip,nw_src=10.0.0.8 actions=drop\n"
        "cookie=0x0, duration=20.0s, table=0, n_packets=100, n_bytes=6000, "
        "priority=0 actions=NORMAL\n"
    )

    with patch("app.services.reconciliation._send_to_daemon") as mock_send:
        mock_send.return_value = {"status": "success", "output": sample_ovs_output}
        parsed = _parse_blocked_from_ovs("s1")

    assert "10.0.0.8" in parsed
    assert len(parsed) == 1
