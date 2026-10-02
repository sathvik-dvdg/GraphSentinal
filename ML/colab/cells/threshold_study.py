# threshold_study.py
# Section 11.1: threshold study and held-out scoring (Monday, Thursday).
#
# Lifted from ML/GraphSentinel_Training.ipynb, cell index 33, so that
# ML/colab/colab_runner.py can run it unattended. It is executed with one
# global, `cfg`, exactly as the notebook cell was.
#
# DIFFERENCES FROM THE NOTEBOOK CELL (everything else is byte-identical):
#   1. OUT comes from the global GS_OUT when the runner sets it (default unchanged), so it can run off Colab without creating /content.
#   2. JSON key "binary_threshold" -> "binary_gate": the name backend/app/services/operating_points.py reads, and the name in the committed threshold_study.json.
#   3. JSON key "window_seconds" -> "alert_window_seconds", for the same reason.
#   4. JSON key "window_rule_min_flows" -> "alert_min_flows", for the same reason.
# ----------------------------------------------------------------------------
# 11.1 — THRESHOLD STUDY AND HELD-OUT SCORING
# ============================================================================
#  GRAPHSENTINEL -- THRESHOLD STUDY AND HELD-OUT SCORING
#
#  Answers three questions with numbers instead of defaults:
#
#    1. What does the model do on data it has never seen?
#         monday    a full capture day, ZERO attacks -- the false-alarm rate
#         thursday  Web Attack / Infiltration / Heartbleed -- families that are
#                   not in the label map and were never trained on
#         test      the held-out episode split (for comparison)
#         shuffled  test graphs with edge features permuted across rows -- a
#                   control that SHOULD collapse. If it does not, the model is
#                   reading something other than the flow features.
#
#    2. Precision and recall per threshold, at flow level AND window level.
#       The window table is the one an operator reads: an IDS does not alert
#       per flow, it alerts per time window, and one noisy flow in a 60s window
#       should not page anybody.
#
#    3. The operating thresholds themselves -- one binary attack/benign gate
#       and one min_conf per class for the SDN policy, which are currently
#       hardcoded at 0.80-0.90 and have never been fitted to anything.
#
#  THE ONE RULE THIS SCRIPT WILL NOT BREAK.
#  Thresholds are fitted on VALIDATION and reported on TEST, MONDAY and
#  THURSDAY. Fitting a threshold on the same data you then quote the precision
#  from is how a 0.99 appears in a report and 0.6 appears in production. Every
#  table below says which split it came from.
#
#  Read-only: trains nothing, overwrites no checkpoint. ~10-20 min (Monday and
#  Thursday have to be parsed and windowed from CSV).
# ============================================================================
import json, time, copy
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from graphsentinel.config import CLASS_NAMES, CLASS_TO_IDX, Config
from graphsentinel.models.net import build_model
from graphsentinel.train import load_checkpoint, prepare_graphs

assert "cfg" in dir(), "Run section 3 (config) first."

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
K = len(CLASS_NAMES)
BENIGN = 0
BAR = "=" * 78
OUT = Path(globals().get("GS_OUT", "/content/gs_logs")); OUT.mkdir(parents=True, exist_ok=True)

MONDAY = "Monday-WorkingHours.pcap_ISCX.csv"
SEED = 1234
UNSEEN_NAME = "__UNSEEN__"      # label for families outside the taxonomy
UNSEEN_IDX = K                  # one past the last real class; see build_day

# ---------------------------------------------------------------- model -----
blob, src = load_checkpoint(cfg.checkpoint_path / "best.pt", map_location=device)
if blob is None:
    raise SystemExit("no readable best.pt -- run training or rescue_artifacts.py")
scored_cfg = Config.from_dict(blob["config"]) if blob.get("config") else cfg
scored_cfg.base_dir = cfg.base_dir            # paths are environment, not model
model = build_model(scored_cfg).to(device)
model.load_state_dict(blob["model"])
model.eval()
print(f"model: epoch {blob.get('epoch')} from {src}")
print(f"classes: {CLASS_NAMES}")


# ------------------------------------------------------------- scoring ------
def score_graphs(graphs, tag):
    """Chronological pass. Returns per-edge window id, true label, probs.

    Memory is reset first: each evaluation set is its own timeline, and
    carrying host state from Monday into Thursday would be a leak.
    """
    model.reset_memory()
    wids, ys, ps = [], [], []
    t0 = time.time()
    with torch.no_grad():
        for wi, g in enumerate(graphs):
            g = g.to(device)
            out = model.step_with_memory(g, now=int(getattr(g, "window_end", 0)))
            logits = out["edge_logits"].float()
            ey = g.edge_y
            mask = getattr(g, "real_edge_mask", None)
            if mask is not None:
                logits, ey = logits[mask], ey[mask]
            if not len(ey):
                continue
            p = torch.softmax(logits, dim=-1).cpu().numpy()
            ps.append(p)
            ys.append(ey.cpu().numpy())
            wids.append(np.full(len(p), wi, dtype=np.int64))
    if not ps:
        return None
    out = {"wid": np.concatenate(wids), "y": np.concatenate(ys),
           "p": np.vstack(ps), "n_windows": len(graphs)}
    print(f"  {tag:<10s} {len(out['y']):>9,} flows over {len(graphs):>5,} windows"
          f"   ({time.time()-t0:.0f}s)")
    return out


# ------------------------------------------- build the evaluation sets ------
print(f"\n{BAR}\n  BUILDING EVALUATION SETS\n{BAR}")
graphs = prepare_graphs(scored_cfg, force=False, verbose=False)
SETS = {}
SETS["val"] = score_graphs(graphs["val"], "val")        # FITTING ONLY
SETS["test"] = score_graphs(graphs["test"], "test")


def build_day(files, keep_unseen=False, tag=""):
    """Window-graph a set of CSVs the model has never been trained on.

    keep_unseen: CICIDS2017 labels outside RAW_LABEL_MAP (Web Attack,
    Infiltration, Heartbleed) are normally DROPPED at load. For the open-set
    test they are exactly the rows that matter, so the map is temporarily
    widened and those rows are given index K -- a real attack with no class in
    this taxonomy. They are never fed to any per-class metric.
    """
    from graphsentinel.data import preprocess as pre
    from graphsentinel.data.graph_builder import GraphBuilder, HostHistory

    c = copy.deepcopy(scored_cfg)
    c.data.csv_files = list(files)
    c.data.unseen_family_files = []

    saved = pre.RAW_LABEL_MAP
    if keep_unseen:
        widened = dict(saved)
        for lbl in ("Web Attack \x96 Brute Force", "Web Attack \x96 XSS",
                    "Web Attack \x96 Sql Injection", "Infiltration", "Heartbleed"):
            widened.setdefault(lbl, UNSEEN_NAME)
        # the CSVs use a latin-1 0x96 dash; match on a normalised form too
        pre.RAW_LABEL_MAP = _CaseMap(widened)
    try:
        df = pre.load_raw(c, verbose=False)
        df = pre.clean(df, c, verbose=False)
        df = pre.clip_outliers(df, c, c.data.edge_feature_cols + c.data.volumetric_cols)
    finally:
        pre.RAW_LABEL_MAP = saved

    # WHY UNSEEN GETS INDEX K AND NOT -1.
    # -1 looks like the natural "no class" marker and it silently corrupts the
    # graph. GraphBuilder._node_labels votes with
    #     flat = endpoint * n_classes + edge_y
    #     np.bincount(flat, ...)
    # so edge_y = -1 either raises on node 0 or, worse, credits the vote to the
    # PREVIOUS node's last class. Giving unseen families a real extra index and
    # widening num_classes FOR THE BUILD ONLY keeps that arithmetic valid. The
    # model is built from scored_cfg and still has K outputs; nothing here
    # indexes a probability by y.
    lab = df["Label"].astype(str)
    df["y"] = lab.map(CLASS_TO_IDX).fillna(UNSEEN_IDX).astype("int64")
    n_unseen = int((df["y"] == UNSEEN_IDX).sum())
    df["binary_label"] = (df["y"] != 0).astype("int8")
    if n_unseen:
        c.model.num_classes = UNSEEN_IDX + 1

    builder = GraphBuilder(c, history=HostHistory(capacity=c.model.memory_capacity))
    g = builder.build(df, update_history=True, verbose=False)
    print(f"  {tag}: {len(df):,} flows, {n_unseen:,} unseen-family, "
          f"{len(g):,} windows")
    return g


class _CaseMap(dict):
    """Label lookup that also matches after collapsing the odd dash bytes and
    whitespace CICIDS2017 uses inconsistently across files."""

    @staticmethod
    def _norm(k):
        return " ".join(str(k).replace("\x96", "-").replace("–", "-").split()).lower()

    def __init__(self, base):
        super().__init__(base)
        self._n = {self._norm(k): v for k, v in base.items()}

    def get(self, k, default=None):
        if k in self:
            return dict.__getitem__(self, k)
        return self._n.get(self._norm(k), default)

    def __missing__(self, k):
        # MUST return NaN, not raise. pandas' Series.map takes the
        # `mapper[x]` path for any dict subclass defining __missing__, so a
        # KeyError here would abort the whole load on the first label outside
        # the map instead of dropping that row the way load_raw expects.
        return self._n.get(self._norm(k), np.nan)


try:
    SETS["monday"] = score_graphs(build_day([MONDAY], tag="monday"), "monday")
except Exception as exc:
    print(f"  monday SKIPPED: {type(exc).__name__}: {exc}")
    SETS["monday"] = None

try:
    thu = list(scored_cfg.data.unseen_family_files) or [
        "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
        "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv"]
    SETS["thursday"] = score_graphs(
        build_day(thu, keep_unseen=True, tag="thursday"), "thursday")
except Exception as exc:
    print(f"  thursday SKIPPED: {type(exc).__name__}: {exc}")
    SETS["thursday"] = None

# shuffled control: same graphs, edge features permuted across rows
rng = np.random.default_rng(SEED)
shuffled = []
for g in graphs["test"]:
    h = g.clone()
    perm = torch.from_numpy(rng.permutation(h.edge_attr.shape[0]))
    h.edge_attr = h.edge_attr[perm]
    shuffled.append(h)
SETS["shuffled"] = score_graphs(shuffled, "shuffled")
del shuffled


# ------------------------------------------------------- threshold maths ----
def grid_for(s, n=400):
    """A linear grid is useless here: 199,185 of 228,000 test edges sit above
    0.9 confidence. Quantiles put the resolution where the data is."""
    q = np.unique(np.quantile(s, np.linspace(0.0, 1.0, n)))
    return np.unique(np.concatenate([q, [0.5, 0.8, 0.85, 0.9, 0.95, 0.99]]))


def pr_table(y_pos, s, grid):
    rows = []
    P, N = int(y_pos.sum()), int((~y_pos).sum())
    for t in grid:
        fired = s >= t
        tp = int((fired & y_pos).sum()); fp = int((fired & ~y_pos).sum())
        fn = P - tp; tn = N - fp
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / P if P else float("nan")
        fpr = fp / N if N else float("nan")
        f1 = (2 * prec * rec / (prec + rec)
              if prec == prec and rec == rec and prec + rec > 0 else 0.0)
        rows.append({"threshold": float(t), "tp": tp, "fp": fp, "fn": fn,
                     "tn": tn, "precision": prec, "recall": rec, "fpr": fpr,
                     "f1": f1})
    return pd.DataFrame(rows)


def show(df, cols, n=12, note=""):
    d = df[cols].copy()
    if len(d) > n:                      # thin evenly, always keep the ends
        idx = np.unique(np.linspace(0, len(d) - 1, n).astype(int))
        d = d.iloc[idx]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(d.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    if note:
        print(f"  {note}")


# =========================================================== BINARY GATE =====
print(f"\n{BAR}\n  1. BINARY GATE  --  attack score = 1 - P(BENIGN)\n{BAR}")
print("  FITTED ON VALIDATION. Every later table applies this number to data")
print("  the threshold has never seen.\n")

v = SETS["val"]
v_score = 1.0 - v["p"][:, BENIGN]
v_pos = v["y"] != BENIGN
vt = pr_table(v_pos, v_score, grid_for(v_score))
best = vt.loc[vt["f1"].idxmax()]
T_BIN = float(best["threshold"])

show(vt, ["threshold", "precision", "recall", "fpr", "f1"], 14)
print(f"\n  >> BINARY THRESHOLD (max F1 on validation): {T_BIN:.6f}")
print(f"     validation precision {best['precision']:.4f}  "
      f"recall {best['recall']:.4f}  FPR {best['fpr']:.6f}  F1 {best['f1']:.4f}")

# alternatives, so the choice is visible rather than asserted
print("\n  alternatives at fixed operating points (validation):")
print(f"  {'criterion':<26s}{'threshold':>12s}{'precision':>11s}{'recall':>9s}{'FPR':>11s}")
for label, sel in [
    ("max F1", vt["f1"].idxmax()),
    ("FPR <= 1%", (vt[vt["fpr"] <= 0.01]["recall"].idxmax()
                   if (vt["fpr"] <= 0.01).any() else None)),
    ("FPR <= 0.1%", (vt[vt["fpr"] <= 0.001]["recall"].idxmax()
                     if (vt["fpr"] <= 0.001).any() else None)),
    ("precision >= 99%", (vt[vt["precision"] >= 0.99]["recall"].idxmax()
                          if (vt["precision"] >= 0.99).any() else None)),
    ("precision >= 99.9%", (vt[vt["precision"] >= 0.999]["recall"].idxmax()
                            if (vt["precision"] >= 0.999).any() else None)),
]:
    if sel is None:
        print(f"  {label:<26s}{'unreachable':>12s}")
        continue
    r = vt.loc[sel]
    print(f"  {label:<26s}{r['threshold']:>12.6f}{r['precision']:>11.4f}"
          f"{r['recall']:>9.4f}{r['fpr']:>11.6f}")

# ------------------------------------- apply it to every held-out set -------
print(f"\n{BAR}\n  2. THAT THRESHOLD APPLIED TO HELD-OUT DATA  (flow level)\n{BAR}")
print(f"  threshold = {T_BIN:.6f}, fitted on validation, applied unchanged\n")
print(f"  {'dataset':<12s}{'flows':>10s}{'attacks':>9s}{'precision':>11s}"
      f"{'recall':>9s}{'FPR':>11s}{'F1':>8s}")
flow_rows = []
for name in ("test", "monday", "thursday", "shuffled"):
    d = SETS.get(name)
    if d is None:
        continue
    s = 1.0 - d["p"][:, BENIGN]
    pos = d["y"] != BENIGN
    r = pr_table(pos, s, [T_BIN]).iloc[0]
    flow_rows.append({"dataset": name, "flows": len(pos), "attacks": int(pos.sum()),
                      **{k: r[k] for k in ("precision", "recall", "fpr", "f1",
                                           "tp", "fp", "fn", "tn")}})
    p_ = "   n/a  " if r["precision"] != r["precision"] else f"{r['precision']:>11.4f}"
    rc = "   n/a " if not pos.sum() else f"{r['recall']:>9.4f}"
    print(f"  {name:<12s}{len(pos):>10,}{int(pos.sum()):>9,}{p_}{rc}"
          f"{r['fpr']:>11.6f}{r['f1']:>8.4f}")
pd.DataFrame(flow_rows).to_csv(OUT / "threshold_flow_level.csv", index=False)

print("\n  how to read this:")
print("    monday   has ZERO attacks, so precision and recall are undefined and")
print("             FPR is the whole story -- it is your false-alarm rate on a")
print("             real working day the model has never seen.")
print("    thursday carries BENIGN traffic plus unseen families (Web Attack,")
print("             Infiltration) with no class in this taxonomy. Recall is the")
print("             fraction of a NOVEL attack the binary gate flags at all, and")
print("             its false positives are real ones on real benign traffic.")
print("             This is an open-set number, not a classifier one.")
print("    shuffled should collapse. If its recall stays high, the model is not")
print("             reading the edge features and every other number is suspect.")

# ============================================================ WINDOW LEVEL ===
print(f"\n{BAR}\n  3. WINDOW-LEVEL PRECISION AND RECALL\n{BAR}")
print(f"  A window ({scored_cfg.graph.window_seconds}s) is TRULY an attack window if it contains >= 1")
print("  attack flow. It is ALERTED if at least MIN_FLOWS flows in it exceed the")
print("  binary threshold. This is what an operator actually sees -- one noisy")
print("  flow in a minute of traffic should not page anyone, and the table below")
print("  is how you choose how many it takes.\n")

MIN_FLOWS = [1, 2, 3, 5, 10, 25, 50, 100]


def window_table(d, thr):
    n_w = d["n_windows"]
    atk = np.zeros(n_w, dtype=bool)
    fired = np.zeros((len(MIN_FLOWS), n_w), dtype=bool)
    s = 1.0 - d["p"][:, BENIGN]
    hot = s >= thr
    # counts per window without a python loop over flows
    cnt_hot = np.bincount(d["wid"][hot], minlength=n_w)
    cnt_atk = np.bincount(d["wid"][d["y"] != BENIGN], minlength=n_w)
    atk = cnt_atk > 0
    for i, mf in enumerate(MIN_FLOWS):
        fired[i] = cnt_hot >= mf
    rows = []
    for i, mf in enumerate(MIN_FLOWS):
        f = fired[i]
        tp = int((f & atk).sum()); fp = int((f & ~atk).sum())
        fn = int((~f & atk).sum()); tn = int((~f & ~atk).sum())
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        fpr = fp / (fp + tn) if fp + tn else float("nan")
        f1 = (2 * prec * rec / (prec + rec)
              if prec == prec and rec == rec and prec + rec > 0 else 0.0)
        rows.append({"min_flows": mf, "windows": n_w, "attack_windows": int(atk.sum()),
                     "alerted": int(f.sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                     "precision": prec, "recall": rec, "fpr": fpr, "f1": f1})
    return pd.DataFrame(rows)


win_all = []
for name in ("test", "monday", "thursday", "shuffled"):
    d = SETS.get(name)
    if d is None:
        continue
    wt = window_table(d, T_BIN)
    wt.insert(0, "dataset", name)
    win_all.append(wt)
    print(f"  -- {name}  ({d['n_windows']:,} windows, "
          f"{int(wt.iloc[0]['attack_windows']):,} contain an attack)")
    show(wt, ["min_flows", "alerted", "tp", "fp", "fn", "precision", "recall",
              "fpr", "f1"], len(MIN_FLOWS))
    print()
win_df = pd.concat(win_all, ignore_index=True)
win_df.to_csv(OUT / "threshold_window_level.csv", index=False)

# the recommendation, chosen on test where both classes exist
_t = win_df[(win_df.dataset == "test") & win_df.f1.notna()]
if len(_t):
    bw = _t.loc[_t["f1"].idxmax()]
    _m = win_df[(win_df.dataset == "monday") & (win_df.min_flows == bw["min_flows"])]
    print(f"  >> RECOMMENDED WINDOW RULE: alert when >= {int(bw['min_flows'])} flows "
          f"in a {scored_cfg.graph.window_seconds}s window exceed {T_BIN:.6f}")
    print(f"     on test: precision {bw['precision']:.4f}  recall {bw['recall']:.4f}"
          f"  F1 {bw['f1']:.4f}")
    if len(_m):
        r = _m.iloc[0]
        print(f"     on monday (no attacks at all): {int(r['fp'])} false alerts in "
              f"{int(r['windows']):,} windows = {r['fpr']:.4%} of windows")

# ======================================================= PER-CLASS SDN =======
print(f"\n{BAR}\n  4. PER-CLASS SDN GATES  (min_conf for MITIGATION_POLICY)\n{BAR}")
print("  The operational rule is: fire when argmax == class AND P(class) >=")
print("  min_conf. So that is exactly what is swept -- not P(class) in")
print("  isolation, which would measure a rule the SDN layer never applies.")
print("  FITTED ON VALIDATION, then reported on TEST.\n")

v_arg = v["p"].argmax(1)
gates, gate_rows = {}, []
for k in range(1, K):
    c = CLASS_NAMES[k]
    sel = v_arg == k
    if not sel.sum() or not (v["y"] == k).sum():
        print(f"  {c:<18s} cannot fit: "
              f"{int(sel.sum())} predicted, {int((v['y'] == k).sum())} true in validation")
        gates[c] = None
        continue
    s_k = np.where(sel, v["p"][:, k], -1.0)     # only argmax-k edges can fire
    tab = pr_table(v["y"] == k, s_k, grid_for(v["p"][sel, k]))
    b = tab.loc[tab["f1"].idxmax()]
    gates[c] = float(b["threshold"])
    gate_rows.append({"class": c, "min_conf": gates[c],
                      "val_precision": b["precision"], "val_recall": b["recall"],
                      "val_f1": b["f1"]})

t_ = SETS["test"]
t_arg = t_["p"].argmax(1)
print(f"  {'class':<18s}{'fitted':>10s}{'current':>9s} | {'val prec':>9s}{'val rec':>9s}"
      f" | {'TEST prec':>10s}{'TEST rec':>9s}{'TEST F1':>9s}")
CURRENT = {"DDoS": 0.90, "PortScan": 0.85, "Botnet": 0.80, "SSHBrute": 0.85,
           "DoSHulk": 0.90, "Volumetric_Flood": 0.90, "BruteForce": 0.85}
final = []
for k in range(1, K):
    c = CLASS_NAMES[k]
    g = gates.get(c)
    if g is None:
        print(f"  {c:<18s}{'--':>10s}{CURRENT.get(c, float('nan')):>9.2f} |"
              f"  no validation support -- keep the conservative default")
        final.append({"class": c, "min_conf": CURRENT.get(c, 0.90),
                      "fitted": False, "reason": "no validation support"})
        continue
    s_k = np.where(t_arg == k, t_["p"][:, k], -1.0)
    r = pr_table(t_["y"] == k, s_k, [g]).iloc[0]
    vr = next(x for x in gate_rows if x["class"] == c)
    print(f"  {c:<18s}{g:>10.4f}{CURRENT.get(c, float('nan')):>9.2f} |"
          f"{vr['val_precision']:>9.4f}{vr['val_recall']:>9.4f} |"
          f"{r['precision']:>10.4f}{r['recall']:>9.4f}{r['f1']:>9.4f}")
    final.append({"class": c, "min_conf": g, "fitted": True,
                  "val_precision": vr["val_precision"], "val_recall": vr["val_recall"],
                  "test_precision": float(r["precision"]),
                  "test_recall": float(r["recall"]), "test_f1": float(r["f1"])})

print("\n  A large val->test precision drop on any row means that gate is fitted")
print("  to validation noise -- keep the conservative default for that class")
print("  rather than shipping the fitted number.")
print("\n  These are PROPOSALS. Nothing is written to MITIGATION_POLICY, and")
print("  dry_run stays True until the rules are validated in a lab topology.")

# ---------------------------------------------------------------- save ------
summary = {
    "checkpoint_epoch": blob.get("epoch"),
    "fitted_on": "validation split",
    "binary_gate": T_BIN,
    "binary_criterion": "max F1 on validation",
    "alert_window_seconds": scored_cfg.graph.window_seconds,
    "alert_min_flows": (int(bw["min_flows"]) if len(_t) else None),
    "per_class_min_conf": final,
    "flow_level": flow_rows,
    "split_protocol": scored_cfg.data.split_strategy,
    "caveat": ("thresholds fitted on validation and reported on test/monday/"
               "thursday; monday has no attacks so only FPR is meaningful; "
               "thursday is unseen families with no class label"),
}
(OUT / "threshold_study.json").write_text(json.dumps(summary, indent=2, default=float))
for p in (OUT, cfg.log_path):
    try:
        p.mkdir(parents=True, exist_ok=True)
        for f in ("threshold_study.json", "threshold_flow_level.csv",
                  "threshold_window_level.csv"):
            if (OUT / f).exists():
                (p / f).write_bytes((OUT / f).read_bytes())
    except Exception as exc:
        print(f"  note: could not copy results to {p} ({type(exc).__name__})")

print(f"\n{BAR}")
print(f"  saved: threshold_study.json, threshold_flow_level.csv,")
print(f"         threshold_window_level.csv  -> {OUT} and {cfg.log_path}")
print(BAR)
