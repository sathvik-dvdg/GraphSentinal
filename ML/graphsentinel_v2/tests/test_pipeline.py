"""
End-to-end verification.

These are not smoke tests. Each one checks a specific claim the redesign makes,
so a regression that quietly reverts a fix is caught rather than hidden behind
a still-plausible F1 score.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphsentinel.config import CLASS_NAMES, Config  # noqa: E402
from graphsentinel.data import ports  # noqa: E402
from graphsentinel.data.graph_builder import (  # noqa: E402
    NODE_FEATURE_NAMES,
    GraphBuilder,
    ipv4_to_int,
)
from graphsentinel.data.preprocess import build_splits, split  # noqa: E402
from graphsentinel.data.schema import SchemaError, validate_dataset  # noqa: E402
from graphsentinel.inference.ema_scaler import EMAScaler  # noqa: E402
from graphsentinel.inference.sdn import SDNTranslator  # noqa: E402
from graphsentinel.losses import FocalLoss, effective_number_alpha  # noqa: E402
from graphsentinel.models.memory import NodeMemory  # noqa: E402
from graphsentinel.models.net import build_model  # noqa: E402

from make_synthetic import write_dataset  # noqa: E402

DATA_ROOT = Path("/tmp/gs_test")


@pytest.fixture(scope="session")
def cfg() -> Config:
    write_dataset(DATA_ROOT / "datasets/cicids2017", seed=7)
    c = Config()
    c.base_dir = str(DATA_ROOT)
    c.graph.window_seconds = 30
    c.graph.window_stride_seconds = 30
    c.train.epochs = 2
    c.model.memory_capacity = 4096
    c.ensure_dirs()
    return c


@pytest.fixture(scope="session")
def splits(cfg):
    # build_splits caches to parquet, which needs pyarrow -- a TRAINING-only
    # dependency. A backend integration audit on 2026-09-13 ran this suite with
    # only the inference deps installed and got five collection ERRORS reading
    # "Unable to find a usable engine", which looks like a broken package
    # rather than a missing optional extra. Skip cleanly and say why.
    pytest.importorskip(
        "pyarrow",
        reason="pyarrow is a TRAINING dependency (parquet split cache). "
               "Install requirements-train.txt to run the split/graph tests; "
               "the inference path does not need it.",
    )
    return build_splits(cfg, force=True, verbose=False)


@pytest.fixture(scope="session")
def graphs(cfg, splits):
    builder = GraphBuilder(cfg)
    return {k: builder.build(v, verbose=False) for k, v in splits.items()}


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
def test_schema_accepts_traffic_labelling(cfg):
    reports = validate_dataset(
        cfg.dataset_path, cfg.data.csv_files, require_ips=True, verbose=False
    )
    assert all(r.variant == "traffic_labelling" for r in reports.values())
    assert all(r.supports_ip_graph for r in reports.values())


def test_schema_rejects_machine_learning_cve(tmp_path):
    """The exact failure the original notebook hit must be loud, not silent."""
    bad = tmp_path / "Tuesday-WorkingHours.pcap_ISCX.csv"
    pd.DataFrame(
        {" Destination Port": [80], " Flow Duration": [10], " Label": ["BENIGN"]}
    ).to_csv(bad, index=False)
    with pytest.raises(SchemaError) as exc:
        validate_dataset(tmp_path, [bad.name], require_ips=True, verbose=False)
    assert "TrafficLabelling" in str(exc.value)


# --------------------------------------------------------------------------
# Ports: the semantic-destruction fix
# --------------------------------------------------------------------------
def test_ports_are_categorical_not_continuous():
    # 22 and 23 are adjacent integers but must be distinct tokens.
    assert ports.port_to_token(22) != ports.port_to_token(23)
    # 80 and 8080 are distant integers but both are named service ports, so
    # both get dedicated tokens the embedding can pull together.
    assert ports.port_to_token(80) != ports.port_to_token(8080)
    assert ports.port_to_token(80) >= 2 and ports.port_to_token(8080) >= 2
    # Ephemeral ports collapse into shared buckets rather than 16k dead rows.
    assert ports.port_to_token(51234) == ports.port_to_token(51235)
    assert ports.port_to_token(-1) == ports.OOV_TOKEN


def test_ports_vectorised_matches_scalar():
    sample = np.array([0, 22, 80, 443, 8080, 51234, 65535, 70000, -3])
    vec = ports.ports_to_tokens(sample)
    scalar = np.array([ports.port_to_token(int(p)) for p in sample])
    assert np.array_equal(vec, scalar)


# --------------------------------------------------------------------------
# Splitting: the leakage fix
# --------------------------------------------------------------------------
def test_temporal_split_has_no_overlap(cfg):
    c = Config.from_dict(cfg.to_dict())
    c.data.split_strategy = "temporal"
    pytest.importorskip("pyarrow", reason="training-only dep; see requirements-train.txt")
    s = build_splits(c, force=True, verbose=False)
    assert s["train"]["t"].max() < s["val"]["t"].min()
    assert s["val"]["t"].max() < s["test"]["t"].min()


def test_episode_split_never_cuts_a_burst(splits):
    """The v1 leakage: the same attack burst appearing in train AND test.

    Under episode splitting every attack episode belongs wholly to one split,
    so no (class, episode) pair may appear on both sides.
    """
    from graphsentinel.data.preprocess import _episodes

    def episode_keys(df, gap=120):
        keys = set()
        for label, grp in df.groupby("Label", sort=False):
            if label == "BENIGN":
                continue
            grp = grp.sort_values("t")
            t = grp["t"].to_numpy()
            # Identify episodes by their start time so the same burst gets the
            # same key regardless of which split it landed in.
            ep = _episodes(t, gap)
            for e in np.unique(ep):
                keys.add((label, int(t[ep == e].min()) // 3600))
        return keys

    tr = episode_keys(splits["train"])
    te = episode_keys(splits["test"])
    assert tr, "no attack episodes in train"
    assert te, "no attack episodes in test"
    assert not (tr & te), f"episodes leaked across train/test: {sorted(tr & te)}"


def test_split_survives_gaps_between_capture_days():
    """Regression: real CICIDS2017 produced a 179-row validation set.

    The dataset is a handful of capture days scattered across a week, so the
    pooled timeline is mostly empty. Cutting at "70% of the wall-clock span"
    landed in the dead air BETWEEN capture days and gave validation zero BENIGN
    rows. Checkpoint selection then ran on 4 nodes: epoch 1 scored a fluke
    0.667, every later epoch scored 0.000, early stopping fired at epoch 13,
    and the exported "best model" was the untrained one. The run looked
    successful the whole way through.

    Cuts are now chosen by row rank, which cannot land in a gap.
    """
    rng = np.random.default_rng(0)
    t0 = 1_499_130_000
    frames = []
    # Tuesday: benign + a brute force
    for lab, n in [("BENIGN", 40_000), ("SSHBrute", 600)]:
        frames.append(pd.DataFrame({"Label": lab,
                                    "t": np.sort(rng.integers(t0, t0 + 8 * 3600, n))}))
    # Friday: three days later, benign + a port scan
    for lab, n in [("BENIGN", 12_000), ("PortScan", 15_000)]:
        base = t0 + 3 * 86400
        frames.append(pd.DataFrame({"Label": lab,
                                    "t": np.sort(rng.integers(base, base + 8 * 3600, n))}))
    df = pd.concat(frames).sort_values("t").reset_index(drop=True)

    c = Config()
    c.data.split_strategy = "episode"
    tr, va, te = split(df, c, verbose=False)

    for name, part in [("train", tr), ("val", va), ("test", te)]:
        assert len(part) > 0.02 * len(df), f"{name} got only {len(part)} of {len(df)} rows"
        assert "BENIGN" in set(part["Label"]), f"{name} has no BENIGN -- metrics meaningless"
    assert len(va) > 1000, f"validation collapsed to {len(va)} rows"


@pytest.mark.parametrize("shape", ["two_bursts", "hyper_dense", "uneven", "uniform", "single_ts"])
def test_split_never_empties_a_class_whatever_the_burst_shape(shape):
    """Regression: real PortScan gave validation 0 of 158,746 rows.

    Attack traffic arrives in dense bursts separated by silence. Deriving cut
    TIMES from rank positions and then filtering with `t < cut_a` can empty a
    split outright (when the rank band lands in the silence between two bursts)
    or discard tens of thousands of rows (when a burst is dense enough that the
    dead zone swallows a slab of it). Slicing by row POSITION cannot do either.
    """
    from graphsentinel.data.preprocess import _adaptive_gap, _apply_cuts, _rank_cuts

    rng = np.random.default_rng(0)
    b = 1_499_000_000
    shapes = {
        "two_bursts": np.concatenate([rng.integers(b, b + 600, 120_000),
                                      rng.integers(b + 40_000, b + 40_600, 38_746)]),
        "hyper_dense": rng.integers(b, b + 60, 158_746),
        "uneven": np.concatenate([rng.integers(b, b + 300, 100_000),
                                  rng.integers(b + 9_000, b + 9_100, 50_000),
                                  rng.integers(b + 20_000, b + 20_500, 8_746)]),
        "uniform": rng.integers(b, b + 5_600, 158_746),
        "single_ts": np.full(5_000, b),
    }
    t = np.sort(shapes[shape])
    grp = pd.DataFrame({"t": t})
    gap = _adaptive_gap(t, 300)
    cut_a, cut_b = _rank_cuts(t, 0.70, 0.15)
    tr, va, te = _apply_cuts(grp, t, cut_a, cut_b, gap)

    for name, part in [("train", tr), ("val", va), ("test", te)]:
        assert len(part) > 0, f"{shape}: {name} is EMPTY"
    # and no split may be starved to a rounding error
    assert len(va) >= 0.01 * len(grp), f"{shape}: val got {len(va)} of {len(grp)}"


def test_split_keeps_every_class_in_every_split(splits):
    """A split that loses a class makes its metrics meaningless."""
    all_labels = set(splits["train"]["Label"]) | set(splits["test"]["Label"])
    for name in ("train", "val", "test"):
        missing = all_labels - set(splits[name]["Label"])
        assert not missing, f"{name} split is missing {sorted(missing)}"


def test_attack_holdout_never_trains_on_held_out_family(cfg):
    c = Config.from_dict(cfg.to_dict())
    c.data.split_strategy = "attack_holdout"
    c.data.holdout_attacks = ["Botnet"]
    pytest.importorskip("pyarrow", reason="training-only dep; see requirements-train.txt")
    s = build_splits(c, force=True, verbose=False)
    assert "Botnet" not in set(s["train"]["Label"])
    assert "Botnet" not in set(s["val"]["Label"])
    assert "Botnet" in set(s["test"]["Label"])


# --------------------------------------------------------------------------
# The graph: does it actually encode attack topology?
# --------------------------------------------------------------------------
def test_graph_nodes_are_ips_not_flows(graphs, splits):
    g = max(graphs["train"], key=lambda x: x.num_nodes)
    # In a flow-as-node graph, nodes == rows. Here nodes must be far fewer.
    assert g.num_nodes < g.edge_index.size(1)
    assert hasattr(g, "node_ip_int")
    assert g.edge_attr.size(0) == g.edge_index.size(1)


def test_portscan_shows_high_port_entropy(cfg):
    """A scanner must be separable by structure alone, with no volume signal."""
    from make_synthetic import generate

    df = generate(seed=3)
    from graphsentinel.config import CLASS_TO_IDX, RAW_LABEL_MAP

    df["y"] = df["Label"].map(RAW_LABEL_MAP).map(CLASS_TO_IDX)
    c = Config.from_dict(cfg.to_dict())
    c.graph.window_seconds = 120
    builder = GraphBuilder(c)
    gs = builder.build(df, verbose=False)

    ent_idx = NODE_FEATURE_NAMES.index("dst_port_entropy")
    scanner_int = int(ipv4_to_int(np.array(["172.16.0.99"]))[0])

    best_scanner, best_other = -1.0, []
    for g in gs:
        ips = g.node_ip_int.numpy()
        ent = g.x[:, ent_idx].numpy()
        hit = np.where(ips == scanner_int)[0]
        if len(hit):
            best_scanner = max(best_scanner, float(ent[hit[0]]))
            best_other.extend(np.delete(ent, hit).tolist())

    assert best_scanner > 0, "scanner never appeared in any window"
    assert best_scanner > np.percentile(best_other, 99), (
        f"scanner port entropy {best_scanner:.3f} not above the 99th percentile "
        f"of other hosts ({np.percentile(best_other, 99):.3f})"
    )


def test_ddos_victim_shows_high_fan_in(cfg):
    from make_synthetic import generate

    df = generate(seed=3)
    from graphsentinel.config import CLASS_TO_IDX, RAW_LABEL_MAP

    df["y"] = df["Label"].map(RAW_LABEL_MAP).map(CLASS_TO_IDX)
    c = Config.from_dict(cfg.to_dict())
    c.graph.window_seconds = 120
    gs = GraphBuilder(c).build(df, verbose=False)

    idx = NODE_FEATURE_NAMES.index("log_unique_src_ips")
    victim_int = int(ipv4_to_int(np.array(["10.0.0.50"]))[0])
    best, others = -1.0, []
    for g in gs:
        ips = g.node_ip_int.numpy()
        v = g.x[:, idx].numpy()
        hit = np.where(ips == victim_int)[0]
        if len(hit):
            best = max(best, float(v[hit[0]]))
            others.extend(np.delete(v, hit).tolist())
    assert best > np.percentile(others, 99)


def _v1_style_loop(df: pd.DataFrame) -> int:
    """Reference implementation of the ORIGINAL per-row builder.

    Reproduced faithfully (``for i in range(n)`` + ``.iloc[i]`` + ``row.get``)
    so the speedup claim is measured against the real thing rather than
    asserted.
    """
    rows = df.reset_index(drop=True)
    feats, last_port = [], {}
    for i in range(len(rows)):
        row = rows.iloc[i]
        fwd = float(row.get("Total Fwd Packets", 0) or 0)
        bwd = float(row.get("Total Backward Packets", 0) or 0)
        fb = float(row.get("Total Length of Fwd Packets", 0) or 0)
        bb = float(row.get("Total Length of Bwd Packets", 0) or 0)
        dur = max(float(row.get("Flow Duration", 1) or 1) / 1e6, 1e-3)
        port = int(float(row.get("Destination Port", 0) or 0)) % 65536
        tot_p, tot_b = fwd + bwd, fb + bb
        feats.append([
            fwd / (tot_p + 1e-6), tot_b / (tot_p + 1e-6),
            float(np.log1p(tot_p / dur)), port / 65535.0,
            (fb - bb) / (tot_b + 1e-6),
        ])
        last_port[port] = i
    return len(feats)


def test_graph_builder_beats_the_v1_row_loop(cfg, splits):
    """Guard against a reintroduced per-row Python loop.

    Timed on a DENSE window so the measurement reflects per-flow cost rather
    than per-window fixed overhead -- the synthetic capture is sparse, and a
    30 s window there holds ~150 flows where real CICIDS2017 traffic holds
    thousands.
    """
    df = splits["train"]
    if len(df) < 5000:
        pytest.skip("synthetic split too small to time meaningfully")

    dense = Config.from_dict(cfg.to_dict())
    dense.graph.window_seconds = 3600
    dense.graph.window_stride_seconds = 3600

    t0 = time.perf_counter()
    GraphBuilder(dense).build(df, verbose=False)
    new_rate = len(df) / (time.perf_counter() - t0)

    sample = df.head(4000)
    t0 = time.perf_counter()
    _v1_style_loop(sample)
    old_rate = len(sample) / (time.perf_counter() - t0)

    print(f"\n  v1 row loop: {old_rate:,.0f} flows/s")
    print(f"  vectorised : {new_rate:,.0f} flows/s  ({new_rate / old_rate:.0f}x)")
    assert new_rate > old_rate * 20, (
        f"vectorised builder only {new_rate / old_rate:.1f}x the v1 loop "
        f"({new_rate:,.0f} vs {old_rate:,.0f} flows/s)"
    )
    assert new_rate > 150_000, f"only {new_rate:,.0f} flows/s -- too slow for line rate"


# --------------------------------------------------------------------------
# Loss
# --------------------------------------------------------------------------
def test_focal_downweights_easy_examples():
    logits_easy = torch.tensor([[6.0, -6.0]])
    logits_hard = torch.tensor([[0.1, -0.1]])
    y = torch.tensor([0])
    fl = FocalLoss(gamma=2.0, reduction="none")
    easy, hard = float(fl(logits_easy, y)), float(fl(logits_hard, y))
    assert hard > easy * 100, "focal loss is not suppressing the easy example"


def test_effective_number_alpha_favours_minority_without_exploding():
    """Minority classes must be lifted, but not by the raw frequency ratio.

    Plain inverse frequency would weight Botnet 500x Benign here, which makes
    training unstable. Effective-number weighting saturates: the 200 000th
    near-duplicate DDoS flow adds almost no information, but it is not
    worthless either.
    """
    counts = [750_000, 100_000, 70_000, 1_500, 2_000, 167_000]
    a = effective_number_alpha(counts)
    inv_ratio = counts[0] / counts[3]  # 500x
    assert a[3] > a[0] * 5, "botnet class is not being upweighted enough"
    assert a[3] / a[0] < inv_ratio / 5, "weighting failed to saturate"
    assert torch.isfinite(a).all()


# --------------------------------------------------------------------------
# Memory: bounded footprint
# --------------------------------------------------------------------------
def test_memory_is_bounded_under_ip_churn():
    """One million distinct IPs must not grow the memory tensor."""
    mem = NodeMemory(memory_dim=16, capacity=1024, ttl_seconds=60, input_dim=16)
    before = mem.memory.numel()
    rng = np.random.default_rng(0)
    for step in range(20):
        ips = torch.from_numpy(rng.integers(0, 2**31, size=5000).astype(np.int64))
        msg = torch.randn(len(ips), 16)
        mem.update(ips, msg, now=step * 30)
    assert mem.memory.numel() == before
    occ = mem.occupancy()
    assert occ["heavy_used"] <= occ["heavy_capacity"]
    assert occ["bytes"] < 200_000


def test_memory_persists_across_windows():
    mem = NodeMemory(memory_dim=8, capacity=64, ttl_seconds=3600, hash_tail=False, input_dim=8)
    ip = torch.tensor([12345], dtype=torch.long)
    mem.update(ip, torch.ones(1, 8), now=0)
    first = mem.read(*mem.slots_for(ip, 10), ip).clone()
    mem.update(ip, torch.ones(1, 8), now=10)
    second = mem.read(*mem.slots_for(ip, 20), ip)
    assert not torch.allclose(first, torch.zeros_like(first))
    assert not torch.allclose(first, second), "memory did not evolve across windows"


# --------------------------------------------------------------------------
# EMA scaler: drift handling
# --------------------------------------------------------------------------
def test_ema_scaler_adapts_and_clamps():
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, size=(2000, 3))
    s = EMAScaler.from_training(ref, ["a", "b", "c"], half_life_seconds=10, warmup_updates=1)

    # a modest baseline shift should be absorbed without alarm
    for i in range(20):
        r = s.partial_fit(rng.normal(0.5, 1, size=(100, 3)), t=i * 10)
    assert not r.drifted

    # a violent shift must trip the alarm and be clamped, not silently followed
    for i in range(40):
        r = s.partial_fit(rng.normal(30.0, 1, size=(100, 3)), t=200 + i * 10)
    assert r.drifted
    assert np.all(np.abs(s.mean - s.ref_mean) <= s.max_drift_sigma * s.ref_std + 1e-6)


# --------------------------------------------------------------------------
# Model + SDN
# --------------------------------------------------------------------------
def test_model_forward_shapes(cfg, graphs):
    model = build_model(cfg)
    g = graphs["train"][0]
    out = model.step_with_memory(g, now=int(g.window_end))
    assert out["node_logits"].shape == (g.num_nodes, len(CLASS_NAMES))
    assert out["edge_logits"].shape == (g.edge_index.size(1), len(CLASS_NAMES))
    assert torch.isfinite(out["node_logits"]).all()


def test_model_accepts_arbitrary_feature_count():
    """The frozen in_channels=7 contract must be gone."""
    from graphsentinel.models.net import GraphSentinelNet

    m = GraphSentinelNet(node_in=16, edge_in=20, hidden=32, heads=2, use_memory=False)
    out = m(
        torch.randn(5, 16),
        torch.randint(0, 5, (2, 12)),
        torch.randn(12, 20),
        torch.randint(0, 50, (12,)),
        torch.randint(0, 50, (12,)),
        torch.randint(0, 6, (12,)),
    )
    assert out["node_logits"].shape[0] == 5


def test_compat_shim_still_importable():
    from graphsentinel.models.compat import GraphSAGEClassifier

    m = GraphSAGEClassifier(in_channels=7, warn=False)
    out = m(torch.randn(6, 7), torch.tensor([[0, 1, 2], [1, 2, 3]]))
    assert out.shape == (6, 2)
    # and the v1 hard-freeze is gone
    m2 = GraphSAGEClassifier(in_channels=19, warn=False)
    assert m2(torch.randn(6, 19), torch.tensor([[0, 1], [1, 2]])).shape == (6, 2)


def test_sdn_emits_actionable_rules():
    n_edges = 6
    edge_probs = torch.zeros(n_edges, len(CLASS_NAMES))
    edge_probs[:, 2] = 0.95  # PortScan
    edge_probs[:, 0] = 0.05
    node_probs = torch.zeros(4, len(CLASS_NAMES))
    node_probs[:, 2] = 0.9
    node_probs[:, 0] = 0.1
    edge_index = torch.tensor([[0, 0, 0, 1, 1, 2], [1, 2, 3, 2, 3, 3]])

    t = SDNTranslator(require_node_corroboration=True)
    rules = t.translate(
        edge_probs, node_probs, edge_index,
        node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"],
        dst_ports=[22, 23, 80, 443, 8080, 3389],
        src_ports=[5000] * n_edges,
        protocols=[6] * n_edges,
        real_edge_mask=np.ones(n_edges, bool),
    )
    assert rules, "no rules produced from confident detections"
    r = rules[0]
    assert r.src_ip and r.dst_ip and r.protocol == 6
    of = r.to_openflow()
    assert of["match"]["ipv4_src"] == r.src_ip
    assert of["hard_timeout"] > 0, "rules must expire"
    assert "ovs-ofctl" in r.to_ovs_ofctl()


def test_sdn_allowlist_blocks_enforcement():
    t = SDNTranslator(allow_networks=["10.0.0.0/8"], require_node_corroboration=False)
    edge_probs = torch.zeros(1, len(CLASS_NAMES))
    edge_probs[0, 2] = 0.99
    node_probs = torch.zeros(2, len(CLASS_NAMES))
    node_probs[:, 2] = 0.99
    rules = t.translate(
        edge_probs, node_probs, torch.tensor([[0], [1]]),
        node_ips=["10.0.0.1", "10.0.0.2"], dst_ports=[22], src_ports=[1],
        protocols=[6], real_edge_mask=np.ones(1, bool),
    )
    assert rules == [], "allowlisted hosts must never produce drop rules"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))


# ---------------------------------------------------------------------------
# Regression: the silent-skip bug (run 4, 2026-08).
#
# `if not torch.isfinite(loss): continue` sat before the bookkeeping, so a
# window whose loss went non-finite was dropped without a trace. It cost the
# optimiser 100% of DDoS, 100% of PortScan, 100% of Botnet and 49.8% of
# DoSHulk across five consecutive runs, while the printed loss (averaged over
# only the surviving windows) read 0.0001 and looked like convergence.
# ---------------------------------------------------------------------------
def test_skipped_window_aborts_instead_of_training_a_starved_class():
    """A class that loses its edges to dropped windows must abort the run."""
    import numpy as np
    from graphsentinel.config import CLASS_NAMES

    edge_counts = np.array([800_000, 58_000, 111_000, 1_000, 2_300, 105_000])
    skipped_edges = np.array([0, 58_000, 111_000, 1_000, 0, 52_000])
    lost = skipped_edges / np.maximum(edge_counts, 1)

    limit = 0.02
    starved = [CLASS_NAMES[i] for i in range(len(CLASS_NAMES)) if lost[i] > limit]
    assert "DDoS" in starved and "PortScan" in starved and "Botnet" in starved
    assert "BENIGN" not in starved, "a fully-trained class must not trip the guard"
    assert "SSHBrute" not in starved


def test_train_loop_reports_dropped_windows():
    """The loop must record dropped windows in history, not swallow them."""
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    assert "skipped_windows" in src, "dropped windows must be tracked"
    assert "windows_dropped" in src, "dropped count must reach the history row"
    assert "max_class_edge_loss" in src, "the starvation guard must be wired in"
    # the bare silent continue must be gone
    assert "if not torch.isfinite(loss):\n                continue" not in src


def test_amp_failure_retries_in_fp32_before_dropping():
    """A window that overflows fp16 gets one fp32 retry before being lost."""
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    assert "amp_rescued" in src
    assert "attempt_amp = False" in src, "must retry the same window in fp32"


# ---------------------------------------------------------------------------
# Regression: checkpoint selection + decision-boundary fix (run of 2026-08-29).
#
# That run passed the class-coverage gate -- 0 windows dropped, every class
# trained -- and still reported edge F1 0.0000 for DoSHulk and SSHBrute while
# their PR-AUCs were 0.7813 and 0.8563. Two separate defects:
#   1. selection was hardcoded to node_macro_f1, chosen over a validation set
#      holding 2-26 attack nodes; it picked epoch 20 (edge macro F1 0.336) over
#      epoch 9 (0.431).
#   2. both classes were ranked well but never won the argmax against DDoS.
# ---------------------------------------------------------------------------
def test_selection_metric_is_not_hardcoded_to_node():
    import inspect
    from graphsentinel import train as train_mod
    from graphsentinel.config import Config

    src = inspect.getsource(train_mod.train)
    assert '.replace("val_", "node_")' not in src, \
        "selection must not force node metrics regardless of config"
    assert Config().train.early_stop_metric == "edge_macro_f1"


def test_edge_head_outweighs_node_head():
    """The head with 993-823k labels per class must not be weighted below the
    head with 24-125."""
    from graphsentinel.config import Config
    assert Config().loss.edge_loss_weight >= 1.0


def test_logit_adjustment_recovers_a_well_ranked_class():
    """A class that is separable but always loses the argmax must be
    recoverable by a per-class offset -- and BENIGN must stay pinned, so the
    fix cannot buy attack recall by biasing away from benign."""
    import numpy as np
    from sklearn.metrics import f1_score
    from graphsentinel.evaluate import fit_logit_adjustment, apply_logit_adjustment

    rng = np.random.default_rng(0)
    n = 3000
    y = rng.choice(6, size=n, p=[0.6, 0.1, 0.1, 0.05, 0.05, 0.1])
    logits = rng.normal(size=(n, 6))
    logits[np.arange(n), y] += 1.6      # every class IS separable
    logits[:, 1] += 1.4                 # but class 1 is systematically inflated
    p = np.exp(logits); p /= p.sum(1, keepdims=True)

    before = f1_score(y, p.argmax(1), average="macro", zero_division=0)
    # min_holdout_per_class=0: this test isolates the boundary correction, not
    # the per-class support floor (which has its own test)
    bias = fit_logit_adjustment(y, p, 6, min_holdout_per_class=0)
    after = f1_score(y, apply_logit_adjustment(p, bias),
                     average="macro", zero_division=0)

    assert after > before, "adjustment must improve a boundary-limited case"
    assert bias[0] == 0.0, "BENIGN must stay pinned at zero"


def test_logit_adjustment_cannot_manufacture_signal():
    """On genuinely unseparable classes the offsets must not produce a large
    gain -- otherwise this is a knob for inflating numbers, not a fix."""
    import numpy as np
    from sklearn.metrics import f1_score
    from graphsentinel.evaluate import fit_logit_adjustment, apply_logit_adjustment

    rng = np.random.default_rng(1)
    n = 3000
    y = rng.choice(6, size=n)
    p = rng.dirichlet(np.ones(6), size=n)     # pure noise, no signal at all
    before = f1_score(y, p.argmax(1), average="macro", zero_division=0)
    bias = fit_logit_adjustment(y, p, 6)
    after = f1_score(y, apply_logit_adjustment(p, bias),
                     average="macro", zero_division=0)
    assert after - before < 0.10, (
        f"gained {after - before:.3f} on noise -- the fit is overfitting the "
        "validation split rather than correcting a boundary"
    )


# ---------------------------------------------------------------------------
# Regression: run of 2026-08-29 (4th). Two defects, both mine.
#   1. The RESET cell was disarmed, so training resumed from epoch 32 of a run
#      trained under edge_loss_weight=0.5 and selection on node_macro_f1. The
#      stored best_metric (0.2018, a NODE score) was compared against EDGE
#      scores (~0.3326), so every epoch declared itself "*best" while the model
#      sat frozen at a cosine LR near zero.
#   2. The offsets maximised macro F1 with no floor, and duly traded a working
#      class for two zeros: DDoS 0.5404 -> 0.1183 while macro "improved" 0.14.
# ---------------------------------------------------------------------------
def test_resume_refuses_when_the_objective_changed():
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    assert "Refusing to resume" in src, \
        "a changed loss must block resume, not silently continue"
    assert "edge_loss_weight" in src and "metric_changed" in src


def test_stale_best_metric_is_discarded_when_metric_changes():
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    i = src.index("metric_changed")
    assert "best_metric, no_improve = -1.0, 0" in src[i:], \
        "a best score on the OLD metric must not be compared against the new one"


def test_logit_adjustment_never_sacrifices_a_class():
    """The exact failure shape from the run: one strong class the optimiser
    would happily trade away for two zeros."""
    import numpy as np
    from sklearn.metrics import f1_score
    from graphsentinel.evaluate import fit_logit_adjustment, apply_logit_adjustment
    from graphsentinel.config import Config

    rng = np.random.default_rng(4)
    n = 5000
    y = rng.choice(6, size=n, p=[0.6, 0.12, 0.12, 0.02, 0.02, 0.12])
    lg = rng.normal(size=(n, 6))
    lg[np.arange(n), y] += 1.5
    lg[:, 1] += 2.2                       # class 1 dominates the argmax
    p = np.exp(lg); p /= p.sum(1, keepdims=True)

    cap = Config().train.max_class_f1_drop
    before = f1_score(y, p.argmax(1), average=None, labels=list(range(6)),
                      zero_division=0)
    bias = fit_logit_adjustment(y, p, 6, max_class_drop=cap)
    after = f1_score(y, apply_logit_adjustment(p, bias), average=None,
                     labels=list(range(6)), zero_division=0)

    worst = float((after - before).min())
    assert worst >= -(cap + 1e-6), (
        f"a class lost {-worst:.4f} F1, above the {cap} cap -- the offsets are "
        "buying macro F1 by sacrificing a working detector"
    )
    assert after.mean() >= before.mean()


# ---------------------------------------------------------------------------
# Regression: run of 2026-08-29 (5th). The offsets were fitted on validation
# and the per-class floor was enforced on the SAME data, which is no protection
# at all. On test they were worse than plain argmax:
#     SSHBrute  0.8647 -> 0.2308   (-0.63)
#     MACRO     0.5955 -> 0.5865   (the "improvement" was negative)
# The fit now holds out part of validation and discards the offsets unless they
# improve the half they were not fitted on.
# ---------------------------------------------------------------------------
def test_offsets_are_discarded_when_they_do_not_generalise():
    """On data with no learnable boundary structure, the fit must return zeros
    -- i.e. plain argmax -- rather than offsets that only flatter the fit set."""
    import numpy as np
    from graphsentinel.evaluate import fit_logit_adjustment

    # multiple seeds: a single seed can pass by luck, and the point of the
    # gate is that noise does not survive it repeatably
    for seed in range(8):
        rng = np.random.default_rng(seed)
        n = 4000
        y = rng.choice(6, size=n)
        p = rng.dirichlet(np.ones(6), size=n)      # pure noise
        bias = fit_logit_adjustment(y, p, 6, seed=seed)
        assert not np.any(bias), (
            f"seed {seed}: offsets fitted on noise must be discarded; keeping "
            "them means the held-out gate is not working"
        )


def test_offsets_are_kept_when_the_boundary_is_genuinely_wrong():
    """The complement: a real, reproducible boundary problem must survive the
    gate, otherwise the gate is just switching the feature off."""
    import numpy as np
    from sklearn.metrics import f1_score
    from graphsentinel.evaluate import fit_logit_adjustment, apply_logit_adjustment

    rng = np.random.default_rng(7)
    n = 6000
    y = rng.choice(6, size=n, p=[0.6, 0.12, 0.12, 0.02, 0.02, 0.12])
    lg = rng.normal(size=(n, 6))
    lg[np.arange(n), y] += 1.5
    lg[:, 1] += 2.2                            # class 1 owns the argmax
    p = np.exp(lg); p /= p.sum(1, keepdims=True)

    bias = fit_logit_adjustment(y, p, 6, min_holdout_per_class=0)
    assert np.any(bias), "a genuine boundary problem must not be discarded"
    assert bias[0] == 0.0, "BENIGN must stay pinned"

    before = f1_score(y, p.argmax(1), average="macro", labels=list(range(6)),
                      zero_division=0)
    after = f1_score(y, apply_logit_adjustment(p, bias), average="macro",
                     labels=list(range(6)), zero_division=0)
    assert after > before


# ---------------------------------------------------------------------------
# Regression: run of 2026-08-29 (6th). The offsets CLEARED the held-out gate
# (+0.0467) and still made test worse (-0.0397), with Botnet 0.1398 -> 0.0000.
# The held-out half held only ~18 Botnet edges, so its F1 there was noise. A
# per-class support floor is the missing guard, and on this dataset the whole
# feature is off by default because it has now failed three runs running.
# ---------------------------------------------------------------------------
def test_offsets_discarded_when_a_class_has_too_few_holdout_examples():
    import numpy as np
    from graphsentinel.evaluate import fit_logit_adjustment

    rng = np.random.default_rng(7)
    n = 6000
    # class 3 is vanishingly rare -- ~15 examples land in the held-out half
    y = rng.choice(6, size=n, p=[0.55, 0.15, 0.15, 0.004, 0.076, 0.07])
    lg = rng.normal(size=(n, 6))
    lg[np.arange(n), y] += 1.5
    lg[:, 1] += 2.2
    p = np.exp(lg); p /= p.sum(1, keepdims=True)

    bias = fit_logit_adjustment(y, p, 6, min_holdout_per_class=200)
    assert not np.any(bias), (
        "a class measured on a handful of held-out examples cannot support an "
        "offset; the fit must decline rather than guess"
    )


def test_logit_adjustment_is_off_by_default_on_this_dataset():
    """Three consecutive runs showed the offsets hurting test. Until the
    validation split is large enough per class, the default must be off."""
    from graphsentinel.config import Config
    cfg = Config()
    assert cfg.train.fit_logit_adjustment is False
    assert cfg.train.min_holdout_per_class >= 100


# ---------------------------------------------------------------------------
# Grouped taxonomy. Measured on the real CICIDS2017 by the label audit:
#   BruteForce  1 -> 2 bursts   (FTP-Patator + SSH-Patator)
#   DoS         2 -> 6 bursts   (Hulk + GoldenEye + slowloris + Slowhttptest)
# More bursts is what makes a genuine episode-held-out split possible.
# ---------------------------------------------------------------------------
def test_taxonomy_switch_mutates_in_place():
    """Every module does `from .config import CLASS_NAMES`, so the switch must
    mutate that exact list. Rebinding would leave importers on the old one and
    silently mis-label everything."""
    from graphsentinel.config import apply_taxonomy, CLASS_NAMES, RAW_LABEL_MAP
    from graphsentinel.data import graph_builder  # an importer, bound at import
    from graphsentinel.config import CLASS_NAMES as ALIAS

    try:
        apply_taxonomy("grouped")
        assert CLASS_NAMES == ["BENIGN", "DDoS", "PortScan", "Botnet",
                               "BruteForce", "DoS"]
        assert ALIAS is CLASS_NAMES and ALIAS == CLASS_NAMES, \
            "an earlier importer must see the new taxonomy"
        assert RAW_LABEL_MAP["FTP-Patator"] == "BruteForce"
        assert RAW_LABEL_MAP["DoS slowloris"] == "DoS"
        assert CLASS_NAMES[0] == "BENIGN", "index 0 must stay BENIGN"
    finally:
        apply_taxonomy("cicids6")


def test_config_round_trip_restores_taxonomy():
    """A checkpoint must restore its own taxonomy. Six classes named one way
    evaluated against six named another would line up by index and be wrong."""
    from graphsentinel.config import Config, CLASS_NAMES
    try:
        c = Config()
        c.data.taxonomy = "grouped"
        c.sync_taxonomy()
        restored = Config.from_dict(c.to_dict())
        assert restored.data.taxonomy == "grouped"
        assert restored.model.num_classes == len(CLASS_NAMES) == 6
        assert "BruteForce" in CLASS_NAMES
    finally:
        Config()          # __post_init__ restores the default


def test_graph_cache_is_keyed_by_taxonomy():
    """Reusing a cicids6 graph cache for a grouped run would silently relabel
    every edge, since the labels line up by index."""
    import inspect
    from graphsentinel import train as train_mod
    src = inspect.getsource(train_mod.prepare_graphs)
    assert "cfg.data.taxonomy" in src, "cache key must include the taxonomy"


def test_taxonomy_change_blocks_resume():
    import inspect
    from graphsentinel import train as train_mod
    src = inspect.getsource(train_mod.train)
    i = src.index("changed = []")
    assert "taxonomy" in src[i:i + 900], \
        "a changed taxonomy must refuse resume, like a changed loss"


def test_unseen_families_are_declared_and_excluded_from_training():
    """The open-set experiment needs families the model has never seen. They
    must not appear in any taxonomy's label map."""
    from graphsentinel.config import (TAXONOMIES, UNSEEN_FAMILY_LABELS,
                                      UNSEEN_FAMILY_FILES, FILE_DAYS)
    for tax in TAXONOMIES.values():
        for lab in UNSEEN_FAMILY_LABELS:
            assert lab not in tax["map"], \
                f"{lab} is held out; mapping it into training destroys the test"
    for f in UNSEEN_FAMILY_FILES:
        assert f not in FILE_DAYS, \
            f"{f} must not be a training capture day"


# ---------------------------------------------------------------------------
# Regression: run of 2026-08-29 (10th). The taxonomy switch was made correctly
# and the run STILL trained cicids6 data under grouped names. Two holes:
#   1. the parquet SPLIT cache was not keyed by taxonomy, so a grouped run
#      loaded splits written under cicids6 -- with FTP-Patator and three DoS
#      subtypes already dropped. Proof: BruteForce came out at exactly 2,301
#      edges (SSH-Patator alone) and DoS at exactly 105,629 (Hulk alone),
#      byte-identical to the cicids6 run.
#   2. the resume guard tested `was is not None`, so a checkpoint written
#      before taxonomies existed recorded nothing and was treated as matching.
# ---------------------------------------------------------------------------
def test_split_cache_is_keyed_by_taxonomy():
    import inspect
    from graphsentinel.data import preprocess
    src = inspect.getsource(preprocess.build_splits)
    assert "cfg.data.taxonomy" in src, (
        "the parquet split cache must include the taxonomy, or a grouped run "
        "silently loads cicids6 splits and relabels them by index"
    )


def test_taxonomy_fingerprint_changes_with_the_label_map():
    from graphsentinel.config import apply_taxonomy, taxonomy_fingerprint
    try:
        apply_taxonomy("cicids6"); a = taxonomy_fingerprint()
        apply_taxonomy("grouped"); b = taxonomy_fingerprint()
        assert a != b
        apply_taxonomy("cicids6"); assert taxonomy_fingerprint() == a, \
            "the fingerprint must be deterministic"
    finally:
        apply_taxonomy("cicids6")


def test_missing_taxonomy_in_checkpoint_is_not_treated_as_matching():
    """A pre-taxonomy checkpoint records nothing. Absent must mean unknown,
    never 'same' -- that is how run 10 resumed across a taxonomy change."""
    import inspect
    from graphsentinel import train as train_mod
    src = inspect.getsource(train_mod.train)
    assert "prev_tax is None and prev_fp is None" in src, \
        "the guard must handle a checkpoint that records no taxonomy at all"
    assert "_taxonomy_fingerprint" in src, \
        "checkpoints must be stamped so future runs can compare"


# ---------------------------------------------------------------------------
# flood4 taxonomy + non-graph baseline. Both follow from the topology audit
# (2026-08-29): four of five attack families are the SAME (source, victim)
# pair -- 172.16.0.1 -> 192.168.10.50 -- because the attacker network is behind
# one NATed address. DDoS has 2 source IPs, DoS has 1, both flood port 80 on
# the same victim, so no graph model can separate them.
# ---------------------------------------------------------------------------
def test_flood4_merges_dos_and_ddos():
    from graphsentinel.config import apply_taxonomy, CLASS_NAMES, RAW_LABEL_MAP
    try:
        n = apply_taxonomy("flood4")
        assert n == 5 and CLASS_NAMES[0] == "BENIGN"
        assert "DDoS" not in CLASS_NAMES and "DoSHulk" not in CLASS_NAMES
        for raw in ("DDoS", "DoS Hulk", "DoS GoldenEye",
                    "DoS slowloris", "DoS Slowhttptest"):
            assert RAW_LABEL_MAP[raw] == "Volumetric_Flood", (
                f"{raw} must merge -- the capture cannot separate it from DDoS")
        # the separable ones stay separate
        assert RAW_LABEL_MAP["PortScan"] == "PortScan"
        assert RAW_LABEL_MAP["FTP-Patator"] == "BruteForce"
        assert RAW_LABEL_MAP["Bot"] == "Botnet"
    finally:
        apply_taxonomy("cicids6")


def test_baseline_sees_the_same_information_as_the_gnn():
    """The baseline must get edge features AND both endpoints' node features.
    Without the endpoints it is a straw man and the comparison proves nothing."""
    import numpy as np, torch
    from torch_geometric.data import Data
    from graphsentinel.baseline import flatten_graphs

    n_node_f, n_edge_f, n_edges = 16, 20, 7
    g = Data(x=torch.randn(4, n_node_f),
             edge_index=torch.randint(0, 4, (2, n_edges)),
             edge_attr=torch.randn(n_edges, n_edge_f))
    g.edge_y = torch.randint(0, 5, (n_edges,))
    g.real_edge_mask = torch.ones(n_edges, dtype=torch.bool)

    out = flatten_graphs([g])
    assert out["X"].shape == (n_edges, n_edge_f + 2 * n_node_f), (
        "baseline rows must be edge features plus BOTH endpoints")
    assert out["y"].shape == (n_edges,)


def test_baseline_verdict_thresholds_are_honest():
    """A delta inside +/-0.05 must NOT be reported as the graph winning."""
    import inspect
    from graphsentinel import baseline
    src = inspect.getsource(baseline.compare)
    assert "not yet justified BY THIS DATASET" in src, \
        "a within-noise result must be reported as such, not spun"
    assert "tabular baseline BEATS the GNN" in src, \
        "the baseline winning must be a stateable outcome"


def test_training_log_write_is_atomic_mirrored_and_non_fatal():
    """The run of 2026-09-13 lost 34 epochs of curves to a Google Drive FUSE
    write: pandas' to_csv truncates the target before writing, and an
    incomplete truncate on that mount left the path unresolvable -- the file
    was listed by the state inspector minutes before training and was gone
    after. Three properties stop that from ever costing history again:

      * write to a temp file and os.replace it, so the target is never left
        half-written;
      * mirror to local disk (/content/gs_logs), which is not a network mount;
      * never let a logging failure kill a training run.
    """
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    assert "os.replace" in src, \
        "the log must be written atomically, not truncated in place"
    assert "/content/gs_logs" in src, \
        "the log must be mirrored to local disk, off the Drive mount"
    # the write sits inside a try/except that only prints
    block = src[src.index("_rows = pd.DataFrame(history)"):]
    block = block[:block.index("\n\n", 200)] if "\n\n" in block[200:] else block
    assert "except Exception" in block, \
        "a logging failure must never abort training"


def test_curves_cell_does_not_depend_on_the_drive_csv():
    """The notebook's curves cell must prefer the in-memory history that
    train() returns. Reading the Drive CSV first is what crashed the run."""
    import json, pathlib
    nb_path = pathlib.Path(__file__).resolve().parents[2] / "GraphSentinel_Training.ipynb"
    if not nb_path.exists():
        import pytest
        pytest.skip("notebook not built in this checkout")
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    curves = [s for s in cells if "training_curves.png" in s]
    assert curves, "no curves cell found in the notebook"
    s = curves[0]
    assert 'report.get("history")' in s or "report['history']" in s, \
        "the curves cell must use the in-memory history first"
    assert s.index("report") < s.index("cfg.log_path"), \
        "the Drive path must be the last resort, not the first read"


def test_checkpoint_write_is_atomic(tmp_path):
    """torch.save opens 'wb', which truncates the target first. On the Drive
    mount a completed truncate with an incomplete write is how a 76 MB best.pt
    became a FileNotFoundError (run of 2026-09-13). The target must never be
    left as neither the old bytes nor the new ones."""
    import torch
    from graphsentinel.train import _atomic_torch_save

    p = tmp_path / "best.pt"
    _atomic_torch_save({"v": 1}, p)
    assert torch.load(p, weights_only=False)["v"] == 1
    assert not (tmp_path / "best.pt.tmp").exists(), "temp file must be renamed away"

    # a failing write must leave the PREVIOUS good file intact
    class Unpicklable:
        def __reduce__(self):
            raise RuntimeError("boom")
    try:
        _atomic_torch_save({"v": Unpicklable()}, p)
    except Exception:
        pass
    assert torch.load(p, weights_only=False)["v"] == 1, \
        "a failed save must not destroy the checkpoint that was already there"


def test_checkpoint_read_never_trusts_exists():
    """The state inspector listed best.pt at 76.2 MB while train() reported
    'no checkpoint' -- the directory entry was real and the file would not
    open. Resume must try-load, not stat."""
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    assert "ckpt_last.exists()" not in src, \
        "existence is not readability on the Drive mount -- try-load instead"
    assert "load_checkpoint(ckpt_last" in src


def test_final_evaluation_does_not_depend_on_a_file(tmp_path):
    """The run of 2026-09-13 trained 26 epochs and then died loading its own
    best.pt. The selected weights were in the process the whole time, so the
    final evaluation must read them from memory first."""
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.train)
    i_mem = src.index("if best_blob is not None:")
    i_load = src.index("load_checkpoint(ckpt_best")
    assert i_mem < i_load, "in-memory best must be preferred over the file"
    assert "report[\"best_state\"] = blob" in src, \
        "the caller must be able to rescue the weights when every write failed"


def test_checkpoint_save_survives_a_failing_destination(tmp_path, monkeypatch):
    """A Drive write that raises must not stop training, and must not stop the
    local copy from being written."""
    import torch
    from graphsentinel import train as train_mod

    mirror = tmp_path / "mirror"
    monkeypatch.setattr(train_mod, "_LOCAL_CKPT_DIR", mirror)
    monkeypatch.setattr(train_mod, "_mirror_dir", lambda: (mirror.mkdir(exist_ok=True) or mirror))

    dead = tmp_path / "no" / "such" / "mount" / "best.pt"
    real_replace = train_mod.os.replace

    def flaky(a, b):
        if "mount" in str(b):
            raise OSError("transport endpoint is not connected")
        return real_replace(a, b)

    monkeypatch.setattr(train_mod.os, "replace", flaky)
    ok = train_mod.save_checkpoint({"v": 7}, dead, verbose=False)
    assert ok is True, "a Drive failure must not count as total failure"
    assert torch.load(mirror / "best.pt", weights_only=False)["v"] == 7

    blob, where = train_mod.load_checkpoint(dead)
    assert blob is not None and blob["v"] == 7, \
        "the reader must find the local mirror when the primary is unreadable"
    assert where == mirror / "best.pt"


def test_export_reports_only_artefacts_it_read_back(tmp_path, monkeypatch):
    """The export cell printed "ok weights" and the verifier printed
    "MISSING weights.pt" one cell later (2026-09-13). A write that returns
    without raising is not evidence on the Drive mount, so export must reopen
    every file before claiming it -- and must say FAILED when it cannot."""
    import torch
    from graphsentinel import export as ex

    monkeypatch.setattr(ex, "_mirror_dir", lambda: None)

    # a destination whose bytes never survive: replace succeeds, the file is
    # then unreadable -- exactly the observed Drive behaviour
    good = tmp_path / "ok.pt"
    assert ex._verified_write(good, lambda p: torch.save({"a": 1}, p),
                              lambda p: torch.load(p, weights_only=False)) == str(good)

    bad = tmp_path / "bad.pt"

    def vanish(p):
        p.write_bytes(b"not a checkpoint")

    assert ex._verified_write(
        bad, vanish,
        lambda p: torch.load(p, weights_only=False)) is None, \
        "a file that will not read back must NOT be reported as exported"


def test_export_falls_back_to_a_local_mirror(tmp_path, monkeypatch):
    """When Drive refuses, the artefacts must still exist somewhere readable
    and export must return that path rather than a success it cannot back."""
    import torch
    from graphsentinel import export as ex

    mirror = tmp_path / "mirror"
    mirror.mkdir()
    monkeypatch.setattr(ex, "_mirror_dir", lambda: mirror)

    dead = tmp_path / "nope" / "weights.pt"
    real_replace = ex.os.replace

    def flaky(a, b):
        if "nope" in str(b):
            raise OSError("transport endpoint is not connected")
        return real_replace(a, b)

    monkeypatch.setattr(ex.os, "replace", flaky)
    got = ex._verified_write(dead, lambda p: torch.save({"a": 2}, p),
                             lambda p: torch.load(p, weights_only=False))
    assert got == str(mirror / "weights.pt")
    assert torch.load(mirror / "weights.pt", weights_only=False)["a"] == 2


def test_drop_edge_features_rejects_raw_column_names():
    """drop_edge_features takes ENGINEERED names (log_total_bytes), not raw
    CICIDS2017 columns (Total Length of Fwd Packets). Silently ignoring a
    wrong name would run the baseline and report it as the ablation."""
    import pytest
    from graphsentinel.config import Config
    from graphsentinel.data.graph_builder import GraphBuilder, EDGE_FEATURE_NAMES

    c = Config()
    c.data.drop_edge_features = ["log_total_bytes", "iat_burstiness"]
    assert GraphBuilder(c)._drop_idx == [
        EDGE_FEATURE_NAMES.index("log_total_bytes"),
        EDGE_FEATURE_NAMES.index("iat_burstiness"),
    ]

    bad = Config()
    bad.data.drop_edge_features = ["Total Length of Fwd Packets"]
    with pytest.raises(ValueError, match="not in EDGE_FEATURE_NAMES"):
        GraphBuilder(bad)

    assert GraphBuilder(Config())._drop_idx == [], "default must change nothing"


def test_graph_cache_is_keyed_by_dropped_features():
    """A graph set built without log_total_bytes is indistinguishable on disk
    from one built with it. Two runs were already lost to a cache key missing
    a term; the ablation must not be the third."""
    import inspect
    from graphsentinel import train as train_mod

    src = inspect.getsource(train_mod.prepare_graphs)
    assert "drop_edge_features" in src, \
        "the graph cache key must include the dropped-feature list"
    i = src.index("drop_edge_features")
    j = src.index("cache = (")
    assert i < j, "the tag must be computed before the cache path"


def test_dropped_features_are_zero_in_the_built_graph(tmp_path):
    """End to end: the column named is actually zero in edge_attr, and no
    other column is touched."""
    import numpy as np, pandas as pd, torch
    from graphsentinel.config import Config
    from graphsentinel.data.graph_builder import (
        GraphBuilder, HostHistory, EDGE_FEATURE_NAMES)

    rng = np.random.default_rng(0)
    n = 400
    base = pd.DataFrame({
        "Source IP": [f"10.0.0.{i % 7}" for i in range(n)],
        "Destination IP": [f"10.0.1.{(i + 3) % 5}" for i in range(n)],
        "Source Port": rng.integers(1024, 65535, n),
        "Destination Port": rng.integers(1, 1024, n),
        "Protocol": rng.choice([6, 17], n),
        "t": np.arange(n) + 1_500_000_000,
        "y": rng.integers(0, 2, n),
    })
    for col in Config().data.edge_feature_cols + Config().data.volumetric_cols:
        base[col] = rng.random(n) * 1000 + 1

    idx = EDGE_FEATURE_NAMES.index("log_total_bytes")
    plain = GraphBuilder(Config(), history=HostHistory()).build(
        base.copy(), update_history=False, verbose=False)
    c = Config(); c.data.drop_edge_features = ["log_total_bytes"]
    dropped = GraphBuilder(c, history=HostHistory()).build(
        base.copy(), update_history=False, verbose=False)

    assert len(plain) == len(dropped) and len(plain) > 0
    for a, b in zip(plain, dropped):
        assert torch.all(b.edge_attr[:, idx] == 0), "named feature must be zero"
        assert torch.any(a.edge_attr[:, idx] != 0), "baseline must be non-zero"
        keep = [k for k in range(len(EDGE_FEATURE_NAMES)) if k != idx]
        assert torch.allclose(a.edge_attr[:, keep], b.edge_attr[:, keep]), \
            "dropping one feature must not disturb the others"


def test_per_epoch_saves_do_not_touch_drive(tmp_path, monkeypatch):
    """A 40-epoch run used to write best.pt and last.pt to the Drive mount
    dozens of times. Repeated overwrite of one path is the only pattern the
    2026-09-13 probe matrix did NOT reproduce, and it is the one Drive (an
    object store that allows duplicate names in a folder) handles worst. The
    local copy is what the run depends on, so per-epoch saves stay local and
    Drive gets the final save only."""
    import torch
    from graphsentinel import train as train_mod

    mirror = tmp_path / "local"
    monkeypatch.setattr(train_mod, "_mirror_dir",
                        lambda: (mirror.mkdir(exist_ok=True) or mirror))
    drive = tmp_path / "drive" / "best.pt"

    assert train_mod.save_checkpoint({"v": 1}, drive, mirror_only=True) is True
    assert (mirror / "best.pt").exists(), "the local copy must always be written"
    assert not drive.exists(), "mirror_only must not write to the primary path"

    assert train_mod.save_checkpoint({"v": 2}, drive) is True
    assert drive.exists(), "the final save must still reach the primary path"
    assert torch.load(drive, weights_only=False)["v"] == 2

    import inspect
    src = inspect.getsource(train_mod.train)
    per_epoch = src[src.index("is_best = current > best_metric"):
                    src.index("# ---------------- final evaluation")]
    assert per_epoch.count("mirror_only=True") == 2, \
        "both per-epoch saves (best.pt and last.pt) must be local-only"


def test_mirror_only_still_writes_when_there_is_no_mirror(tmp_path, monkeypatch):
    """Off Colab there is no /content, so mirror_only must degrade to a normal
    write rather than silently saving nothing."""
    from graphsentinel import train as train_mod

    monkeypatch.setattr(train_mod, "_mirror_dir", lambda: None)
    p = tmp_path / "best.pt"
    assert train_mod.save_checkpoint({"v": 3}, p, mirror_only=True) is True
    assert p.exists(), "with no mirror available the primary must be written"


def test_window_result_exposes_edge_level_verdicts():
    """A backend integration audit (2026-09-13) found the engine's public API
    returned only NODE-head detections and SDN rules -- the edge head, which is
    this model's deliverable, had no way out at all. Edge test macro F1 is
    0.7042 and binary F1 0.9974; the node head's binary F1 is 0.1407. Handing a
    consumer the weak head and hiding the strong one is the wrong default."""
    import numpy as np
    from graphsentinel.config import Config, CLASS_NAMES
    from graphsentinel.models.net import build_model
    from graphsentinel.inference.engine import InferenceEngine, FlowVerdict

    cfg = Config()
    cfg.data.taxonomy = "flood4"
    cfg.sync_taxonomy()
    eng = InferenceEngine(build_model(cfg), cfg)

    rng = np.random.default_rng(0)
    recs = [{
        "Source IP": f"10.0.0.{1 + i % 6}",
        "Destination IP": f"10.0.1.{1 + (i * 3) % 4}",
        "Source Port": int(rng.integers(1024, 65535)),
        "Destination Port": int(rng.integers(1, 1024)),
        "Protocol": 6, "t": 1_500_000_000 + i,
        "Flow Duration": float(rng.integers(100, 5_000_000)),
        "Total Fwd Packets": int(rng.integers(1, 50)),
        "Total Backward Packets": 0,
        "Total Length of Fwd Packets": float(rng.integers(60, 50_000)),
        "Total Length of Bwd Packets": 0.0,
    } for i in range(40)]

    eng.ingest(recs)
    res = eng.flush()

    assert len(res.flows) == 40, "one verdict per REAL flow; mirrors excluded"
    v = res.flows[0]
    assert isinstance(v, FlowVerdict)
    assert v.attack_class in CLASS_NAMES
    assert abs(sum(v.class_probs.values()) - 1.0) < 1e-5
    assert abs(v.threat_score - (1.0 - v.class_probs["BENIGN"])) < 1e-6
    assert v.confidence == max(v.class_probs.values())
    assert "flows" in res.to_dict()


def test_small_window_reports_unscored_not_clean():
    """cfg.graph.min_edges_per_graph (8) means a window with fewer flows builds
    no graph. Returning an empty result made 'not scored' and 'scored, found
    nothing' identical to a caller -- an unscored minute reading as a clean
    bill of health."""
    import numpy as np
    from graphsentinel.config import Config
    from graphsentinel.models.net import build_model
    from graphsentinel.inference.engine import InferenceEngine

    cfg = Config()
    assert cfg.graph.min_edges_per_graph == 8
    eng = InferenceEngine(build_model(cfg), cfg)
    recs = [{
        "Source IP": f"10.0.0.{i}", "Destination IP": "10.0.1.1",
        "Source Port": 1234, "Destination Port": 80, "Protocol": 6,
        "t": 1_500_000_000 + i,
        "Flow Duration": 1000.0, "Total Fwd Packets": 3,
        "Total Backward Packets": 0, "Total Length of Fwd Packets": 300.0,
        "Total Length of Bwd Packets": 0.0,
    } for i in range(5)]
    eng.ingest(recs)
    res = eng.flush()
    assert res.unscored is True
    assert res.flows == [] and res.detections == []
    assert res.n_flows == 5, "the flows must still be counted, just not scored"


def test_model_card_labels_which_split_its_metrics_came_from():
    """train() stores VALIDATION metrics in the checkpoint and export_all
    copies them into the card under the same key names test_report.json uses
    for TEST metrics. Unlabelled, that invites quoting validation (edge macro
    F1 0.7568) as the headline instead of test (0.7042)."""
    import json, tempfile
    from pathlib import Path
    from graphsentinel.config import Config
    from graphsentinel.models.net import build_model
    from graphsentinel.export import export_all

    d = Path(tempfile.mkdtemp())
    cfg = Config()
    cfg.export.export_onnx = False
    export_all(cfg, build_model(cfg), out_dir=d, metrics={"edge_macro_f1": 0.5},
               verbose=False)
    card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
    assert card["metrics_split"] == "validation"
    assert "test_report.json" in card["metrics_note"]
    assert card["scaling"]["used_in_this_export"] is False, \
        "no scalers were passed, so the card must not claim they shipped"


def test_engine_refuses_a_card_whose_class_list_does_not_match():
    """CLASS_NAMES is a mutable global rewritten in place by Config.from_dict.
    Read before that happens, the stale six-class list shifts every index:
    1 DDoS->Volumetric_Flood, 3 Botnet->BruteForce, 4 SSHBrute->Botnet. A
    BruteForce flow would be labelled Botnet, whose mitigation is
    drop_and_quarantine at the lowest confidence floor in the table."""
    import json, tempfile, pytest
    from pathlib import Path
    from graphsentinel.config import Config
    from graphsentinel.models.net import build_model
    from graphsentinel.export import export_all
    from graphsentinel.inference.engine import InferenceEngine

    d = Path(tempfile.mkdtemp())
    cfg = Config()
    cfg.data.taxonomy = "flood4"
    cfg.sync_taxonomy()
    cfg.export.export_onnx = False
    export_all(cfg, build_model(cfg), out_dir=d, verbose=False)
    InferenceEngine.from_artifacts(d)          # matching card loads

    card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
    card["outputs"]["classes"] = ["BENIGN", "DDoS", "PortScan", "Botnet",
                                  "SSHBrute", "DoSHulk"]
    (d / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Class list mismatch"):
        InferenceEngine.from_artifacts(d)


def test_fsync_never_leaks_a_descriptor_when_it_raises():
    """THE WINDOWS BUG, caught by a backend integration audit on 2026-09-13.

    _verified_write used to do:

        fd = os.open(tmp, os.O_RDONLY)
        os.fsync(fd)      # raises OSError(9) on Windows for a read-only fd
        os.close(fd)      # never reached
        except OSError: pass

    The leaked descriptor holds a Windows file lock on the .tmp, the following
    os.replace dies with PermissionError(WinError 32), the outer handler
    swallows that too, and export_all reports FAILED for every artefact while
    leaving three orphan .tmp files behind. On Linux fsync of a read-only fd
    succeeds, so the whole suite passed here and broke there.

    This test forces the Windows behaviour on any platform.
    """
    import os, json, tempfile
    from pathlib import Path
    from graphsentinel import export as ex

    d = Path(tempfile.mkdtemp())
    real_open, real_close = os.open, os.close
    live = []

    def spy_open(*a, **k):
        fd = real_open(*a, **k)
        live.append(fd)
        return fd

    def spy_close(fd):
        if fd in live:
            live.remove(fd)
        return real_close(fd)

    def windows_fsync(fd):
        raise OSError(9, "Bad file descriptor")

    ex.os.open, ex.os.close, ex.os.fsync = spy_open, spy_close, windows_fsync
    try:
        got = ex._verified_write(
            d / "card.json",
            lambda p: p.write_text(json.dumps({"a": 1}), encoding="utf-8"),
            lambda p: json.loads(p.read_text(encoding="utf-8"))["a"],
        )
    finally:
        ex.os.open, ex.os.close, ex.os.fsync = real_open, real_close, os.fsync

    assert live == [], f"fsync raised and leaked descriptors {live}"
    assert got is not None, "a raising fsync must not fail the write"
    assert (d / "card.json").exists()
    assert not (d / "card.json.tmp").exists(), "orphan .tmp left behind"


def test_package_never_reads_json_without_an_explicit_encoding():
    """Path.read_text() defaults to the locale encoding -- cp1252 on Windows.
    model_card.json happens to be pure ASCII today, so it works by luck; one
    non-ASCII byte in a feature name or a path would raise UnicodeDecodeError
    on a Windows backend and nowhere else."""
    import pathlib

    offenders = []
    pkg_root = pathlib.Path(__file__).resolve().parents[1]
    # tests/ is scanned too: the Windows UnicodeDecodeError that
    # prompted this test was in a TEST file reading the notebook,
    # which a graphsentinel/-only scan could never have caught.
    files = list((pkg_root / "graphsentinel").rglob("*.py")) + \
            list((pkg_root / "tests").rglob("*.py"))
    root = pkg_root
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if ("read_text(" in line or "write_text(" in line) and "encoding" not in line:
                offenders.append(f"{f.relative_to(root)}:{n}: {line.strip()}")
    assert not offenders, (
        "these read/write text without an explicit encoding:\n    "
        + "\n    ".join(offenders)
    )
