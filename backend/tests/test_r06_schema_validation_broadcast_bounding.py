"""R-06 — Schema-Layer IP Validation & Bounded Graph Broadcast Tests.

M11-F01: FlowRecord.src_ip / dst_ip must reject malformed IPs at the
         Pydantic schema boundary before graph construction or persistence.

M16-F02: emit_analysis_events must emit bounded compact graph projections
         instead of full snapshots to mitigate O(M×N) broadcast amplification.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.models.schemas import FlowRecord
from app.websocket.events import (
    _MAX_BROADCAST_LINKS,
    _MAX_BROADCAST_NODES,
    _compact_graph_snapshot,
    emit_analysis_events,
)


# =====================================================================
# M11-F01 — Schema-Layer IP Validation
# =====================================================================

class TestM11F01_IPValidation:
    """FlowRecord must validate src_ip/dst_ip at the Pydantic boundary."""

    def test_valid_ipv4_accepted(self):
        """Standard Mininet IPv4 addresses are accepted."""
        flow = FlowRecord(src_ip="10.0.0.1", dst_ip="10.0.0.2", dst_port=80)
        assert flow.src_ip == "10.0.0.1"
        assert flow.dst_ip == "10.0.0.2"

    def test_valid_ipv4_boundary_addresses(self):
        """Boundary-valid IPv4 addresses are accepted."""
        flow = FlowRecord(src_ip="1.0.0.1", dst_ip="254.254.254.254", dst_port=80)
        assert flow.src_ip == "1.0.0.1"
        assert flow.dst_ip == "254.254.254.254"

    def test_valid_ipv4_loopback(self):
        """127.0.0.1 is a valid IPv4 format (enforcement CIDR check is downstream)."""
        flow = FlowRecord(src_ip="127.0.0.1", dst_ip="10.0.0.1", dst_port=80)
        assert flow.src_ip == "127.0.0.1"

    def test_valid_ipv4_zero_padded_normalized(self):
        """IP addresses with leading whitespace are stripped."""
        flow = FlowRecord(src_ip=" 10.0.0.1 ", dst_ip="10.0.0.2", dst_port=80)
        assert flow.src_ip == "10.0.0.1"

    def test_invalid_src_ip_rejected(self):
        """Non-IP source string rejected at schema boundary."""
        with pytest.raises(ValidationError, match="Invalid IP address"):
            FlowRecord(src_ip="not-an-ip", dst_ip="10.0.0.2", dst_port=80)

    def test_invalid_dst_ip_rejected(self):
        """Non-IP destination string rejected at schema boundary."""
        with pytest.raises(ValidationError, match="Invalid IP address"):
            FlowRecord(src_ip="10.0.0.1", dst_ip="malformed", dst_port=80)

    def test_empty_ip_rejected(self):
        """Empty string IP rejected."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="", dst_ip="10.0.0.2", dst_port=80)

    def test_whitespace_only_ip_rejected(self):
        """Whitespace-only IP rejected."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="   ", dst_ip="10.0.0.2", dst_port=80)

    def test_cidr_notation_rejected(self):
        """CIDR notation is not a valid host IP."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="10.0.0.1/24", dst_ip="10.0.0.2", dst_port=80)

    def test_ip_with_port_rejected(self):
        """IP:port notation is not a valid IP."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="10.0.0.1:80", dst_ip="10.0.0.2", dst_port=80)

    def test_out_of_range_octets_rejected(self):
        """Octets > 255 are not valid IPv4."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="999.999.999.999", dst_ip="10.0.0.2", dst_port=80)

    def test_incomplete_ip_rejected(self):
        """Incomplete IP address rejected."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="10.0.0", dst_ip="10.0.0.2", dst_port=80)

    def test_ipv6_rejected(self):
        """IPv6 addresses are rejected (system is IPv4-only / Mininet)."""
        with pytest.raises(ValidationError, match="Only IPv4"):
            FlowRecord(src_ip="::1", dst_ip="10.0.0.2", dst_port=80)
        with pytest.raises(ValidationError, match="Only IPv4"):
            FlowRecord(src_ip="2001:db8::1", dst_ip="10.0.0.2", dst_port=80)

    def test_command_injection_attempt_rejected(self):
        """Shell injection payload is rejected at schema boundary."""
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="10.0.0.1; rm -rf /", dst_ip="10.0.0.2", dst_port=80)

    def test_existing_mininet_topology_addresses(self):
        """All baseline Mininet topology addresses (10.0.0.1-10) are valid."""
        for i in range(1, 11):
            flow = FlowRecord(src_ip=f"10.0.0.{i}", dst_ip="10.0.0.1", dst_port=80)
            assert flow.src_ip == f"10.0.0.{i}"

    def test_validation_before_graph_construction(self):
        """Malformed IPs are rejected before they could reach graph_builder."""
        # This test proves the rejection happens at the FlowRecord level,
        # which is the entry point before analyze_flows -> build_pyg_graph.
        with pytest.raises(ValidationError):
            FlowRecord(src_ip="MALICIOUS", dst_ip="10.0.0.2", dst_port=80)

    def test_both_ips_validated_independently(self):
        """Both src_ip AND dst_ip are validated independently."""
        # Valid src, invalid dst
        with pytest.raises(ValidationError, match="dst_ip"):
            FlowRecord(src_ip="10.0.0.1", dst_ip="bad", dst_port=80)
        # Invalid src, valid dst
        with pytest.raises(ValidationError, match="src_ip"):
            FlowRecord(src_ip="bad", dst_ip="10.0.0.2", dst_port=80)

    def test_special_addresses_accepted(self):
        """0.0.0.0 and 255.255.255.255 are valid IPv4 format (enforcement checks downstream)."""
        flow = FlowRecord(src_ip="0.0.0.0", dst_ip="255.255.255.255", dst_port=80)
        assert flow.src_ip == "0.0.0.0"
        assert flow.dst_ip == "255.255.255.255"


# =====================================================================
# M16-F02 — Bounded Graph Broadcast
# =====================================================================

class TestM16F02_BoundedBroadcast:
    """emit_analysis_events must emit bounded compact graph projections."""

    def _make_nodes(self, count: int) -> list[dict]:
        """Generate count synthetic node dicts."""
        return [
            {
                "id": f"10.0.{i // 256}.{i % 256}",
                "label": f"h{i}",
                "status": "normal",
                "threat_score": round(i / count, 4) if count > 0 else 0.0,
                "connections": 1,
                "bytes_total": 100,
                "attack_type": None,
                "is_blocked": False,
                "source": "observed",
                "data_source": "manual",
            }
            for i in range(count)
        ]

    def _make_links(self, count: int) -> list[dict]:
        """Generate count synthetic link dicts."""
        return [
            {
                "source": f"10.0.0.{i % 256}",
                "target": f"10.0.0.{(i + 1) % 256}",
                "value": round(i / count, 4) if count > 0 else 0.0,
                "attack_type": None,
                "packet_count": 10,
                "data_source": "manual",
            }
            for i in range(count)
        ]

    def test_compact_small_graph_not_truncated(self):
        """Small graphs below limits are passed through without truncation."""
        snapshot = {
            "nodes": self._make_nodes(10),
            "links": self._make_links(5),
            "metadata": {"total_nodes": 10, "malicious_nodes": 0, "blocked_nodes": 0},
        }
        compact = _compact_graph_snapshot(snapshot)
        assert len(compact["nodes"]) == 10
        assert len(compact["links"]) == 5
        assert compact["truncated"] is False
        assert compact["total_nodes"] == 10
        assert compact["total_links"] == 5
        assert "metadata" in compact

    def test_compact_large_graph_truncated(self):
        """Large graphs are bounded to _MAX_BROADCAST_NODES / _MAX_BROADCAST_LINKS."""
        snapshot = {
            "nodes": self._make_nodes(200),
            "links": self._make_links(300),
            "metadata": {"total_nodes": 200},
        }
        compact = _compact_graph_snapshot(snapshot)
        assert len(compact["nodes"]) == _MAX_BROADCAST_NODES
        assert len(compact["links"]) == _MAX_BROADCAST_LINKS
        assert compact["truncated"] is True
        assert compact["total_nodes"] == 200
        assert compact["total_links"] == 300

    def test_compact_preserves_highest_threat_nodes(self):
        """Truncated broadcast includes nodes sorted by highest threat_score first."""
        nodes = self._make_nodes(100)
        # Assign a known high score to a specific node
        nodes[99]["threat_score"] = 0.99
        nodes[99]["id"] = "10.0.0.99"
        snapshot = {"nodes": nodes, "links": [], "metadata": {}}
        compact = _compact_graph_snapshot(snapshot)
        # The highest-scoring node must be in the compact output
        node_ids = [n["id"] for n in compact["nodes"]]
        assert "10.0.0.99" in node_ids
        # First node should be the highest threat
        assert compact["nodes"][0]["threat_score"] == 0.99

    def test_compact_preserves_metadata(self):
        """Metadata is always included in compact snapshot."""
        snapshot = {
            "nodes": [],
            "links": [],
            "metadata": {"last_updated": "2026-08-30T00:00:00Z", "malicious_nodes": 5},
        }
        compact = _compact_graph_snapshot(snapshot)
        assert compact["metadata"]["malicious_nodes"] == 5

    def test_compact_handles_non_dict(self):
        """Non-dict input is passed through unchanged."""
        assert _compact_graph_snapshot("not-a-dict") == "not-a-dict"
        assert _compact_graph_snapshot(None) is None

    def test_compact_empty_graph(self):
        """Empty graph snapshot is handled safely."""
        snapshot = {"nodes": [], "links": [], "metadata": {}}
        compact = _compact_graph_snapshot(snapshot)
        assert compact["nodes"] == []
        assert compact["links"] == []
        assert compact["truncated"] is False
        assert compact["total_nodes"] == 0
        assert compact["total_links"] == 0

    def test_emit_uses_compact_snapshot(self):
        """emit_analysis_events emits compact payload, not full snapshot."""
        mock_sio = MagicMock()
        emitted_payloads = []

        async def capture_emit(event, data):
            emitted_payloads.append((event, data))

        mock_sio.emit = AsyncMock(side_effect=capture_emit)

        large_snapshot = {
            "nodes": self._make_nodes(200),
            "links": self._make_links(300),
            "metadata": {"total_nodes": 200},
        }
        result = {
            "graph_snapshot": large_snapshot,
            "alerts": [],
            "healing_events": [],
        }

        asyncio.run(emit_analysis_events(mock_sio, result))

        # Find the graph_update emission
        graph_emissions = [(e, d) for e, d in emitted_payloads if e == "graph_update"]
        assert len(graph_emissions) == 1
        _, emitted = graph_emissions[0]
        assert len(emitted["nodes"]) == _MAX_BROADCAST_NODES
        assert len(emitted["links"]) == _MAX_BROADCAST_LINKS
        assert emitted["truncated"] is True

    def test_emit_preserves_r05_error_isolation(self):
        """R-05 error isolation remains intact — exceptions don't propagate."""
        mock_sio = MagicMock()
        mock_sio.emit = AsyncMock(side_effect=RuntimeError("Transport failure"))

        result = {
            "graph_snapshot": {"nodes": [{"threat_score": 0.5}], "links": [], "metadata": {}},
            "alerts": [{"ip": "10.0.0.5"}],
            "healing_events": [{"ip": "10.0.0.5"}],
        }

        # Must complete without raising
        asyncio.run(emit_analysis_events(mock_sio, result))

    def test_emit_none_and_non_dict_safety(self):
        """None/non-dict inputs handled safely (R-05 contract preserved)."""
        mock_sio = MagicMock()
        mock_sio.emit = AsyncMock()
        asyncio.run(emit_analysis_events(None, {"graph_snapshot": {}}))
        asyncio.run(emit_analysis_events(mock_sio, None))

    def test_bounded_broadcast_no_memory_growth(self):
        """Repeated compact_graph_snapshot calls don't accumulate state."""
        for _ in range(100):
            snapshot = {
                "nodes": self._make_nodes(500),
                "links": self._make_links(500),
                "metadata": {},
            }
            compact = _compact_graph_snapshot(snapshot)
            assert len(compact["nodes"]) == _MAX_BROADCAST_NODES
            assert len(compact["links"]) == _MAX_BROADCAST_LINKS
