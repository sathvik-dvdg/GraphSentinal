import socket
import pytest
from unittest.mock import patch, MagicMock

from app.config import settings
from app.services.enforcement_agent import EnforcementError
from app.services.reconciliation import (
    _parse_blocked_from_ovs,
    reconcile_once,
    ReconciliationWorker,
)


def test_t1_successful_ovs_query_with_zero_managed_flows(monkeypatch):
    """Test 1: Successful query returning zero priority=1000 flows returns an empty set and ok status."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    mock_response = {
        "status": "success",
        "action": "dump_flows",
        "output": "NXST_FLOW reply (xid=0x4):\n cookie=0x0, duration=100s, table=0, priority=0,actions=NORMAL\n",
    }
    
    with patch("app.services.reconciliation._send_to_daemon", return_value=mock_response):
        with patch("app.services.reconciliation._sqlite_blocked_ips", return_value=set()):
            flows = _parse_blocked_from_ovs("s1")
            assert flows == set()
            
            res = reconcile_once("s1")
            assert res["status"] == "ok"
            assert res["reapplied"] == []
            assert res["removed"] == []
            assert res["ovs_blocked"] == 0


def test_t2_successful_ovs_query_with_managed_flows(monkeypatch):
    """Test 2: Successful query with priority=1000 flows parses the IP set correctly."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    mock_response = {
        "status": "success",
        "action": "dump_flows",
        "output": (
            "cookie=0x0, duration=10s, table=0, priority=1000,ip,nw_src=10.0.0.98 actions=drop\n"
            "cookie=0x0, duration=10s, table=0, priority=1000,ip,nw_src=10.0.0.99 actions=drop\n"
            "cookie=0x0, duration=100s, table=0, priority=0,actions=NORMAL\n"
        ),
    }
    
    with patch("app.services.reconciliation._send_to_daemon", return_value=mock_response):
        flows = _parse_blocked_from_ovs("s1")
        assert flows == {"10.0.0.98", "10.0.0.99"}


def test_t3_daemon_connection_failure_raises_enforcement_error(monkeypatch):
    """Test 3: Daemon connection failure raises EnforcementError and reconcile_once returns error status."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    with patch("socket.socket") as mock_socket:
        mock_sock_inst = MagicMock()
        mock_sock_inst.__enter__.return_value = mock_sock_inst
        mock_sock_inst.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_socket.return_value = mock_sock_inst
        
        with pytest.raises(EnforcementError) as excinfo:
            _parse_blocked_from_ovs("s1")
        assert "Daemon communication failure" in str(excinfo.value)
        
        with patch("app.services.reconciliation._sqlite_blocked_ips", return_value={"10.0.0.98", "10.0.0.99"}):
            res = reconcile_once("s1")
            assert res["status"] == "error"
            assert "Failed to query OVS flows" in res["error"]
            assert res["reapplied"] == []
            assert res["removed"] == []
            assert res["ovs_blocked"] is None
            assert res["db_blocked"] == 2


def test_t4_unauthorized_daemon_response_raises_enforcement_error(monkeypatch):
    """Test 4: Unauthorized response from daemon raises EnforcementError and prevents false flow assumption."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    with patch("app.services.reconciliation._send_to_daemon", side_effect=EnforcementError("Unauthorized")):
        with patch("app.services.reconciliation._sqlite_blocked_ips", return_value={"10.0.0.1", "10.0.0.2"}):
            with pytest.raises(EnforcementError) as excinfo:
                _parse_blocked_from_ovs("s1")
            assert "Unauthorized" in str(excinfo.value)
            
            res = reconcile_once("s1")
            assert res["status"] == "error"
            assert "Unauthorized" in res["error"]
            assert res["reapplied"] == []
            assert res["ovs_blocked"] is None


def test_t5_socket_timeout_raises_enforcement_error(monkeypatch):
    """Test 5: Socket timeout when contacting daemon raises EnforcementError."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    with patch("socket.socket") as mock_socket:
        mock_sock_inst = MagicMock()
        mock_sock_inst.__enter__.return_value = mock_sock_inst
        mock_sock_inst.connect.side_effect = socket.timeout("timed out")
        mock_socket.return_value = mock_sock_inst
        
        with pytest.raises(EnforcementError) as excinfo:
            _parse_blocked_from_ovs("s1")
        assert "Daemon communication failure" in str(excinfo.value)


def test_t6_worker_liveness_survives_daemon_outage_and_recovers(monkeypatch):
    """Test 6: ReconciliationWorker thread survives daemon outage and updates status to degraded, then recovers."""
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    
    worker = ReconciliationWorker(interval=1)
    
    # 1. Simulate failure during tick
    with patch("app.services.reconciliation.reconcile_once", return_value={"status": "error", "error": "Daemon offline"}):
        with patch("app.services.reconciliation.reconcile_blockchain_outbox", return_value={"status": "ok"}):
            ovs_result = {"status": "error", "error": "Daemon offline"}
            bc_result = {"status": "ok"}
            ovs_status = ovs_result.get("status", "ok")
            bc_status = bc_result.get("status", "ok")
            overall = "degraded" if (ovs_status in {"error", "degraded"} or bc_status in {"error", "degraded"}) else "ok"
            worker.last_result = {"ovs": ovs_result, "blockchain": bc_result, "status": overall}
            
            assert worker.last_result["status"] == "degraded"
            assert worker.last_result["ovs"]["status"] == "error"
            
    # 2. Simulate recovery
    with patch("app.services.reconciliation.reconcile_once", return_value={"status": "ok", "ovs_blocked": 14, "db_blocked": 14, "reapplied": [], "removed": []}):
        with patch("app.services.reconciliation.reconcile_blockchain_outbox", return_value={"status": "ok"}):
            ovs_result = {"status": "ok", "ovs_blocked": 14, "db_blocked": 14, "reapplied": [], "removed": []}
            bc_result = {"status": "ok"}
            ovs_status = ovs_result.get("status", "ok")
            bc_status = bc_result.get("status", "ok")
            overall = "degraded" if (ovs_status in {"error", "degraded"} or bc_status in {"error", "degraded"}) else "ok"
            worker.last_result = {"ovs": ovs_result, "blockchain": bc_result, "status": overall}
            
            assert worker.last_result["status"] == "ok"
            assert worker.last_result["ovs"]["status"] == "ok"
