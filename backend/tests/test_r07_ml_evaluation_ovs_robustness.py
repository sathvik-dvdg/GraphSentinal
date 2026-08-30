"""R-07 — ML Evaluation, OVS Counter Robustness & Threshold Integrity Tests.

Covers:
- M04-F02: OVS unidirectional counter fallback, bidirectional vs unidirectional
  feature semantics, and zero-counter numerical stability.
- M06-F02: Production threshold sensitivity sweep, decision boundary
  verification, and operational cost tradeoff testing.
- M19-F01: Enforcement daemon host binding configuration.
- Numerical stability, clipping boundaries, and graph construction invariants.
"""

import math
import os
from unittest.mock import patch

import pytest
import torch

from app.config import settings
from app.models.schemas import FlowRecord
from app.services.graph_builder import (
    _feature_row,
    build_pyg_graph,
    get_global_stats,
    reset_global_stats_cache,
)
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import ThreatAnalyzer


@pytest.fixture(autouse=True)
def clean_singletons():
    reset_global_stats_cache()
    InferenceService._instance = None
    yield
    reset_global_stats_cache()
    InferenceService._instance = None


# =====================================================================
# M04-F02 — OVS Counter Robustness & Directional Semantics
# =====================================================================

class TestM04F02_OVSCounterRobustness:
    """Tests for OVS unidirectional fallback and bidirectional counter semantics."""

    def test_unidirectional_fallback_pins_ratio_and_asymmetry(self):
        """When fwd/bwd counters are None (standard OVS single-rule telemetry),
        fwd_packets defaults to packet_count and bwd_packets to 0, pinning
        fwd_ratio to 1.0 and byte_asymmetry to +1.0."""
        flow_dict = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "packet_count": 100,
            "byte_count": 50000,
            "duration_sec": 1.0,
            "tcp_flags": 2,
            # fwd/bwd fields omitted / None
        }
        row = _feature_row(flow_dict)
        assert len(row) == 7

        # Index 0: fwd_ratio should be ~1.0
        assert math.isclose(row[0], 1.0, rel_tol=1e-4)

        # Index 1: avg_packet_size = byte_count / packet_count = 50000 / 100 = 500
        assert math.isclose(row[1], 500.0, rel_tol=1e-4)

        # Index 4: byte_asymmetry should be ~+1.0
        assert math.isclose(row[4], 1.0, rel_tol=1e-4)

    def test_bidirectional_telemetry_computes_exact_asymmetry(self):
        """When bidirectional counters are provided (enriched telemetry),
        fwd_ratio and byte_asymmetry reflect true bidirectional traffic."""
        flow_dict = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 443,
            "packet_count": 100,
            "byte_count": 60000,
            "fwd_packets": 40,
            "bwd_packets": 60,
            "fwd_bytes": 10000,
            "bwd_bytes": 50000,
            "duration_sec": 2.0,
            "tcp_flags": 16,
        }
        row = _feature_row(flow_dict)

        # Index 0: fwd_ratio = 40 / (40 + 60) = 0.40
        assert math.isclose(row[0], 0.40, rel_tol=1e-4)

        # Index 1: avg_packet_size = 60000 / 100 = 600
        assert math.isclose(row[1], 600.0, rel_tol=1e-4)

        # Index 4: byte_asymmetry = (10000 - 50000) / 60000 = -40000 / 60000 = -0.6667
        assert math.isclose(row[4], -40000.0 / 60000.0, rel_tol=1e-4)

    def test_zero_packet_zero_byte_flow_numerical_stability(self):
        """Zero packets and zero bytes do not divide by zero or produce NaN."""
        flow_dict = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "packet_count": 0,
            "byte_count": 0,
            "duration_sec": 1.0,
            "tcp_flags": 0,
        }
        row = _feature_row(flow_dict)
        assert all(math.isfinite(x) for x in row)
        # fwd_ratio = 0 / 1e-6 = 0.0
        assert math.isclose(row[0], 0.0, abs_tol=1e-5)
        # avg_packet_size = 0 / 1e-6 = 0.0
        assert math.isclose(row[1], 0.0, abs_tol=1e-5)
        # connection_rate = log1p(0) = 0.0
        assert math.isclose(row[2], 0.0, abs_tol=1e-5)
        # byte_asymmetry = 0 / 1e-6 = 0.0
        assert math.isclose(row[4], 0.0, abs_tol=1e-5)

    def test_syn_ratio_capping_at_one(self):
        """SYN flag count exceeding total packets is safely clamped to 1.0."""
        flow_dict = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "packet_count": 10,
            "byte_count": 500,
            "duration_sec": 1.0,
            "tcp_flags": 2,
            "syn_flag_count": 50,  # exceeds total packets
        }
        row = _feature_row(flow_dict)
        # Index 5: syn_ratio capped at 1.0
        assert math.isclose(row[5], 1.0, rel_tol=1e-5)

    def test_byte_rate_normalization_and_saturation(self):
        """Byte rate normalizes smoothly with log1p and saturates at 3e8 B/s."""
        # Normal rate: 1 MB/s
        normal_flow = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "packet_count": 1000,
            "byte_count": 1_000_000,
            "duration_sec": 1.0,
        }
        row_normal = _feature_row(normal_flow)
        expected_normal = math.log1p(1_000_000) / math.log1p(3e8)
        assert math.isclose(row_normal[6], expected_normal, rel_tol=1e-4)

        # Extreme rate: 10 GB/s (saturates at 3e8)
        extreme_flow = {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "packet_count": 1_000_000,
            "byte_count": 10_000_000_000,
            "duration_sec": 1.0,
            "flow_bytes_per_s": 1e10,
        }
        row_extreme = _feature_row(extreme_flow)
        assert math.isclose(row_extreme[6], 1.0, rel_tol=1e-4)

    def test_port_normalization_bounds(self):
        """Port normalization maps [0, 65535] to [0.0, 1.0]."""
        p0 = _feature_row({"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 0})
        assert math.isclose(p0[3], 0.0, abs_tol=1e-5)

        p80 = _feature_row({"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 80})
        assert math.isclose(p80[3], 80.0 / 65535.0, rel_tol=1e-5)

        p65535 = _feature_row({"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 65535})
        assert math.isclose(p65535[3], 1.0, rel_tol=1e-5)


# =====================================================================
# M06-F02 — Threshold Sensitivity & Decision Boundary
# =====================================================================

class TestM06F02_ThresholdSensitivity:
    """Tests evaluating candidate thresholds and decision boundaries."""

    @pytest.mark.parametrize("threshold,score,should_alert", [
        (0.50, 0.49, False),
        (0.50, 0.51, True),
        (0.75, 0.74, False),
        (0.75, 0.75, True),
        (0.75, 0.76, True),
        (0.90, 0.89, False),
        (0.90, 0.91, True),
    ])
    def test_threshold_decision_boundary_sweep(self, threshold, score, should_alert):
        """ThreatAnalyzer decision boundary functions consistently across threshold sweep."""
        analyzer = ThreatAnalyzer()
        analyzer.threshold = threshold

        flow = FlowRecord(
            src_ip="10.0.0.99",
            dst_ip="10.0.0.2",
            dst_port=80,
            packet_count=100,
            byte_count=5000,
        )
        pred = {"source_scores": {"10.0.0.99": score}}

        with patch.object(analyzer.healer, "block_ip", return_value={"status": "success", "enforcement_status": "enforced"}), \
             patch.object(analyzer.blockchain, "store_incident", return_value={"status": "success", "tx_hash": "0xabc"}):
            alerts, _ = analyzer.evaluate(pred, [flow])
            assert (len(alerts) > 0) == should_alert

    def test_production_default_threshold_is_conservative_075(self):
        """Verify default production configuration sets threat_threshold to 0.75."""
        assert settings.threat_threshold == 0.75

    def test_mixed_flow_batch_graph_construction(self):
        """Graph construction with both unidirectional and bidirectional flows
        produces valid normalized feature tensors and edge indices."""
        flows = [
            # Unidirectional flow (standard OVS)
            FlowRecord(
                src_ip="10.0.0.1",
                dst_ip="10.0.0.2",
                dst_port=80,
                packet_count=1000,
                byte_count=500000,
                duration_sec=1.0,
            ),
            # Bidirectional flow (enriched)
            FlowRecord(
                src_ip="10.0.0.2",
                dst_ip="10.0.0.3",
                dst_port=80,
                packet_count=200,
                byte_count=100000,
                fwd_packets=80,
                bwd_packets=120,
                fwd_bytes=30000,
                bwd_bytes=70000,
                duration_sec=1.0,
            ),
            # Third flow on different port
            FlowRecord(
                src_ip="10.0.0.3",
                dst_ip="10.0.0.4",
                dst_port=443,
                packet_count=50,
                byte_count=10000,
                duration_sec=0.5,
            ),
        ]
        graph = build_pyg_graph(flows)
        assert graph.x.shape == (3, 7)
        assert torch.isfinite(graph.x).all().item()
        assert graph.edge_index.shape[0] == 2
        # Temporal edges (0->1, 1->2) + port-sharing edge (0->1 for port 80)
        assert graph.edge_index.shape[1] >= 2


# =====================================================================
# M19-F01 — Daemon Host Binding Configuration
# =====================================================================

class TestM19F01_DaemonHostBinding:
    """Test daemon host binding configuration."""

    def test_daemon_script_host_defaults_to_localhost(self):
        """Enforcement daemon script defaults HOST to 127.0.0.1."""
        daemon_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "enforcement_daemon.py"
        )
        with open(daemon_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'HOST = os.environ.get("DAEMON_HOST", "127.0.0.1")' in content

    def test_backend_config_matches_localhost_daemon(self):
        """Backend config.py defaults daemon_host to 127.0.0.1."""
        assert settings.daemon_host == "127.0.0.1"
        assert settings.daemon_port == 50051
