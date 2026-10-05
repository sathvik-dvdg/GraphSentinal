# ============================================================================
#  SPLIT COMPOSITION AND GATE CONFIDENCE
#
#  Run by colab_runner's split_composition stage. Expects `cfg` (the retrain config, fix on)
#  in globals; writes
#  split_composition.json to GS_OUT.
#
#  PART A: what each split contains, under BOTH parses. No model.
#    The episode protocol cuts every class by row rank on its own, and BENIGN by
#    rank over the pooled timeline; graphs are then built per split from that
#    split's rows only. So whether an attack flow shares its 60 s window with
#    benign traffic depends on which BENIGN rows the pooled cut gave that split,
#    and the clock fix moves that cut (the BENIGN tail was Friday morning under
#    the old parse and is Friday afternoon under the fix). This part measures,
#    per split and class: the source files, the time range, the share of attack
#    flows whose window holds >= 1 BENIGN flow of the same split, and the share
#    in windows with enough flows to become a graph at all.
#
#  PART B: the post-fix model's confidence, per (true class, predicted class),
#    on validation and test, against the SDN floors. Answers whether
#    Volumetric_Flood ever reaches 0.90, and how many WRONG-class rules (e.g.
#    PortScan scored as BruteForce) would clear their class's floor.
#
#  Read-only: trains nothing, overwrites no checkpoint or cache.
# ============================================================================
import contextlib, copy, io, json, time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from graphsentinel.config import CLASS_NAMES, Config
from graphsentinel.data import preprocess as pre
from graphsentinel.models.net import build_model
from graphsentinel.train import load_checkpoint, prepare_graphs
from colab_runner import boundary_sharing, split_composition   # tested in test_colab_runner.py

assert "cfg" in dir(), "needs cfg"
OUT = Path(globals().get("GS_OUT", "/content/gs_logs")); OUT.mkdir(parents=True, exist_ok=True)
BAR = "=" * 78
W = int(cfg.graph.window_seconds)
MIN_EDGES = int(cfg.graph.min_edges_per_graph)
#: The floors in backend/app/services/mitigation_policy.py at the time of this
#: run. Botnet is alert-only (1.01, unreachable).
POLICY_FLOORS = {"Volumetric_Flood": 0.90, "PortScan": 0.85, "BruteForce": 0.85, "Botnet": 1.01}
QS = (0.05, 0.25, 0.50, 0.75, 0.95)


# ------------------------------------------------------- the prediction -----
# Written into the code on 2026-10-04, before the first run, so that Part A is
# a test and not a narrative. Printed first; recorded in the JSON as given.
PREDICTION = (
    "If the mechanism holds (the clock fix moved the pooled BENIGN cut, so "
    "pre-fix test attack windows were nearly pure attack and post-fix ones are "
    "mixed), the pre-fix share of test attack flows sharing a window with "
    "benign traffic is LOW and the post-fix share is SUBSTANTIALLY HIGHER. If "
    "both shares are similar, the mechanism is wrong and the drop needs another "
    "explanation.")
print(f"\n{BAR}\n  PREDICTION, RECORDED BEFORE THE MEASUREMENT\n{BAR}")
print("  " + PREDICTION)

# ------------------------------------------------------------- PART A -------
print(f"\n{BAR}\n  PART A -- WHAT EACH SPLIT CONTAINS, UNDER BOTH PARSES\n{BAR}")
part_a = {}
for fix in (False, True):
    c = copy.deepcopy(cfg)
    c.data.fix_12h_clock = fix
    tag = "fixed_parse" if fix else "old_parse"
    t0 = time.time()
    df = pre.load_raw(c, verbose=False)
    if fix:
        # Timestamp resolution per training file: is it minute-only? (the
        # argument that a cut can fall inside one timestamp rests on it)
        sec = df["t"].to_numpy() % 60
        part_a["_resolution"] = {
            str(f): {"rows": int(m.sum()),
                     "rows_off_the_minute": int((sec[m] != 0).sum()),
                     "distinct_second_values": int(len(set(sec[m].tolist())))}
            for f in sorted(df["source_file"].unique())
            for m in [df["source_file"].to_numpy() == f]}
    df = pre.clean(df, c, verbose=False)
    cleaned = df["Label"].astype(str).value_counts().to_dict()
    # The split's own episode lines, captured so they are committed rather than
    # left in a console: per class, episodes found and what the splitter did.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        parts = pre.split(df, c, verbose=True)
    splits = dict(zip(("train", "val", "test"), parts))
    del df
    part_a[tag] = {name: split_composition(p, W, MIN_EDGES)
                   for name, p in splits.items()}
    # Rows the split's dead zone removed (_apply_cuts, split_gap_seconds around
    # each class's rank cuts): cleaned rows that reach no split.
    in_splits = {}
    for p in splits.values():
        for k, v in p["Label"].astype(str).value_counts().items():
            in_splits[k] = in_splits.get(k, 0) + int(v)
    part_a[tag]["_purge"] = {k: {"cleaned": int(n), "in_splits": in_splits.get(k, 0),
                                 "purged": int(n) - in_splits.get(k, 0)}
                             for k, n in sorted(cleaned.items())}
    # PART C: timestamps adjacent splits share (a cut inside one timestamp)
    part_a[tag]["_boundary"] = boundary_sharing(splits)
    part_a[tag]["_episodes"] = [ln.strip() for ln in buf.getvalue().splitlines()
                                if "episode" in ln]
    del splits
    print(f"\n  -- {tag}  ({time.time() - t0:.0f}s)")
    print(f"  {'split':<6s}{'class':<18s}{'rows':>9s}  {'first':<16s}{'last':<16s}"
          f"{'w/ benign':>10s}{'graphable':>10s}  benign from")
    for name, comp in part_a[tag].items():
        if name.startswith("_"):
            continue
        for cls, r in comp.items():
            share = r.get("share_sharing_window_with_benign")
            src = ", ".join(f"{k.split('.')[0]}:{v:,}" for k, v in r["source_files"].items()) \
                if cls == "BENIGN" else ""
            print(f"  {name:<6s}{cls:<18s}{r['rows']:>9,}  {r['first']:<16s}{r['last']:<16s}"
                  f"{'' if share is None else f'{share:.1%}':>10s}"
                  f"{r['rows_in_graphable_windows'] / max(r['rows'], 1):>10.1%}  {src}")
    print(f"  dead-zone purge (cleaned rows reaching no split): " + ", ".join(
        f"{k} {v['purged']:,} of {v['cleaned']:,}" for k, v in part_a[tag]["_purge"].items()))
    print(f"  PART C -- timestamps shared across a split boundary:")
    for cls, b in part_a[tag]["_boundary"].items():
        for edge in ("train|val", "val|test"):
            e = b[edge]
            if e["shared_timestamps"]:
                a, z = edge.split("|")
                print(f"    {cls:<18s}{edge:<10s} {e['shared_timestamps']} timestamp(s): "
                      f"{e[a + '_rows_on_shared']:,} {a} rows, {e[z + '_rows_on_shared']:,} {z} rows")
        print(f"    {cls:<18s}distinct timestamps per split: {b['distinct_timestamps']}")
    print("  episode assignment (the split's own lines):")
    for ln in part_a[tag]["_episodes"]:
        print(f"    {ln}")
if "_resolution" in part_a:
    print("\n  timestamp resolution per training file (fixed parse):")
    for f, r in part_a["_resolution"].items():
        print(f"    {f:<52s} rows {r['rows']:>8,}  off the minute {r['rows_off_the_minute']:>8,}"
              f"  distinct second values {r['distinct_second_values']}")


# ------------------------------------------------------------- PART B -------
print(f"\n{BAR}\n  PART B -- CONFIDENCE AGAINST THE SDN FLOORS (post-fix model)\n{BAR}")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
blob, src = load_checkpoint(cfg.checkpoint_path / "best.pt", map_location=device)
if blob is None:
    raise SystemExit("no readable best.pt")
scored_cfg = Config.from_dict(blob["config"]) if blob.get("config") else cfg
scored_cfg.base_dir = cfg.base_dir
model = build_model(scored_cfg).to(device)
model.load_state_dict(blob["model"])
model.eval()
print(f"  model: epoch {blob.get('epoch')} from {src}")
graphs = prepare_graphs(scored_cfg, force=False, verbose=False)


def score(gs):
    model.reset_memory()
    ys, ps, ws = [], [], []
    with torch.no_grad():
        for g in gs:
            g = g.to(device)
            o = model.step_with_memory(g, now=int(getattr(g, "window_end", 0)))
            lg, ey = o["edge_logits"].float(), g.edge_y
            m = getattr(g, "real_edge_mask", None)
            if m is not None:
                lg, ey = lg[m], ey[m]
            if len(ey):
                ps.append(torch.softmax(lg, -1).cpu().numpy())
                ys.append(ey.cpu().numpy())
                ws.append(np.full(len(ey), float(getattr(g, "window_start", np.nan))))
    return np.concatenate(ys), np.vstack(ps), np.concatenate(ws)


part_b = {}
scored = {}
for split in ("val", "test"):
    y, p, ws = score(graphs[split])
    scored[split] = (y, p, ws)
    pred, conf = p.argmax(1), p.max(1)
    rows = []
    for ti, tn in enumerate(CLASS_NAMES):
        for pi, pn in enumerate(CLASS_NAMES):
            if pn == "BENIGN":
                continue
            m = (y == ti) & (pred == pi)
            if not m.any():
                continue
            floor = POLICY_FLOORS.get(pn)
            cm = conf[m]
            rows.append({
                "true": tn, "predicted": pn, "edges": int(m.sum()),
                "quantiles": {f"p{int(q * 100)}": round(float(np.quantile(cm, q)), 4) for q in QS},
                "floor": floor,
                "edges_at_or_above_floor": int((cm >= floor).sum()) if floor is not None else None,
                "share_at_or_above_floor": (round(float((cm >= floor).mean()), 4)
                                            if floor is not None else None),
            })
    part_b[split] = rows
    print(f"\n  -- {split}")
    print(f"  {'true':<18s}{'predicted':<18s}{'edges':>8s}{'p5':>7s}{'p50':>7s}{'p95':>7s}"
          f"{'floor':>7s}{'>= floor':>10s}")
    for r in rows:
        q = r["quantiles"]
        print(f"  {r['true']:<18s}{r['predicted']:<18s}{r['edges']:>8,}{q['p5']:>7.3f}"
              f"{q['p50']:>7.3f}{q['p95']:>7.3f}{r['floor']:>7.2f}"
              f"{r['edges_at_or_above_floor']:>10,} ({r['share_at_or_above_floor']:.1%})")

# ------------------------------------------------------------- PART D -------
# Test PortScan at the minute it shares with validation (and train) versus
# after it. If the shared minute scores like validation and the rest like the
# test figure, the driver is contamination; if both score alike, composition.
print(f"\n{BAR}\n  PART D -- TEST PORTSCAN: THE SHARED MINUTE VERSUS THE REST\n{BAR}")
PS = list(CLASS_NAMES).index("PortScan")
shared = part_a["fixed_parse"]["_boundary"].get("PortScan", {}).get("val|test", {}).get("shared", [])
y, p, ws = scored["test"]
pred, conf = p.argmax(1), p.max(1)
part_d = {"shared_timestamps": shared, "floor": POLICY_FLOORS["PortScan"]}
if shared:
    first = min(shared)
    in_shared = (ws <= first) & (first < ws + W)
    for name, m in (("shared_minute", in_shared), ("after", ~in_shared & (ws > first))):
        t_ps, p_ps = (y == PS) & m, (pred == PS) & m
        tp = int((t_ps & p_ps).sum())
        prec = tp / max(int(p_ps.sum()), 1)
        rec = tp / max(int(t_ps.sum()), 1)
        ok = t_ps & p_ps
        part_d[name] = {
            "true_portscan_edges": int(t_ps.sum()), "predicted_portscan": int(p_ps.sum()),
            "correct": tp, "f1": round(2 * prec * rec / max(prec + rec, 1e-12), 4),
            "correct_at_or_above_floor": int((conf[ok] >= POLICY_FLOORS["PortScan"]).sum()),
            "share_of_correct_at_or_above_floor": (round(float((conf[ok] >= POLICY_FLOORS["PortScan"]).mean()), 4)
                                                   if ok.any() else None),
            "predicted_bruteforce": int((t_ps & (pred == list(CLASS_NAMES).index("BruteForce"))).sum()),
        }
        d = part_d[name]
        print(f"  {name:<14s} true PortScan {d['true_portscan_edges']:>7,}  correct {d['correct']:>7,}"
              f"  F1 {d['f1']:.4f}  correct >= 0.85: {d['correct_at_or_above_floor']:,}"
              f"  as BruteForce {d['predicted_bruteforce']:,}")
else:
    print("  no timestamp shared between validation and test PortScan -- nothing to separate")

result = {
    "what": "split composition under both parses, and post-fix confidence against the SDN floors",
    "prediction_recorded_before_measurement": PREDICTION,
    "window_seconds": W, "min_edges_per_graph": MIN_EDGES,
    "policy_floors": POLICY_FLOORS,
    "part_a_split_composition": part_a,
    "part_b_confidence": part_b,
    "part_d_portscan_shared_minute": part_d,
    "checkpoint_epoch": blob.get("epoch"),
}
(OUT / "split_composition.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(f"\n  saved: split_composition.json -> {OUT}")
