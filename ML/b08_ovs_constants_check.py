"""Audit B08: what do the three features OVS cannot supply cost the v1 model?

The v1 GraphSAGE model reads seven features per flow. Open vSwitch flow dumps
carry no direction split and no TCP flags, so on live traffic three of them are
constants: fwd_ratio = 1.0, byte_asymmetry = +1.0, syn_ratio = 0.

This scores the committed labelled sample twice with the installed v1 weights
and the backend's own feature builder and scaling:

  offline  -- direction and SYN columns as the training notebook used them
  ovs      -- the same rows with the three features forced to the OVS constants

Everything else is identical, so the difference is the cost of those constants.

LIMITS. The v1 training and test sets are not in the repository; this is the
v2 sample (ML/testdata/cicids2017_sample.csv), a small contiguous slice that is
90.8% benign and may overlap v1's training rows. Read the deltas, not the
absolute scores. Windows are 500 consecutive rows, as in training; the live
path scores whatever one poll returns (audit B25), which this does not model.

Run from the repository root:  python ML/b08_ovs_constants_check.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
os.environ.setdefault("SQLITE_PATH", str(Path(tempfile.gettempdir()) / "b08_check.db"))
os.chdir(REPO / "backend")
sys.path.insert(0, str(REPO / "backend"))

import pandas as pd  # noqa: E402

from app.services.graph_builder import build_pyg_graph  # noqa: E402
from app.services.inference_service import InferenceService  # noqa: E402

SAMPLE = REPO / "ML" / "testdata" / "cicids2017_sample.csv"
OUT = REPO / "ML" / "b08_ovs_constants.json"
WINDOW = 500
THRESHOLDS = (0.40, 0.50, 0.75)  # backend/.env on the dev machine, argmax, tracked default


def flows_from(df: pd.DataFrame, ovs: bool) -> list[dict]:
    out = []
    for row in df.itertuples(index=False):
        fwd_p, bwd_p, fwd_b, bwd_b, dur_us, port, syn, rate, src, dst = row
        rate = float(rate) if pd.notna(rate) and rate not in (float("inf"),) else 0.0
        flow = {
            "src_ip": str(src),
            "dst_ip": str(dst),
            "dst_port": int(port) % 65536,
            "duration_sec": max(float(dur_us) / 1e6, 1e-3),
            "flow_bytes_per_s": max(rate, 0.0),
        }
        if ovs:  # one counter per flow, no direction, no flags
            flow.update(fwd_packets=fwd_p + bwd_p, bwd_packets=0.0,
                        fwd_bytes=fwd_b + bwd_b, bwd_bytes=0.0, syn_flag_count=0.0)
        else:
            flow.update(fwd_packets=fwd_p, bwd_packets=bwd_p,
                        fwd_bytes=fwd_b, bwd_bytes=bwd_b, syn_flag_count=syn)
        out.append(flow)
    return out


def score(model, torch, flows: list[dict]) -> list[float]:
    scores: list[float] = []
    for start in range(0, len(flows), WINDOW):
        graph = build_pyg_graph(flows[start:start + WINDOW])
        with torch.no_grad():
            scores.extend(float(v) for v in model.predict_proba(graph.x, graph.edge_index).tolist())
    return scores


def metrics(scores, labels, sources, threshold) -> dict:
    pred = [s >= threshold for s in scores]
    tp = sum(p and y for p, y in zip(pred, labels))
    fp = sum(p and not y for p, y in zip(pred, labels))
    fn = sum((not p) and y for p, y in zip(pred, labels))
    tn = len(labels) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    # What the backend acts on: per batch, a source whose highest flow score
    # reaches the threshold is blocked.
    blocked = benign_blocked = 0
    for start in range(0, len(scores), WINDOW):
        best: dict[str, float] = {}
        attacker: dict[str, bool] = {}
        for s, y, src in zip(scores[start:start + WINDOW], labels[start:start + WINDOW], sources[start:start + WINDOW]):
            best[src] = max(best.get(src, 0.0), s)
            attacker[src] = attacker.get(src, False) or y
        for src, s in best.items():
            if s >= threshold:
                blocked += 1
                benign_blocked += not attacker[src]
    return {
        "accuracy": round((tp + tn) / len(labels), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sources_over_threshold": blocked,
        "of_which_sent_no_attack_flow": benign_blocked,
    }


def main() -> None:
    inference = InferenceService.get_instance()
    if inference.model is None:
        raise SystemExit(f"v1 model not loaded: {inference.degraded_reason}")
    cols = [" Total Fwd Packets", " Total Backward Packets", "Total Length of Fwd Packets",
            " Total Length of Bwd Packets", " Flow Duration", " Destination Port", " SYN Flag Count",
            "Flow Bytes/s", " Source IP", " Destination IP"]
    df = pd.read_csv(SAMPLE, low_memory=False)
    labels = [lab.strip() != "BENIGN" for lab in df[" Label"]]
    classes = [lab.strip() for lab in df[" Label"]]
    sources = [str(s) for s in df[" Source IP"]]

    result = {
        "sample": str(SAMPLE.relative_to(REPO)).replace("\\", "/"),
        "rows": len(df), "attack_rows": sum(labels), "window": WINDOW,
        "weights": str(Path(inference.weights_path).name),
        "conditions": {},
    }
    scored = {}
    for name, ovs in (("offline", False), ("ovs_constants", True)):
        scored[name] = score(inference.model, inference.torch, flows_from(df[cols], ovs))
        result["conditions"][name] = {
            f"threshold_{t:.2f}": metrics(scored[name], labels, sources, t) for t in THRESHOLDS
        }
        by_class = {}
        for cls in sorted(set(classes)):
            vals = [s for s, c in zip(scored[name], classes) if c == cls]
            by_class[cls] = {"n": len(vals), "mean_score": round(sum(vals) / len(vals), 4),
                             "share_over_0.75": round(sum(v >= 0.75 for v in vals) / len(vals), 4)}
        result["conditions"][name]["by_class"] = by_class
    flipped = sum((a >= 0.75) != (b >= 0.75) for a, b in zip(scored["offline"], scored["ovs_constants"]))
    result["flows_whose_0.75_decision_changes"] = flipped
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
