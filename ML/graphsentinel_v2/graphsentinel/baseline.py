"""
Non-graph baseline: the experiment that decides whether the GNN earns its place.

WHY THIS IS NOT OPTIONAL, AND WHY IT MATTERS MORE AFTER THE TOPOLOGY AUDIT.

Measured on CICIDS2017 (2026-08-29):

    class        flows     src IPs  dst IPs  dst ports   top source
    DDoS       128,027        2        2         4       172.16.0.1
    DoS        252,661        1        1         1       172.16.0.1
    PortScan   158,930        1        1     1,000       172.16.0.1
    BruteForce  13,835        1        1         3       172.16.0.1
    Botnet       1,966        8        8       706       205.174.165.73

Four of the five attack families are the SAME (source, victim) pair --
172.16.0.1 -> 192.168.10.50 -- because the attacker network sits behind one
NATed address. As a graph, those four attacks are one edge pair wearing four
labels. The information that separates them (destination-port spread, flag
mix, packet sizes) lives on the FLOW, not in the topology.

So the obvious question a reviewer will ask is: does the graph contribute
anything at all here, or would a row-by-row classifier on the same features do
just as well? This module answers it with a number instead of an argument.

It is deliberately generous to the baseline: the same split, the same edge
features, and the node features of BOTH endpoints appended -- so the tabular
model sees everything the GNN sees about a flow and its two hosts, minus the
message passing. If it matches the GNN, the message passing is not earning its
latency and the honest write-up says so.
"""
from __future__ import annotations

import time
from typing import Dict, List

import numpy as np

from .config import CLASS_NAMES, Config


def flatten_graphs(graphs: List) -> Dict[str, np.ndarray]:
    """One row per real edge: edge features + both endpoints' node features.

    The endpoint features are what make this a FAIR baseline rather than a
    straw man. Without them the comparison would only prove that a flow row
    carries less than a flow row plus its hosts, which nobody doubts.
    """
    X, y = [], []
    for g in graphs:
        m = g.real_edge_mask.numpy()
        ei = g.edge_index.numpy()[:, m]
        ea = g.edge_attr.numpy()[m]
        nx = g.x.numpy()
        X.append(np.concatenate([ea, nx[ei[0]], nx[ei[1]]], axis=1))
        y.append(g.edge_y.numpy()[m])
    if not X:
        return {"X": np.zeros((0, 0)), "y": np.zeros(0, dtype=np.int64)}
    return {"X": np.concatenate(X).astype(np.float32),
            "y": np.concatenate(y).astype(np.int64)}


def run_baseline(
    cfg: Config,
    graphs: Dict[str, List],
    n_estimators: int = 200,
    max_depth: int = 24,
    verbose: bool = True,
) -> dict:
    """Random Forest on flattened flows. Returns metrics in the same shape as
    the GNN's, so the two are directly comparable."""
    from sklearn.ensemble import RandomForestClassifier
    from .evaluate import multiclass_metrics

    tr = flatten_graphs(graphs["train"])
    te = flatten_graphs(graphs["test"])
    if not len(tr["y"]):
        raise RuntimeError("no training edges to flatten")

    if verbose:
        print(f"  baseline input: {tr['X'].shape[1]} features "
              f"({tr['X'].shape[1] - 2 * graphs['train'][0].x.shape[1]} edge + "
              f"2 x {graphs['train'][0].x.shape[1]} node)")
        print(f"  train rows {len(tr['y']):,} | test rows {len(te['y']):,}")

    # class_weight="balanced_subsample" is the tabular analogue of the focal
    # loss the GNN uses -- without it the comparison would be unfair in the
    # GNN's favour, which is the wrong direction for a baseline.
    clf = RandomForestClassifier(
        n_estimators=n_estimators, max_depth=max_depth,
        class_weight="balanced_subsample", n_jobs=-1,
        random_state=cfg.train.seed,
    )
    t0 = time.time()
    clf.fit(tr["X"], tr["y"])
    fit_s = time.time() - t0

    t0 = time.time()
    prob = clf.predict_proba(te["X"])
    pred_s = time.time() - t0

    # predict_proba only has columns for classes seen in training
    full = np.zeros((len(te["y"]), len(CLASS_NAMES)), dtype=np.float64)
    for j, c in enumerate(clf.classes_):
        full[:, int(c)] = prob[:, j]

    metrics = multiclass_metrics(te["y"], full.argmax(1), full, "edge_")
    out = {
        "metrics": metrics,
        "fit_seconds": fit_s,
        "predict_seconds": pred_s,
        "n_features": int(tr["X"].shape[1]),
        "feature_importance": clf.feature_importances_.tolist(),
    }

    if verbose:
        print(f"  fitted in {fit_s:.1f}s, predicted {len(te['y']):,} rows "
              f"in {pred_s:.1f}s")
        print(f"\n  {'class':<18s}{'baseline edge F1':>18s}")
        for c in CLASS_NAMES:
            print(f"  {c:<18s}{metrics.get(f'edge_f1_{c}', float('nan')):>18.4f}")
        print(f"  {'MACRO':<18s}{metrics.get('edge_macro_f1', 0):>18.4f}")
    return out


def compare(gnn_metrics: dict, base: dict, verbose: bool = True) -> dict:
    """Side-by-side, with the verdict stated rather than left to the reader."""
    bm = base["metrics"]
    rows = []
    for c in CLASS_NAMES:
        k = f"edge_f1_{c}"
        rows.append((c, gnn_metrics.get(k, float("nan")), bm.get(k, float("nan"))))
    g = gnn_metrics.get("edge_macro_f1", float("nan"))
    b = bm.get("edge_macro_f1", float("nan"))

    if verbose:
        print("\n" + "=" * 74)
        print("  GNN vs NON-GRAPH BASELINE  (same split, same features)")
        print("=" * 74)
        print(f"  {'class':<18s}{'GNN':>10s}{'RandomForest':>15s}{'delta':>10s}")
        for c, a, bb in rows:
            print(f"  {c:<18s}{a:>10.4f}{bb:>15.4f}{a - bb:>+10.4f}")
        print(f"  {'MACRO':<18s}{g:>10.4f}{b:>15.4f}{g - b:>+10.4f}")
        print()
        if not np.isfinite(g - b):
            print("  incomparable -- one side is missing metrics")
        elif g - b > 0.05:
            print(f"  >> The graph adds {g - b:+.4f} macro F1 over a tabular model")
            print("     with the same information. Message passing is earning its")
            print("     place, and this table is the evidence to show a reviewer.")
        elif g - b > -0.05:
            print(f"  >> The graph adds {g - b:+.4f} -- within noise of the tabular")
            print("     baseline. On this capture four of five attack families are")
            print("     the same (source, victim) pair, so there is little topology")
            print("     for message passing to exploit. Report this honestly: the")
            print("     GNN is not yet justified BY THIS DATASET, which is a")
            print("     statement about CICIDS2017, not about graph learning.")
        else:
            print(f"  >> The tabular baseline BEATS the GNN by {b - g:.4f}. Do not")
            print("     report the GNN as the contribution. Either find where the")
            print("     graph helps (per-class deltas above) or change the data.")
    return {"gnn_macro": g, "baseline_macro": b, "delta": g - b,
            "per_class": rows}
