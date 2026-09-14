# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.incident import AuditLog, FlowSnapshot, Incident
from app.services.retention import cleanup_expired_flow_snapshots
from app.services.threat_analyzer import ThreatAnalyzer


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"X-API-Key": settings.admin_api_token or settings.backend_api_token}


@pytest.fixture
def operator_headers():
    return {"X-API-Key": settings.backend_api_token}


# ─── 1. Request Correlation ID Tests (M14-F01) ────────────────────────────────

def test_request_correlation_id_auto_generated(client, operator_headers):
    """M14-F01: Requests without X-Request-ID receive an auto-generated X-Request-ID response header."""
    resp = client.get("/api/v1/stats", headers=operator_headers)
    assert resp.status_code == 200
    req_id = resp.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 16


def test_request_correlation_id_propagates_client_header(client, operator_headers):
    """M14-F01: Valid client-supplied X-Request-ID is preserved and reflected in response."""
    custom_id = "trace-client-abc-12345"
    headers = dict(operator_headers)
    headers["X-Request-ID"] = custom_id

    resp = client.get("/api/v1/stats", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id


def test_request_correlation_id_sanitizes_malformed_header(client, operator_headers):
    """M14-F01: Malformed/unsafe X-Request-ID is sanitized and replaced with a clean generated ID."""
    unsafe_id = "<script>alert('xss')</script>; DROP TABLE incidents; --"
    headers = dict(operator_headers)
    headers["X-Request-ID"] = unsafe_id

    resp = client.get("/api/v1/stats", headers=headers)
    assert resp.status_code == 200
    reflected_id = resp.headers.get("X-Request-ID")
    assert reflected_id != unsafe_id
    assert "<script>" not in reflected_id


# ─── 2. Administrative Auditability Tests (M14-F02) ───────────────────────────

def test_settings_mutation_creates_audit_log(client, admin_headers):
    """M14-F02: PATCH /settings creates an immutable AuditLog record attributing the change."""
    custom_id = "req-audit-settings-test-99"
    headers = dict(admin_headers)
    headers["X-Request-ID"] = custom_id

    orig_threshold = settings.threat_threshold
    try:
        resp = client.patch("/api/v1/settings", json={"threat_threshold": 0.82}, headers=headers)
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            log_row = (
                db.query(AuditLog)
                .filter(AuditLog.request_id == custom_id)
                .first()
            )
            assert log_row is not None
            assert log_row.action == "settings_update"
            assert log_row.target_resource == "threat_threshold"
            assert log_row.actor_role == "admin"
            assert "0.82" in log_row.details
            assert log_row.status == "success"
        finally:
            db.close()
    finally:
        settings.threat_threshold = orig_threshold


def test_manual_block_unblock_creates_audit_logs(client, admin_headers):
    """M14-F02: POST /block (block & unblock) creates attributed AuditLog entries."""
    block_req_id = "req-audit-block-10-0-0-199"
    headers_block = dict(admin_headers)
    headers_block["X-Request-ID"] = block_req_id

    # 1. Block
    resp_block = client.post(
        "/api/v1/block",
        json={"ip": "10.0.0.199", "action": "block", "reason": "MANUAL_OVERRIDE"},
        headers=headers_block,
    )
    assert resp_block.status_code == 200

    # 2. Unblock
    unblock_req_id = "req-audit-unblock-10-0-0-199"
    headers_unblock = dict(admin_headers)
    headers_unblock["X-Request-ID"] = unblock_req_id

    resp_unblock = client.post(
        "/api/v1/block",
        json={"ip": "10.0.0.199", "action": "unblock", "reason": "MANUAL_OVERRIDE"},
        headers=headers_unblock,
    )
    assert resp_unblock.status_code == 200

    db = SessionLocal()
    try:
        log_block = db.query(AuditLog).filter(AuditLog.request_id == block_req_id).first()
        assert log_block is not None
        assert log_block.action == "manual_block"
        assert log_block.target_resource == "ip:10.0.0.199"

        log_unblock = db.query(AuditLog).filter(AuditLog.request_id == unblock_req_id).first()
        assert log_unblock is not None
        assert log_unblock.action == "manual_unblock"
        assert log_unblock.target_resource == "ip:10.0.0.199"
    finally:
        db.close()


def test_get_audit_logs_endpoint_paginated(client, admin_headers, operator_headers):
    """M14-F02: GET /api/v1/audit-logs requires admin privilege and supports pagination."""
    # Operator cannot access audit logs
    op_resp = client.get("/api/v1/audit-logs", headers=operator_headers)
    assert op_resp.status_code == 403

    # Admin can access audit logs
    admin_resp = client.get("/api/v1/audit-logs?limit=10&offset=0", headers=admin_headers)
    assert admin_resp.status_code == 200
    data = admin_resp.json()
    assert "audit_logs" in data
    assert "total" in data
    assert "count" in data
    assert data["limit"] == 10
    assert data["offset"] == 0


# ─── 3. Forensics Query Safety & Pagination Tests (M16-F01) ───────────────────

def test_forensics_pagination_default_and_bounded(client, operator_headers):
    """M16-F01: GET /api/v1/forensics bounds results and provides total count and pagination fields."""
    resp = client.get("/api/v1/forensics", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_incidents" in data
    assert "incidents" in data
    assert data["limit"] == 100
    assert data["offset"] == 0
    assert isinstance(data["has_more"], bool)


def test_forensics_pagination_custom_limit_offset(client, operator_headers):
    """M16-F01: GET /api/v1/forensics respects explicit limit and offset."""
    # Seed 3 dummy incidents if needed
    db = SessionLocal()
    try:
        for i in range(5):
            db.add(
                Incident(
                    source_ip=f"10.0.0.{120 + i}",
                    attack_type="DDoS",
                    threat_score=0.95,
                    severity=3,
                    is_blocked=False,
                    enforcement_status="simulated",
                    data_source="manual",
                )
            )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/forensics?limit=2&offset=1", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["incidents"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 1


def test_forensics_pagination_rejects_excessive_limit(client, operator_headers):
    """M16-F01: GET /api/v1/forensics rejects queries with limit > 500 to prevent DoS."""
    resp = client.get("/api/v1/forensics?limit=501", headers=operator_headers)
    assert resp.status_code == 422  # Validation error from FastAPI


# ─── 4. Flow Snapshot Retention Cleanup Tests (M12-F02) ───────────────────────

def test_flow_snapshot_retention_cleanup():
    """M12-F02: cleanup_expired_flow_snapshots removes rows older than retention cutoff."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # 1. Add expired snapshot (30 hours old, retention default 24h)
        expired_snapshot = FlowSnapshot(
            src_ip="10.0.0.81",
            dst_ip="10.0.0.1",
            protocol="TCP",
            captured_at=now - timedelta(hours=30),
        )
        # 2. Add recent snapshot (2 hours old)
        recent_snapshot = FlowSnapshot(
            src_ip="10.0.0.82",
            dst_ip="10.0.0.1",
            protocol="TCP",
            captured_at=now - timedelta(hours=2),
        )
        db.add(expired_snapshot)
        db.add(recent_snapshot)
        db.commit()

        # Run retention cleanup with 24 hours
        deleted_count = cleanup_expired_flow_snapshots(db, retention_hours=24)
        assert deleted_count >= 1

        # Check remaining snapshots
        remaining_expired = db.query(FlowSnapshot).filter(FlowSnapshot.src_ip == "10.0.0.81").all()
        assert len(remaining_expired) == 0

        remaining_recent = db.query(FlowSnapshot).filter(FlowSnapshot.src_ip == "10.0.0.82").all()
        assert len(remaining_recent) >= 1
    finally:
        db.close()


# ─── 5. Degraded Mode Threat Detection Attribution (M09-F02) ──────────────────

def test_threat_analyzer_degraded_mode_detection_attribution():
    """M09-F02: In degraded mode, incidents and healing events are attributed as HEURISTIC_DEGRADED."""
    analyzer = ThreatAnalyzer()

    sample_flows = [
        {
            "src_ip": "10.0.0.177",
            "dst_ip": "10.0.0.1",
            "src_port": 1234,
            "dst_port": 80,
            "protocol": "TCP",
            "packet_count": 100,
            "byte_count": 10000,
            "duration_sec": 1.0,
            "data_source": "manual",
        }
    ]
    # Prediction payload indicating degraded mode
    prediction = {
        "predictions": {"10.0.0.177": 0.88},
        "ml_mode": "degraded",
        "ip_scores": {"10.0.0.177": 0.88},
    }

    alerts, healing_events = analyzer.evaluate(
        prediction=prediction,
        flows=sample_flows,
    )

    assert len(healing_events) >= 1

    db = SessionLocal()
    try:
        from app.models.incident import BlockedIP, EnforcementAction
        blocked_row = db.query(BlockedIP).filter(BlockedIP.ip_address == "10.0.0.177").first()
        assert blocked_row is not None
        assert blocked_row.reason == "HEURISTIC_DEGRADED"

        action_row = db.query(EnforcementAction).filter(EnforcementAction.ip_address == "10.0.0.177").order_by(EnforcementAction.id.desc()).first()
        assert action_row is not None
        assert action_row.reason == "HEURISTIC_DEGRADED"
    finally:
        db.close()

