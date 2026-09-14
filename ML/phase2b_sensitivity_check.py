"""
Can PHASE 2b's sample detect edge-feature damage at all?

WHY THIS EXISTS. `phase2b_live_path_cost.py` reported every delta as +0.0000 on
ML/testdata/cicids2017_sample.csv. A zero has two very different readings:

  * the live path genuinely costs nothing, or
  * the measurement cannot move on this sample, whatever the damage.

Those are told apart by a control that CAN fail. This script:

  1. confirms the degradation reaches the model (edge features change, and
     edge probabilities move), so a zero is not a no-op bug;
  2. zeroes ALL 20 edge features -- far more damage than the live path does --
     and counts how many predictions change. If none do, the sample is
     separable without edge features, and 2b's zero says nothing about the
     live path;
  3. reports, per class, how confident the model is on predictions it gets
     RIGHT, against the SDN floors in backend/app/services/mitigation_policy.py.

It invents nothing: real rows, real weights, and the same preprocessing steps
as phase2b_live_path_cost.py. The digest of every input is written with the
results.

Run from the repo root:
    python ML/phase2b_sensitivity_check.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ML" / "graphsentinel_v2"))

SAMPLE = REPO / "ML" / "testdata" / "cicids2017_sample.csv"
MODEL_DIR = REPO / "ML"
OUT = REPO / "ML" / "phase2b_sensitivity.json"

PINNED_ONE = ["fwd_packet_ratio", "byte_asymmetry"]
ZEROED = ["log_max_fwd_len", "log_max_bwd_len", "syn_ratio", "rst_ratio",
          "ack_ratio", "psh_ratio", "log_iat_mean", "iat_burstiness"]
CONFIDENCE_FLOORS = [0.80, 0.85, 0.90]

if not SAMPLE.exists():
    raise SystemExit(f"missing {SAMPLE} -- this check needs the real slice and substitutes nothing.")

from graphsentinel.config import CLASS_NAMES, CLASS_TO_IDX, Config  # noqa: E402
from graphsentinel.data import preprocess as pre  # noqa: E402
from graphsentinel.data.graph_builder import EDGE_FEATURE_NAMES, GraphBuilder, HostHistory  # noqa: E402
from graphsentinel.models.net import build_model  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


card = json.loads((MODEL_DIR / "model_card.json").read_text(encoding="utf-8"))
cfg = Config.from_dict(card["config"])
assert list(CLASS_NAMES) == list(card["outputs"]["classes"]), "class list drift"
assert list(EDGE_FEATURE_NAMES) == list(card["inputs"]["edge_features"]["names"])
model = build_model(cfg)
_state = torch.load(MODEL_DIR / "weights.pt", map_location="cpu", weights_only=False)
model.load_state_dict(_state["model"] if "model" in _state else _state)
model.eval()
PIN_IDX = [EDGE_FEATURE_NAMES.index(n) for n in PINNED_ONE]
ZERO_IDX = [EDGE_FEATURE_NAMES.index(n) for n in ZEROED]

# Same preprocessing steps as phase2b_live_path_cost.py.
raw = pd.read_csv(SAMPLE, low_memory=False, encoding="latin-1", on_bad_lines="skip")
raw.columns = [str(c).strip() for c in raw.columns]
n_rows_in_file = len(raw)
raw["Label"] = raw["Label"].astype(str).str.strip().map(pre.RAW_LABEL_MAP)
raw = raw[raw["Label"].notna()].copy()
raw["Timestamp"] = pre._parse_timestamps(raw["Timestamp"])
raw = raw[raw["Timestamp"].notna()].sort_values("Timestamp", kind="mergesort")
raw["t"] = raw["Timestamp"].to_numpy(dtype="datetime64[s]").astype("int64")
raw = pre.clean(raw, cfg, verbose=False)
raw["y"] = raw["Label"].map(CLASS_TO_IDX).astype("int64")
raw = pre.clip_outliers(raw, cfg, cfg.data.edge_feature_cols + cfg.data.volumetric_cols)
raw = raw.reset_index(drop=True)

graphs = GraphBuilder(cfg, history=HostHistory(capacity=cfg.model.memory_capacity)).build(
    raw.copy(), update_history=True, verbose=False)
if not graphs:
    raise SystemExit("no graphs built -- every window is below min_edges_per_graph")


def score(mode: str):
    """mode: 'baseline' | 'live_path' (pin 2, zero 8) | 'all_zero' (zero all 20)."""
    model.reset_memory()
    probs, ys, feats = [], [], []
    with torch.no_grad():
        for g in graphs:
            h = g.clone()
            h.edge_attr = h.edge_attr.clone()
            if mode == "live_path":
                h.edge_attr[:, PIN_IDX] = 1.0
                h.edge_attr[:, ZERO_IDX] = 0.0
            elif mode == "all_zero":
                h.edge_attr = torch.zeros_like(h.edge_attr)
            m = h.real_edge_mask
            probs.append(model.predict(h, now=int(h.window_end))["edge_probs"][m].numpy())
            ys.append(h.edge_y[m].numpy())
            feats.append(h.edge_attr[m].numpy())
    return np.vstack(probs), np.concatenate(ys), np.vstack(feats)


p0, y, f0 = score("baseline")
p1, _, f1 = score("live_path")
pz, _, _ = score("all_zero")
arg0 = p0.argmax(1)


def comparison(p_other: np.ndarray, f_other: np.ndarray | None) -> dict:
    out = {
        "argmax_changed": int((arg0 != p_other.argmax(1)).sum()),
        "max_abs_delta_prob": float(np.abs(p0 - p_other).max()),
        "per_class_recall": {},
    }
    if f_other is not None:
        out["edges_with_changed_features_share"] = float((np.abs(f0 - f_other).sum(1) > 0).mean())
    for k, c in enumerate(CLASS_NAMES):
        mk = y == k
        if mk.any():
            out["per_class_recall"][c] = {
                "baseline": float((arg0[mk] == k).mean()),
                "variant": float((p_other[mk].argmax(1) == k).mean()),
            }
    return out


confidence = {}
for k, c in enumerate(CLASS_NAMES):
    correct = (y == k) & (arg0 == k)
    entry = {"true_edges": int((y == k).sum()), "correct": int(correct.sum())}
    if correct.any():
        s = p0[correct, k]
        q = np.quantile(s, [0.05, 0.5, 0.95])
        entry.update({
            "p05": float(q[0]), "p50": float(q[1]), "p95": float(q[2]), "max": float(s.max()),
            "share_at_or_above": {f"{t:.2f}": float((s >= t).mean()) for t in CONFIDENCE_FLOORS},
        })
    confidence[c] = entry

result = {
    "note": ("Sensitivity control for phase2b_live_path_cost.py on the same sample. If "
             "all_zero_edge_features.argmax_changed is 0, the sample is separable without "
             "edge features and phase2b's deltas cannot measure edge-feature damage."),
    "inputs": {
        "sample": {"path": "ML/testdata/cicids2017_sample.csv", "sha256": sha256(SAMPLE),
                   "rows_in_file": n_rows_in_file, "rows_after_preprocessing": int(len(raw))},
        "model_card_sha256": sha256(MODEL_DIR / "model_card.json"),
        "weights_sha256": sha256(MODEL_DIR / "weights.pt"),
    },
    "windows": len(graphs),
    "real_edges": int(len(y)),
    "live_path_degradation": comparison(p1, f1),
    "all_zero_edge_features": comparison(pz, None),
    "baseline_confidence_of_correct_predictions": confidence,
}
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")

d, z = result["live_path_degradation"], result["all_zero_edge_features"]
print(f"windows {result['windows']} | real edges {result['real_edges']:,}")
print(f"live-path degradation: features changed on {d['edges_with_changed_features_share']:.1%} of edges, "
      f"max |dP| {d['max_abs_delta_prob']:.3f}, argmax changed on {d['argmax_changed']:,}")
print(f"ALL 20 edge features zeroed: max |dP| {z['max_abs_delta_prob']:.3f}, "
      f"argmax changed on {z['argmax_changed']:,} of {result['real_edges']:,}")
print("confidence of correct predictions:")
for c, e in confidence.items():
    if "p50" in e:
        shares = "  ".join(f">={t}: {v:.1%}" for t, v in e["share_at_or_above"].items())
        print(f"  {c:<18s} correct {e['correct']:>6,}  p05 {e['p05']:.4f}  p50 {e['p50']:.4f}  "
              f"p95 {e['p95']:.4f}  max {e['max']:.4f}  {shares}")
    else:
        print(f"  {c:<18s} correct {e['correct']:>6,}  (of {e['true_edges']:,} true edges)")
print(f"saved -> {OUT}")
