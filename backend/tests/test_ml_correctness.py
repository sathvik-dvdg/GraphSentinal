import os
import pytest
import torch
from unittest.mock import patch
from pathlib import Path

from app.config import settings
from app.models.schemas import FlowRecord
from app.services.graph_builder import (
    build_pyg_graph,
    get_global_stats,
    reset_global_stats_cache,
    _feature_row,
)
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import ThreatAnalyzer


@pytest.fixture(autouse=True)
def ensure_service_setup():
    reset_global_stats_cache()
    InferenceService._instance = None
    yield
    reset_global_stats_cache()
    InferenceService._instance = None


def test_single_flow_n1_normalization_non_zero():
    """Test A (M04-F01 / M01-F03): N=1 single flow does not collapse to zero vector."""
    flow = FlowRecord(
        src_ip="10.0.0.99",
        dst_ip="10.0.0.2",
        dst_port=80,
        packet_count=5000,
        byte_count=500000,
        duration_sec=1.0,
        tcp_flags=2,
    )
    graph = build_pyg_graph([flow])
    assert graph.x.shape == (1, 7)
    assert not torch.all(graph.x == 0).item()
    assert torch.isfinite(graph.x).all().item()


def test_batch_context_independence():
    """Test B (M08-F02): Target flow normalized features are identical regardless of batch context."""
    target = FlowRecord(
        src_ip="10.0.0.99",
        dst_ip="10.0.0.2",
        dst_port=80,
        packet_count=5000,
        byte_count=500000,
        duration_sec=1.0,
        tcp_flags=2,
    )
    benign1 = FlowRecord(
        src_ip="10.0.0.10",
        dst_ip="10.0.0.2",
        dst_port=53,
        packet_count=2,
        byte_count=150,
        duration_sec=0.05,
        tcp_flags=0,
    )
    benign2 = FlowRecord(
        src_ip="10.0.0.11",
        dst_ip="10.0.0.3",
        dst_port=443,
        packet_count=20,
        byte_count=15000,
        duration_sec=2.0,
        tcp_flags=16,
    )

    g1 = build_pyg_graph([target])
    g2 = build_pyg_graph([target, benign1])
    g3 = build_pyg_graph([target, benign1, benign2])

    assert torch.equal(g1.x[0], g2.x[0])
    assert torch.equal(g1.x[0], g3.x[0])


def test_batch_permutation_stability():
    """Test C: Reordering flows does not alter per-flow normalized features."""
    flow_a = FlowRecord(
        src_ip="10.0.0.1",
        dst_ip="10.0.0.2",
        dst_port=80,
        packet_count=100,
        byte_count=10000,
        duration_sec=1.0,
        tcp_flags=2,
    )
    flow_b = FlowRecord(
        src_ip="10.0.0.2",
        dst_ip="10.0.0.3",
        dst_port=443,
        packet_count=50,
        byte_count=5000,
        duration_sec=0.5,
        tcp_flags=16,
    )

    g_ab = build_pyg_graph([flow_a, flow_b])
    g_ba = build_pyg_graph([flow_b, flow_a])

    assert torch.equal(g_ab.x[0], g_ba.x[1])
    assert torch.equal(g_ab.x[1], g_ba.x[0])


def test_feature_dimensions_shape_and_dtype():
    """Test D: Exactly 7 features with valid float32 dtype and finite values."""
    flows = [
        FlowRecord(
            src_ip=f"10.0.0.{i}",
            dst_ip="10.0.0.2",
            dst_port=80,
            packet_count=10 * i + 1,
            byte_count=1000 * i + 100,
            duration_sec=1.0,
            tcp_flags=2,
        )
        for i in range(1, 10)
    ]
    graph = build_pyg_graph(flows)
    assert graph.x.shape == (9, 7)
    assert graph.x.dtype == torch.float32
    assert torch.isfinite(graph.x).all().item()


def test_probability_full_precision_decision_path():
    """Test E (M08-F03): ThreatAnalyzer evaluates full precision scores without rounding artifacts."""
    analyzer = ThreatAnalyzer()
    analyzer.threshold = 0.7500

    # Flow with score just below threshold (0.74996) should NOT trigger alert
    pred_below = {"source_scores": {"10.0.0.99": 0.74996}}
    flows = [
        FlowRecord(
            src_ip="10.0.0.99",
            dst_ip="10.0.0.2",
            dst_port=80,
            packet_count=10,
            byte_count=1000,
            duration_sec=1.0,
            tcp_flags=2,
        )
    ]
    alerts_below, _ = analyzer.evaluate(pred_below, flows)
    assert len(alerts_below) == 0

    # Flow with score at or above threshold (0.75001) SHOULD trigger alert
    pred_above = {"source_scores": {"10.0.0.99": 0.75001}}
    with patch.object(analyzer.healer, "block_ip", return_value={"status": "success", "enforcement_status": "enforced"}), \
         patch.object(analyzer.blockchain, "store_incident", return_value={"status": "success", "tx_hash": "0x123"}):
        alerts_above, _ = analyzer.evaluate(pred_above, flows)
        assert len(alerts_above) == 1
        assert alerts_above[0]["source_ip"] == "10.0.0.99"


def test_degraded_mode_heuristic_fallback():
    """Test F: When ML model is missing/disabled, system falls back safely to heuristic scoring."""
    service = InferenceService()
    service.model = None
    service.mode = "degraded"

    flows = [
        FlowRecord(
            src_ip="10.0.0.99",
            dst_ip="10.0.0.2",
            dst_port=80,
            packet_count=10000,
            byte_count=1000000,
            duration_sec=1.0,
            tcp_flags=2,
        )
    ]
    result = service.predict(flows)
    assert result["mode"] == "degraded"
    assert len(result["flow_scores"]) == 1
    assert result["flow_scores"][0]["score"] >= 0.75


def test_global_stats_fallback_on_missing_file():
    """Test G: Global statistics fall back deterministically if stats file is missing."""
    reset_global_stats_cache()
    with patch.object(settings, "stats_path", "/non/existent/path/stats.pt"):
        mean, std = get_global_stats(torch)
        assert mean.shape == (1, 7)
        assert std.shape == (1, 7)
        assert torch.isfinite(mean).all().item()
        assert torch.isfinite(std).all().item()
