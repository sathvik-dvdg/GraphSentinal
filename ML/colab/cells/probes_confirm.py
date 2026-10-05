# probes_confirm.py
# Section 12.2: confirm on validation, memory on/off, per-feature leave-one-out.
#
# Lifted from ML/GraphSentinel_Training.ipynb, cell index 36, so that
# ML/colab/colab_runner.py can run it unattended. It is executed with one
# global, `cfg`, exactly as the notebook cell was.
#
# DIFFERENCES FROM THE NOTEBOOK CELL (everything else is byte-identical):
#   1. The memory-off result is kept in `memory_off` as well as printed, so the runner can write it to probes.json.
# ----------------------------------------------------------------------------
# 12.2 — CONFIRM ON VALIDATION + PER-FEATURE LEAVE-ONE-OUT
# ============================================================================
#  CONFIRMING THE TWO SURPRISES, AND FINDING WHICH FEATURES CAUSE THEM
#
#  The information probe produced two results that are too good to act on
#  without checking, because both were measured on TEST:
#
#      full           macro F1 0.7042   BruteForce 0.5508
#      no_edge_feat   macro F1 0.7998   BruteForce 1.0000   <- zeroing inputs HELPED
#      ip_permuted    macro F1 0.7975   BruteForce 0.9861   <- so did breaking host identity
#
#  Choosing a configuration because it scores well on test IS test-set
#  selection, and it is how a +0.10 evaporates in the final write-up. So:
#
#    PART 1  re-run the key ablations on VALIDATION. If the effect is real it
#            appears on both splits. If it appears only on test, it is luck.
#
#    PART 2  isolate the host memory. ip_permuted scrambles the keys the memory
#            is looked up by, so "permuting identities helps" is really the
#            hypothesis "the memory is hurting". Resetting the memory before
#            every window tests that directly instead of by proxy.
#
#    PART 3  leave-one-out over the 20 numeric edge features. "The flow
#            features hurt" is not actionable; "these three features hurt" is.
#
#  NOTHING HERE PICKS A MODEL. It tells you which retrain is worth running.
#  Read-only, ~4-6 min.
# ============================================================================
import copy
import numpy as np
import torch

from graphsentinel.config import CLASS_NAMES, Config
from graphsentinel.models.net import build_model
from graphsentinel.train import load_checkpoint, prepare_graphs
from graphsentinel.evaluate import multiclass_metrics
from graphsentinel.data.graph_builder import EDGE_FEATURE_NAMES, VOLUMETRIC_EDGE_IDX

assert "cfg" in dir(), "Run section 3 (config) first."
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
K = len(CLASS_NAMES)
BAR = "=" * 78
SEED = 7

blob, _ = load_checkpoint(cfg.checkpoint_path / "best.pt", map_location=device)
if blob is None:
    raise SystemExit("no readable best.pt")
scored_cfg = Config.from_dict(blob["config"]) if blob.get("config") else cfg
scored_cfg.base_dir = cfg.base_dir
model = build_model(scored_cfg).to(device)
model.load_state_dict(blob["model"])
model.eval()

G = prepare_graphs(scored_cfg, force=False, verbose=False)
SPLITS = {"val": G["val"], "test": G["test"]}
print(f"model epoch {blob.get('epoch')} | val {len(G['val'])} windows, "
      f"test {len(G['test'])} windows")
print(f"edge features ({len(EDGE_FEATURE_NAMES)}): volumetric idx {sorted(VOLUMETRIC_EDGE_IDX)}")


def score(gs, reset_every_window=False):
    model.reset_memory()
    ys, ps = [], []
    with torch.no_grad():
        for g in gs:
            if reset_every_window:
                model.reset_memory()
            g = g.to(device)
            out = model.step_with_memory(g, now=int(getattr(g, "window_end", 0)))
            logits = out["edge_logits"].float()
            ey = g.edge_y
            m = getattr(g, "real_edge_mask", None)
            if m is not None:
                logits, ey = logits[m], ey[m]
            if not len(ey):
                continue
            ps.append(torch.softmax(logits, -1).cpu().numpy())
            ys.append(ey.cpu().numpy())
    y, p = np.concatenate(ys), np.vstack(ps)
    return multiclass_metrics(y, p.argmax(1), p, "edge_")


def variant(gs, zero_edge=False, zero_ports=False, perm_ip=False, zero_idx=None):
    out = []
    rng = np.random.default_rng(SEED)
    for g in gs:
        h = g.clone()
        if zero_edge:
            h.edge_attr = torch.zeros_like(h.edge_attr)
        if zero_idx is not None:
            h.edge_attr = h.edge_attr.clone()
            h.edge_attr[:, list(zero_idx)] = 0.0
        if zero_ports:
            for a in ("edge_dst_port", "edge_src_port", "edge_proto"):
                if hasattr(h, a):
                    setattr(h, a, torch.zeros_like(getattr(h, a)))
        if perm_ip and hasattr(h, "node_ip_int"):
            v = h.node_ip_int
            h.node_ip_int = v[torch.from_numpy(rng.permutation(len(v)))]
        out.append(h)
    return out


def line(tag, m, base=None):
    per = "".join(f"{m.get(f'edge_f1_{c}', float('nan')):>10.4f}" for c in CLASS_NAMES)
    mf = m.get("edge_macro_f1", float("nan"))
    d = f"{mf - base:>+9.4f}" if base is not None else " " * 9
    print(f"  {tag:<22s}{per}{mf:>9.4f}{d}")


HDR = ("  " + f"{'variant':<22s}"
       + "".join(f"{c[:8]:>10s}" for c in CLASS_NAMES)
       + f"{'MACRO':>9s}{'delta':>9s}")

# ======================================================= PART 1: BOTH SPLITS =
print(f"\n{BAR}\n  PART 1  --  DOES ZEROING THE EDGE FEATURES HELP ON VALIDATION TOO?\n{BAR}")
print("  If it only helps on test, it is test-set noise and must not be used.\n")

summary = {}
for split, gs in SPLITS.items():
    print(f"  -- {split}")
    print(HDR)
    base_m = score(gs)
    line("full", base_m)
    b = base_m["edge_macro_f1"]
    res = {"full": b}
    for tag, kw in [("no_edge_feat", dict(zero_edge=True)),
                    ("no_volumetric_only", dict(zero_idx=list(VOLUMETRIC_EDGE_IDX))),
                    ("ip_permuted", dict(perm_ip=True)),
                    ("no_edge_feat+ip_perm", dict(zero_edge=True, perm_ip=True))]:
        m = score(variant(gs, **kw))
        line(tag, m, b)
        res[tag] = m["edge_macro_f1"]
    summary[split] = res
    print()

print("  AGREEMENT BETWEEN SPLITS (this is the whole point of Part 1):")
print(f"  {'variant':<24s}{'val delta':>12s}{'test delta':>12s}{'verdict':>28s}")
for tag in ("no_edge_feat", "no_volumetric_only", "ip_permuted", "no_edge_feat+ip_perm"):
    dv = summary["val"][tag] - summary["val"]["full"]
    dt = summary["test"][tag] - summary["test"]["full"]
    if dv > 0.02 and dt > 0.02:
        v = "REAL -- helps on both"
    elif dv < -0.02 and dt < -0.02:
        v = "REAL -- hurts on both"
    elif abs(dv) <= 0.02 and abs(dt) <= 0.02:
        v = "no effect either way"
    else:
        v = "SPLIT-SPECIFIC -- do not act"
    print(f"  {tag:<24s}{dv:>+12.4f}{dt:>+12.4f}{v:>28s}")

# ============================================================ PART 2: MEMORY =
print(f"\n{BAR}\n  PART 2  --  IS THE HOST MEMORY HELPING OR HURTING?\n{BAR}")
print("  ip_permuted scrambles the keys the memory is read by, so its gain was")
print("  really a hypothesis about the memory. Resetting before every window")
print("  removes cross-window state outright and tests it directly.\n")
print(HDR)
memory_off = {}
for split, gs in SPLITS.items():
    b = summary[split]["full"]
    m = score(gs, reset_every_window=True)
    memory_off[split] = m
    line(f"{split}: memory OFF", m, b)
print("\n  A positive delta here means the memory module -- a headline piece of")
print("  this architecture -- is COSTING you accuracy on this dataset. That is")
print("  a reportable negative result, not something to hide. A near-zero delta")
print("  means the memory is inert and the ip_permuted gain came from somewhere")
print("  else, in which case do not blame the memory in the write-up.")

# ================================================= PART 3: WHICH FEATURES ====
print(f"\n{BAR}\n  PART 3  --  LEAVE-ONE-OUT OVER THE 20 NUMERIC EDGE FEATURES (test)\n{BAR}")
print("  'the flow features hurt' is not actionable. This says which ones.")
print("  A POSITIVE delta means zeroing that feature IMPROVED macro F1 --")
print("  the model is being actively misled by it.\n")
b_test = summary["test"]["full"]
loo = []
for i, name in enumerate(EDGE_FEATURE_NAMES):
    m = score(variant(SPLITS["test"], zero_idx=[i]))
    loo.append((name, i, m["edge_macro_f1"] - b_test,
                m.get("edge_f1_BruteForce", float("nan")),
                m.get("edge_f1_PortScan", float("nan"))))
loo.sort(key=lambda r: -r[2])
print(f"  {'feature':<34s}{'idx':>5s}{'delta macro':>13s}{'BruteForce':>12s}{'PortScan':>10s}")
for name, i, d, bf, ps in loo:
    mark = "  <== misleading" if d > 0.02 else ("  (load-bearing)" if d < -0.02 else "")
    print(f"  {name[:33]:<34s}{i:>5d}{d:>+13.4f}{bf:>12.4f}{ps:>10.4f}{mark}")

harmful = [n for n, _, d, _, _ in loo if d > 0.02]
print(f"\n  features whose REMOVAL improves macro F1: {len(harmful)}")
for n in harmful:
    print(f"      {n}")

print(f"\n{BAR}\n  WHAT TO RETRAIN\n{BAR}")
dv = summary["val"]["no_edge_feat"] - summary["val"]["full"]
dt = summary["test"]["no_edge_feat"] - summary["test"]["full"]
if dv > 0.02 and dt > 0.02:
    print("  Zeroing the numeric edge features helps on BOTH splits, so it is a")
    print("  real property of this model and not test noise. But do NOT ship a")
    print("  model that is fed zeros: that is a trained-with-features model being")
    print("  run out of distribution, and it will not behave the same after a")
    print("  retrain. The experiment worth running is a RETRAIN with the harmful")
    print("  features dropped from cfg.data.edge_feature_cols, selected on")
    print("  validation as usual, then scored once on test.")
elif dv > 0.02 or dt > 0.02:
    print("  The effect appears on one split only. Treat it as noise, keep the")
    print("  current feature set, and say so if a reviewer raises the ablation.")
else:
    print("  The test-set gain did not reproduce on validation. It was noise.")
    print("  Keep the current configuration and report the ablation honestly.")
print("\n  Either way: the RandomForest baseline is now the decisive experiment.")
print("  Give it node features + port tokens, which this probe says are where")
print("  the signal lives, and see whether message passing adds anything.")
