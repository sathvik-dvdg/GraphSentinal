import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.deps import _login_attempts, _prune_rate_limit_map, _requests
from app.config import settings
from app.main import app, sio
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import infer_attack_type
from app.websocket.events import emit_analysis_events


@pytest.fixture
def client():
    return TestClient(app)


def test_r05_inference_service_reload_model_recovers(monkeypatch):
    """M10-F01: InferenceService.reload_model() recovers from degraded mode to model mode."""
    svc = InferenceService.get_instance()
    
    # Simulate degraded mode
    svc.mode = "degraded"
    svc.model = None
    svc.degraded_reason = "Simulated temporary disk outage"
    
    assert svc.mode == "degraded"
    assert svc.health()["mode"] == "degraded"
    
    # Trigger reload
    recovered = svc.reload_model()
    assert recovered is True
    assert svc.mode == "model"
    assert svc.model is not None
    assert svc.degraded_reason == ""
    assert svc.health()["mode"] == "model"


def test_r05_inference_service_reload_handles_missing_weights(monkeypatch):
    """M10-F01: reload_model() handles missing weights gracefully without crashing."""
    svc = InferenceService.get_instance()
    
    with patch.object(svc, "_existing_weights_path", return_value=None):
        recovered = svc.reload_model()
        assert recovered is False
        assert svc.mode == "degraded"
        assert "not found" in svc.degraded_reason.lower()
        
    # Restore model mode for other tests
    svc.reload_model()
    assert svc.mode == "model"


def test_r05_ml_reload_endpoint_rbac(client):
    """M10-F01 / R-03: POST /api/v1/ml/reload enforces admin RBAC."""
    # 1. Unauthenticated -> 401
    resp = client.post("/api/v1/ml/reload")
    assert resp.status_code == 401

    # 2. Operator token -> 403
    resp_op = client.post(
        "/api/v1/ml/reload",
        headers={"X-API-Key": "operator-test-token"},
    )
    # If operator token is configured or mocked
    if settings.backend_api_token:
        resp_op = client.post(
            "/api/v1/ml/reload",
            headers={"X-API-Key": settings.backend_api_token},
        )
        assert resp_op.status_code == 403

    # 3. Admin token -> 200
    if settings.admin_api_token:
        resp_admin = client.post(
            "/api/v1/ml/reload",
            headers={"X-API-Key": settings.admin_api_token},
        )
        assert resp_admin.status_code == 200
        data = resp_admin.json()
        assert data["status"] in {"ok", "degraded"}
        assert data["mode"] in {"model", "degraded"}


def test_r05_rate_limiter_pruning_bounds_memory():
    """M11-F01: _prune_rate_limit_map evicts expired client deques when size exceeds max_entries."""
    mock_map = {}
    now = 1000.0
    window = 60.0

    # Populate 100 entries: 50 expired, 50 active
    for i in range(50):
        mock_map[f"expired_{i}"] = deque([now - 100.0])
    for i in range(50):
        mock_map[f"active_{i}"] = deque([now - 10.0])

    assert len(mock_map) == 100

    # Prune with max_entries = 40 (triggering eviction)
    _prune_rate_limit_map(mock_map, now=now, window=window, max_entries=40)

    # All expired entries must be pruned
    assert len(mock_map) == 50
    assert all(k.startswith("active_") for k in mock_map)


def test_r05_websocket_emit_analysis_events_isolation():
    """M16-F02, M17-F01: emit_analysis_events isolates exceptions without disrupting caller."""
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock(side_effect=RuntimeError("Socket.IO serialization error"))

    payload = {
        "graph_snapshot": {"nodes": [], "edges": []},
        "alerts": [{"ip": "10.0.0.5", "attack_type": "DDoS", "score": 0.95}],
        "healing_events": [{"ip": "10.0.0.5", "action": "block"}],
    }

    # Must complete cleanly without raising exception
    asyncio.run(emit_analysis_events(mock_sio, payload))

    # None and non-dict payload safety
    asyncio.run(emit_analysis_events(None, payload))
    asyncio.run(emit_analysis_events(mock_sio, None))


def test_r05_infer_attack_type_defensiveness():
    """M09-F01: infer_attack_type handles edge-case/malformed flow dicts cleanly."""
    # 1. Normal SSHBrute
    flows_ssh = [{"dst_port": 22, "packet_count": 300, "byte_count": 1000}]
    assert infer_attack_type("10.0.0.1", 0.85, flows_ssh) == "SSHBrute"

    # 2. Normal PortScan (5+ distinct ports)
    flows_scan = [{"dst_port": p, "packet_count": 5} for p in [80, 443, 21, 25, 8080]]
    assert infer_attack_type("10.0.0.2", 0.85, flows_scan) == "PortScan"

    # 3. Normal DoSHulk (> 1,000,000 HTTP bytes)
    flows_hulk = [{"dst_port": 80, "packet_count": 100, "byte_count": 1_500_000}]
    assert infer_attack_type("10.0.0.3", 0.85, flows_hulk) == "DoSHulk"

    # 4. Normal DDoS (score >= 0.90 or > 5000 packets)
    flows_ddos = [{"dst_port": 80, "packet_count": 6000, "byte_count": 5000}]
    assert infer_attack_type("10.0.0.4", 0.95, flows_ddos) == "DDoS"

    # 5. Default Botnet
    flows_bot = [{"dst_port": 445, "packet_count": 10, "byte_count": 500}]
    assert infer_attack_type("10.0.0.5", 0.76, flows_bot) == "Botnet"

    # 6. Malformed/non-dict elements and None values handled safely
    malformed_flows = [
        None,
        "not_a_dict",
        {"dst_port": None, "packet_count": "invalid", "byte_count": None},
        {"dst_port": 22, "packet_count": 500, "byte_count": 100},
    ]
    assert infer_attack_type("10.0.0.6", 0.85, malformed_flows) == "SSHBrute"
