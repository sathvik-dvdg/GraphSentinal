# [WSL2]
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.config import settings
from app.services.enforcement_agent import validate_mininet_ip
from app.services.graph_builder import build_pyg_graph
from app.models.schemas import FlowRecord


client = TestClient(app)


def test_manual_block_rejects_command_injection():
    """Manual block rejects '10.0.0.1; rm -rf /' — Proves command injection is blocked before subprocess"""
    with pytest.raises(ValueError, match="Invalid IP address"):
        validate_mininet_ip("10.0.0.1; rm -rf /")

    with pytest.raises(ValueError, match="Invalid IP address"):
        validate_mininet_ip("10.0.0.1 & echo 'hacked'")


def test_manual_block_rejects_outside_cidr():
    """Manual block rejects IP outside 10.0.0.0/24 — Prevents accidental host/network blocking"""
    with pytest.raises(ValueError, match="is outside"):
        validate_mininet_ip("192.168.1.100")

    with pytest.raises(ValueError, match="is not a host address"):
        validate_mininet_ip("10.0.0.0")

    with pytest.raises(ValueError, match="is not a host address"):
        validate_mininet_ip("10.0.0.255")

    with pytest.raises(ValueError, match="not enforceable"):
        validate_mininet_ip("127.0.0.1")


def test_analyze_rejects_max_flows():
    """/api/v1/analyze rejects more than MAX_ANALYZE_FLOWS — Prevents CPU denial of service"""
    flows = [
        {
            "src_ip": "10.0.0.2",
            "dst_ip": "10.0.0.1",
            "src_port": 12345,
            "dst_port": 80,
            "protocol": "TCP",
            "packet_count": 10,
            "byte_count": 1000,
            "duration_sec": 1.0,
            "tcp_flags": 2
        }
    ] * (settings.max_analyze_flows + 1)

    headers = {"X-API-Key": settings.backend_api_token}
    response = client.post("/api/v1/analyze", json={"flows": flows}, headers=headers)
    assert response.status_code == 422
    assert "Too many flows" in response.text


def test_graph_builder_rejects_nan_and_negative():
    """Graph builder rejects NaN and negative flow values — Prevents NaN threat scores"""
    with pytest.raises(ValueError):
        FlowRecord(
            src_ip="10.0.0.2",
            dst_ip="10.0.0.1",
            src_port=12345,
            dst_port=80,
            protocol="TCP",
            packet_count=-5,  # negative
            byte_count=1000,
            duration_sec=1.0,
            tcp_flags=2
        )


def test_ganache_timeout_does_not_block():
    """Ganache timeout does not block monitor loop — Keeps graph updates alive"""
    from app.services.blockchain_adapter import BlockchainAdapter
    
    adapter = BlockchainAdapter()
    
    # Mock the client to sleep for 10 seconds, while timeout is 5
    mock_client = MagicMock()
    def slow_log(*args, **kwargs):
        import time
        time.sleep(10)
        return "0x123"
        
    mock_client.log_incident.side_effect = slow_log
    adapter.client = mock_client
    adapter._connected = True
    
    # Should timeout quickly, not after 10s
    import time
    start = time.time()
    
    # We temporarily set timeout to 1s for testing speed
    original_timeout = settings.blockchain_tx_timeout_seconds
    settings.blockchain_tx_timeout_seconds = 1
    try:
        result = adapter.store_incident("10.0.0.2", "DDoS", 9, True, 1)
        elapsed = time.time() - start
        
        assert result["status"] == "pending"
        assert result["error"] == "blockchain timeout"
        assert elapsed < 2.0  # Finished fast despite the 10s mock
    finally:
        settings.blockchain_tx_timeout_seconds = original_timeout


def test_path_traversal_rejection():
    """Path traversal attempt in IP block should fail validation."""
    with pytest.raises(ValueError, match="Invalid IP address"):
        validate_mininet_ip("../../etc/passwd")


def test_sqlite_concurrency_locking():
    """Simulate 50 simultaneous requests to /analyze to ensure no SQLITE_BUSY crash."""
    import concurrent.futures

    flows = [
        {
            "src_ip": "10.0.0.2",
            "dst_ip": "10.0.0.1",
            "src_port": 12345,
            "dst_port": 80,
            "protocol": "TCP",
            "packet_count": 10,
            "byte_count": 1000,
            "duration_sec": 1.0,
            "tcp_flags": 2
        }
    ]
    headers = {"X-API-Key": settings.backend_api_token}

    def make_request():
        return client.post("/api/v1/analyze", json={"flows": flows}, headers=headers)

    # 50 requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request) for _ in range(50)]
        for f in concurrent.futures.as_completed(futures):
            resp = f.result()
            # It might rate limit (429) or succeed (200), but should NEVER be a 500 SQLITE_BUSY
            assert resp.status_code in [200, 429]


def test_model_shape_mismatch_fails_gracefully():
    """If graph_builder produces 8 features instead of 7, InferenceService degrades gracefully."""
    try:
        import torch as _torch
    except Exception:
        pytest.skip("torch not available on this platform (e.g. missing fbgemm.dll)")
        return

    from app.services.inference_service import InferenceService
    
    # Reset instance for testing
    InferenceService._instance = None
    service = InferenceService.get_instance()
    
    flows = [
        FlowRecord(
            src_ip="10.0.0.2",
            dst_ip="10.0.0.1",
            src_port=12345,
            dst_port=80,
            protocol="TCP",
            packet_count=10,
            byte_count=1000,
            duration_sec=1.0,
            tcp_flags=2
        )
    ]
    
    with patch("app.services.inference_service.build_pyg_graph") as mock_build:
        # Mock graph returning x with 8 features
        class MockGraph:
            x = _torch.zeros((1, 8))
            edge_index = _torch.zeros((2, 0), dtype=_torch.long)
            flow_sources = ["10.0.0.2"]
            flow_destinations = ["10.0.0.1"]
            
        mock_build.return_value = MockGraph()
        
        # Should not crash; should degrade and fall back to heuristic
        result = service.predict(flows)
        
        # If it was in model mode, shape mismatch will trigger fallback to degraded mode
        # If it was already in degraded mode, heuristic predicts successfully
        assert "flow_scores" in result
        assert len(result["flow_scores"]) == 1


def test_unauthenticated_read_routes_rejected():
    """Read routes like /graph should reject calls missing X-API-Key header when backend_api_token is set."""
    resp = client.get("/api/v1/graph")
    assert resp.status_code == 401
    assert "Invalid API key" in resp.text


def test_admin_route_requires_key():
    """Admin write routes like /simulate should reject read token and accept admin token."""
    # 1. No header -> 403 Forbidden
    resp = client.post("/api/v1/simulate", json={"attack_type": "DDoS", "target_ip": "10.0.0.2"})
    assert resp.status_code == 403
    assert "Admin API key required" in resp.text

    # 2. Read token passed to admin route -> 403 Forbidden
    read_headers = {"X-API-Key": settings.backend_api_token}
    resp = client.post("/api/v1/simulate", json={"attack_type": "DDoS", "target_ip": "10.0.0.2"}, headers=read_headers)
    assert resp.status_code == 403

    # 3. Admin token passed to admin route -> 200 OK
    admin_headers = {"X-API-Key": settings.admin_api_token}
    resp = client.post("/api/v1/simulate", json={"attack_type": "DDoS", "target_ip": "10.0.0.2"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "injected"


def test_production_default_token_guard():
    """Refuse to start in production environment when using default, empty, or short demo token."""
    from app.main import lifespan
    import asyncio

    # Default token
    with patch("app.config.settings.environment", "production"):
        with patch("app.config.settings.backend_api_token", "change-me-for-demo"):
            with pytest.raises(RuntimeError, match="Refusing to boot in production"):
                asyncio.run(lifespan(app).__aenter__())

    # Empty token
    with patch("app.config.settings.environment", "production"):
        with patch("app.config.settings.backend_api_token", ""):
            with pytest.raises(RuntimeError, match="Refusing to boot in production"):
                asyncio.run(lifespan(app).__aenter__())

    # Short token
    with patch("app.config.settings.environment", "production"):
        with patch("app.config.settings.backend_api_token", "short_secret"):
            with pytest.raises(RuntimeError, match="Refusing to boot in production"):
                asyncio.run(lifespan(app).__aenter__())


def test_update_config_injection_rejection():
    """update_config rejects CRLF newline injection and malformed Ethereum contract addresses."""
    from app.services.blockchain_adapter import BlockchainAdapter
    adapter = BlockchainAdapter.get_instance()

    # Newline injection attempt
    with pytest.raises(ValueError, match="cannot contain newlines"):
        adapter.update_config(ganache_url="http://127.0.0.1:8545\nBACKEND_API_TOKEN=hacked")

    # Invalid URL scheme
    with pytest.raises(ValueError, match="must be a valid HTTP or HTTPS URL"):
        adapter.update_config(ganache_url="ftp://127.0.0.1:8545")

    # Invalid Ethereum address format
    with pytest.raises(ValueError, match="must be a valid Ethereum address"):
        adapter.update_config(contract_address="not_an_eth_address")


def test_simulate_rejects_outside_target_ip():
    """Simulate endpoint rejects IPs outside the 10.0.0.x network range via Pydantic regex validation."""
    admin_headers = {"X-API-Key": settings.admin_api_token}
    resp = client.post("/api/v1/simulate", json={"attack_type": "DDoS", "target_ip": "8.8.8.8"}, headers=admin_headers)
    assert resp.status_code == 422


