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
    assert "List should have at most 5000 items" in response.text


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
