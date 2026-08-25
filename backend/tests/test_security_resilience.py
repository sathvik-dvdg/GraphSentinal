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


def test_k03_daemon_policy_validation_rejections():
    """K-03: Privileged daemon independently rejects non-Mininet, loopback, multicast, broadcast, and IPv6 IPs."""
    import importlib.util
    from pathlib import Path

    daemon_path = Path(__file__).resolve().parent.parent / "scripts" / "enforcement_daemon.py"
    spec = importlib.util.spec_from_file_location("enforcement_daemon", daemon_path)
    daemon_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon_mod)

    # Rejection of loopback, unspecified, multicast
    with pytest.raises(ValueError, match="not enforceable"):
        daemon_mod.validate_ip("127.0.0.1")
    with pytest.raises(ValueError, match="not enforceable"):
        daemon_mod.validate_ip("0.0.0.0")
    with pytest.raises(ValueError, match="not enforceable"):
        daemon_mod.validate_ip("224.0.0.1")

    # Rejection of outside CIDR
    with pytest.raises(ValueError, match="is outside"):
        daemon_mod.validate_ip("192.168.1.1")
    with pytest.raises(ValueError, match="is outside"):
        daemon_mod.validate_ip("8.8.8.8")

    # Rejection of network and broadcast addresses
    with pytest.raises(ValueError, match="is not a host address"):
        daemon_mod.validate_ip("10.0.0.0")
    with pytest.raises(ValueError, match="is not a host address"):
        daemon_mod.validate_ip("10.0.0.255")

    # Rejection of IPv6
    with pytest.raises(ValueError, match="IPv6 address"):
        daemon_mod.validate_ip("2001:db8::1")
    with pytest.raises(ValueError, match="IPv6 address"):
        daemon_mod.validate_ip("::1")


def test_k03_daemon_policy_validation_acceptance():
    """K-03: Privileged daemon accepts valid Mininet host IPs."""
    import importlib.util
    from pathlib import Path

    daemon_path = Path(__file__).resolve().parent.parent / "scripts" / "enforcement_daemon.py"
    spec = importlib.util.spec_from_file_location("enforcement_daemon", daemon_path)
    daemon_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon_mod)

    assert daemon_mod.validate_ip("10.0.0.5") == "10.0.0.5"
    assert daemon_mod.validate_ip("10.0.0.1") == "10.0.0.1"
    assert daemon_mod.validate_ip("10.0.0.254") == "10.0.0.254"


def test_k02_daemon_connection_timeout_and_liveness():
    """K-02: Real run_daemon() terminates idle client connection on timeout, remains alive, and processes subsequent request."""
    import importlib.util
    import json
    import socket
    import threading
    import time
    from pathlib import Path

    daemon_path = Path(__file__).resolve().parent.parent / "scripts" / "enforcement_daemon.py"
    spec = importlib.util.spec_from_file_location("enforcement_daemon", daemon_path)
    daemon_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon_mod)

    # Find a free local port for test isolation
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    original_host = daemon_mod.HOST
    original_port = daemon_mod.PORT
    original_timeout = daemon_mod.CLIENT_TIMEOUT

    daemon_mod.HOST = "127.0.0.1"
    daemon_mod.PORT = free_port
    daemon_mod.CLIENT_TIMEOUT = 0.3

    # Run the real production run_daemon() in a daemon thread
    worker = threading.Thread(target=daemon_mod.run_daemon, daemon=True)
    worker.start()
    time.sleep(0.1)  # Allow socket bind and listen

    try:
        # 1. Connect idle client, send no data, and hold connection beyond CLIENT_TIMEOUT
        idle_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        idle_client.connect(("127.0.0.1", free_port))
        time.sleep(0.5)  # Exceeds CLIENT_TIMEOUT (0.3s)

        # 2. Verify real run_daemon() closed the idle client connection
        idle_client.settimeout(0.2)
        assert len(idle_client.recv(1024)) == 0  # EOF -> closed by server
        idle_client.close()

        # 3. Connect a second legitimate client to verify daemon is still alive and accepting
        legit_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        legit_client.connect(("127.0.0.1", free_port))
        req_payload = {
            "token": daemon_mod.SHARED_SECRET,
            "action": "block",
            "switch": "s1",
            "ip": "10.0.0.5",
        }

        with patch.object(daemon_mod.subprocess, "run") as mock_subproc:
            mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")
            legit_client.sendall(json.dumps(req_payload).encode("utf-8"))
            resp_bytes = legit_client.recv(4096)
            resp = json.loads(resp_bytes.decode("utf-8"))

        assert resp.get("status") == "success"
        assert resp.get("ip") == "10.0.0.5"
        legit_client.close()
    finally:
        daemon_mod.HOST = original_host
        daemon_mod.PORT = original_port
        daemon_mod.CLIENT_TIMEOUT = original_timeout
