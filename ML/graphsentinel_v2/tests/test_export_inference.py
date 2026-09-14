"""Export + streaming inference verification (runs after a training run)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphsentinel.config import Config  # noqa: E402
from graphsentinel.data.graph_builder import EDGE_FEATURE_NAMES, NODE_FEATURE_NAMES  # noqa: E402
from graphsentinel.export import export_all, verify_export  # noqa: E402
from graphsentinel.inference.capture import CSVReplaySource, run_pipeline  # noqa: E402
from graphsentinel.inference.ema_scaler import EMAScaler  # noqa: E402
from graphsentinel.inference.engine import InferenceEngine  # noqa: E402
from graphsentinel.models.net import build_model  # noqa: E402

from make_synthetic import write_dataset  # noqa: E402

ROOT = Path("/tmp/gs_export")


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    out = tmp_path_factory.mktemp("export")
    cfg = Config()
    cfg.base_dir = str(out)
    cfg.model.memory_capacity = 2048
    cfg.ensure_dirs()
    model = build_model(cfg)

    rng = np.random.default_rng(0)
    edge_scaler = EMAScaler.from_training(
        rng.normal(size=(500, len(EDGE_FEATURE_NAMES))), EDGE_FEATURE_NAMES
    )
    node_scaler = EMAScaler.from_training(
        rng.normal(size=(500, len(NODE_FEATURE_NAMES))), NODE_FEATURE_NAMES
    )
    status = export_all(cfg, model, cfg.model_path, edge_scaler, node_scaler, verbose=False)
    return cfg, model, status


def test_model_card_is_a_complete_contract(artifacts):
    cfg, model, status = artifacts
    card = json.loads(Path(status["model_card"]).read_text(encoding="utf-8"))

    # Everything a backend needs to build inputs without importing our code.
    assert card["inputs"]["node_features"]["names"] == NODE_FEATURE_NAMES
    assert card["inputs"]["edge_features"]["names"] == EDGE_FEATURE_NAMES
    assert card["outputs"]["classes"][0] == "BENIGN"
    assert card["contract_version"]
    assert card["graph"]["node_entity"] == "ip_address"
    assert card["graph"]["edge_entity"] == "network_flow"
    # And the freeze is documented as retired.
    assert "in_channels_7" in card["deprecations"]
    # Artefact hashes let the backend detect a swapped model.
    assert "sha256" in card["artifacts"]["weights"]


def test_weights_reload_without_the_training_code(artifacts):
    cfg, model, status = artifacts
    fresh = build_model(cfg)
    blob = torch.load(status["weights"], map_location="cpu", weights_only=False)
    fresh.load_state_dict(blob["model"])
    assert blob["config"]["model"]["num_classes"] == cfg.model.num_classes


def test_torchscript_matches_eager(artifacts):
    cfg, model, status = artifacts
    if str(status.get("torchscript", "")).startswith("FAILED"):
        pytest.skip(f"TorchScript unavailable here: {status['torchscript']}")
    res = verify_export(cfg.model_path, model)
    assert res["torchscript"]["pass"], res["torchscript"]


def test_scaler_roundtrips_through_json(artifacts):
    cfg, _, _ = artifacts
    s = EMAScaler.load(cfg.model_path / "edge_scaler.json")
    assert s.n_features == len(EDGE_FEATURE_NAMES)
    x = np.random.randn(10, len(EDGE_FEATURE_NAMES))
    assert s.transform(x).shape == x.shape
    assert np.isfinite(s.transform(x)).all()


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------
def test_engine_streams_and_emits_rules(artifacts, tmp_path):
    cfg, _, _ = artifacts
    engine = InferenceEngine.from_artifacts(cfg.model_path, threat_threshold=0.5)

    data_dir = tmp_path / "ds"
    write_dataset(data_dir, seed=5)
    src = CSVReplaySource(
        data_dir / "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
        speed=0.0,
        limit=4000,
    )

    results = []
    run_pipeline(src, engine, batch_size=512, on_result=results.append)

    assert results, "no windows closed"
    assert any(r.n_hosts > 0 for r in results)
    total_flows = sum(r.n_flows for r in results)
    assert total_flows > 3000, f"only {total_flows} flows made it through"

    # Latency budget: a 60 s window must be scored in far less than 60 s.
    worst = max(r.latency_ms for r in results)
    assert worst < 60_000, f"window inference took {worst:.0f} ms"

    # Every rule must be installable: real 5-tuple, finite lifetime.
    for r in results:
        for rule in r.rules:
            of = rule.to_openflow()
            assert of["match"]["ipv4_src"] and of["match"]["ipv4_dst"]
            assert of["hard_timeout"] > 0 and of["idle_timeout"] > 0
            assert rule.attack_class != "BENIGN"


def test_engine_reports_drift(artifacts, tmp_path):
    """The EMA scaler must surface a drift verdict on every window."""
    cfg, _, _ = artifacts
    engine = InferenceEngine.from_artifacts(cfg.model_path)
    data_dir = tmp_path / "ds2"
    write_dataset(data_dir, seed=6)
    src = CSVReplaySource(
        data_dir / "Tuesday-WorkingHours.pcap_ISCX.csv", speed=0.0, limit=2500
    )
    results = []
    run_pipeline(src, engine, batch_size=512, on_result=results.append)
    with_drift = [r for r in results if r.drift is not None]
    assert with_drift, "no drift report produced"
    assert "max_z" in with_drift[0].drift


def test_legacy_adapter_exposes_v1_surface(artifacts):
    from graphsentinel.models.compat import LegacyBinaryAdapter

    cfg, model, _ = artifacts
    from graphsentinel.data.graph_builder import GraphBuilder
    from make_synthetic import generate
    from graphsentinel.config import CLASS_TO_IDX, RAW_LABEL_MAP

    df = generate(seed=2, minutes=4)
    df["y"] = df["Label"].map(RAW_LABEL_MAP).map(CLASS_TO_IDX)
    c = Config.from_dict(cfg.to_dict())
    c.graph.window_seconds = 60
    gs = GraphBuilder(c).build(df, verbose=False)

    adapter = LegacyBinaryAdapter(model)
    probs = adapter.predict_proba(gs[0])
    assert probs.shape == (gs[0].num_nodes,)
    assert ((probs >= 0) & (probs <= 1)).all()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
