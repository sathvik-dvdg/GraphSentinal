# probes_information.py
# Section 12.1: information-source ablation on the test split.
#
# Lifted from ML/GraphSentinel_Training.ipynb, cell index 35, so that
# ML/colab/colab_runner.py can run it unattended. It is executed with one
# global, `cfg`, exactly as the notebook cell was.
#
# DIFFERENCES FROM THE NOTEBOOK CELL (everything else is byte-identical):
#   none
# ----------------------------------------------------------------------------
# 12.1 — INFORMATION-SOURCE ABLATION
# ============================================================================
#  WHAT IS THIS MODEL ACTUALLY READING?
#
#  WHY THIS REPLACES THE "shuffled" CONTROL, WHICH WAS BROKEN.
#
#  The threshold study's shuffled control reported
#      test      precision 0.9997  recall 0.9949  F1 0.9973
#      shuffled  precision 0.9998  recall 0.9949  F1 0.9973
#  and that looked like proof the model ignores its edge features. It is not
#  proof of anything. That control permuted edge_attr WITHIN each window, and
#  under the episode split the attack windows are close to class-homogeneous:
#  in a window that is 100% Volumetric_Flood, permuting feature rows among
#  Volumetric_Flood edges changes nothing at all. The control was a no-op by
#  construction. It also left the port and protocol tokens and the node
#  features untouched, which is where much of the signal lives.
#
#  So instead of one weak shuffle, this probe removes ONE information source
#  at a time and reports what survives. That answers the question the NAT
#  finding makes urgent -- four of five attack families are the same
#  (172.16.0.1 -> 192.168.10.50) host pair, so "the model memorised the host
#  pair" is a live hypothesis that has to be tested, not assumed away.
#
#    full            baseline
#    no_edge_feat    the 20 flow features zeroed
#    no_ports        port + protocol tokens flattened to one value
#    no_flow_info    both of the above -- nothing left about the flow itself
#    no_node_feat    the 16 node features zeroed
#    topology_only   no flow info, no node features -- only the graph shape
#    global_shuffle  edge features permuted ACROSS ALL WINDOWS (the control
#                    the threshold study should have run)
#    rewired         edge_index randomised -- topology destroyed, features kept
#    ip_permuted     node identities remapped -- breaks host memorisation
#
#  Read-only. ~3-5 min on the cached test graphs.
# ============================================================================
import copy
import numpy as np
import torch

from graphsentinel.config import CLASS_NAMES, Config
from graphsentinel.models.net import build_model
from graphsentinel.train import load_checkpoint, prepare_graphs
from graphsentinel.evaluate import multiclass_metrics

assert "cfg" in dir(), "Run section 3 (config) first."

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
K = len(CLASS_NAMES)
BAR = "=" * 78
SEED = 7

blob, src = load_checkpoint(cfg.checkpoint_path / "best.pt", map_location=device)
if blob is None:
    raise SystemExit("no readable best.pt")
scored_cfg = Config.from_dict(blob["config"]) if blob.get("config") else cfg
scored_cfg.base_dir = cfg.base_dir
model = build_model(scored_cfg).to(device)
model.load_state_dict(blob["model"])
model.eval()
print(f"model: epoch {blob.get('epoch')}  |  classes: {CLASS_NAMES}")

graphs = prepare_graphs(scored_cfg, force=False, verbose=False)
TEST = graphs["test"]
print(f"test: {len(TEST)} windows")


# ------------------------------------------------------------- variants -----
def clone_all(gs):
    return [g.clone() for g in gs]


def v_full(gs):
    return gs


def v_no_edge_feat(gs):
    for g in gs:
        g.edge_attr = torch.zeros_like(g.edge_attr)
    return gs


def v_no_ports(gs):
    for g in gs:
        for a in ("edge_dst_port", "edge_src_port", "edge_proto"):
            if hasattr(g, a):
                setattr(g, a, torch.zeros_like(getattr(g, a)))
    return gs


def v_no_flow_info(gs):
    return v_no_ports(v_no_edge_feat(gs))


def v_no_node_feat(gs):
    for g in gs:
        g.x = torch.zeros_like(g.x)
    return gs


def v_topology_only(gs):
    return v_no_node_feat(v_no_flow_info(gs))


def v_global_shuffle(gs):
    """Permute every edge's features across the WHOLE test set, not within its
    own window. This is the control that actually breaks the feature->label
    association, because it moves a Volumetric_Flood feature vector onto a
    BENIGN edge in a different window."""
    rng = np.random.default_rng(SEED)
    sizes = [g.edge_attr.shape[0] for g in gs]
    total = sum(sizes)
    perm = torch.from_numpy(rng.permutation(total))
    pool = {"edge_attr": torch.cat([g.edge_attr for g in gs])}
    for a in ("edge_dst_port", "edge_src_port", "edge_proto"):
        if hasattr(gs[0], a):
            pool[a] = torch.cat([getattr(g, a) for g in gs])
    for a in pool:
        pool[a] = pool[a][perm]
    off = 0
    for g, n in zip(gs, sizes):
        for a, t in pool.items():
            setattr(g, a, t[off:off + n])
        off += n
    return gs


def v_rewired(gs):
    """Randomise which nodes each edge connects. Features stay on their own
    edge, so anything that survives is being read from the flow, not the
    topology."""
    rng = np.random.default_rng(SEED)
    for g in gs:
        n = int(g.x.shape[0])
        e = int(g.edge_index.shape[1])
        g.edge_index = torch.from_numpy(
            rng.integers(0, max(n, 1), size=(2, e))).to(g.edge_index.dtype)
    return gs


def v_ip_permuted(gs):
    """Keep the graph and the features, change WHO each node is. The host
    memory is keyed on node_ip_int, so if performance depends on recognising
    172.16.0.1 specifically, this is where it shows."""
    rng = np.random.default_rng(SEED)
    for g in gs:
        if hasattr(g, "node_ip_int"):
            v = g.node_ip_int
            g.node_ip_int = v[torch.from_numpy(rng.permutation(len(v)))]
    return gs


VARIANTS = [
    ("full",           v_full,          "baseline"),
    ("no_edge_feat",   v_no_edge_feat,  "20 flow features zeroed"),
    ("no_ports",       v_no_ports,      "port/proto tokens flattened"),
    ("no_flow_info",   v_no_flow_info,  "nothing left about the flow"),
    ("no_node_feat",   v_no_node_feat,  "16 node features zeroed"),
    ("topology_only",  v_topology_only, "only the graph shape survives"),
    ("global_shuffle", v_global_shuffle, "features permuted across windows"),
    ("rewired",        v_rewired,       "topology destroyed, features kept"),
    ("ip_permuted",    v_ip_permuted,   "node identities remapped"),
]


def score(gs):
    model.reset_memory()
    ys, ps = [], []
    with torch.no_grad():
        for g in gs:
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
    y = np.concatenate(ys)
    p = np.vstack(ps)
    return multiclass_metrics(y, p.argmax(1), p, "edge_")


print(f"\n{BAR}\n  INFORMATION-SOURCE ABLATION  (edge head, test split)\n{BAR}")
rows = {}
for name, fn, note in VARIANTS:
    m = score(fn(clone_all(TEST)))
    rows[name] = m
    print(f"  {name:<16s} macroF1 {m.get('edge_macro_f1', 0):.4f}   "
          f"binaryF1 {m.get('edge_binary_f1', 0):.4f}   ({note})")

base = rows["full"]["edge_macro_f1"]
print(f"\n{BAR}\n  PER-CLASS F1 UNDER EACH ABLATION\n{BAR}")
hdr = f"  {'variant':<16s}" + "".join(f"{c[:9]:>11s}" for c in CLASS_NAMES) + f"{'MACRO':>9s}{'delta':>9s}"
print(hdr)
for name, _, _ in VARIANTS:
    m = rows[name]
    line = f"  {name:<16s}"
    for c in CLASS_NAMES:
        line += f"{m.get(f'edge_f1_{c}', float('nan')):>11.4f}"
    mf = m.get("edge_macro_f1", float("nan"))
    line += f"{mf:>9.4f}{mf - base:>+9.4f}"
    print(line)

# ------------------------------------------------------------- verdict ------
print(f"\n{BAR}\n  WHAT THIS MEANS\n{BAR}")


def drop(name):
    return base - rows[name]["edge_macro_f1"]


checks = [
    ("flow features", "no_flow_info",
     "the model reads the flow itself (features, ports, protocol)",
     "the flow content is DECORATIVE -- the model is not using it"),
    ("topology", "rewired",
     "the graph structure carries real signal",
     "message passing is decorative -- a per-flow classifier would do the same"),
    ("node features", "no_node_feat",
     "the aggregated host features matter",
     "node features are not being used"),
    ("host identity", "ip_permuted",
     "performance depends on WHICH hosts these are -- memorisation risk",
     "the model does not depend on specific host identities (good)"),
]
for label, key, if_drops, if_flat in checks:
    d = drop(key)
    verdict = if_drops if d > 0.05 else if_flat
    print(f"  {label:<16s} drop {d:>+7.4f}   {verdict}")

print()
gs_drop = drop("global_shuffle")
if gs_drop <= 0.05:
    print("  !! THE PROPER GLOBAL SHUFFLE ALSO DID NOT COLLAPSE.")
    print("     Permuting every edge's features across the whole test set left")
    print("     macro F1 essentially unchanged. The model is then classifying")
    print("     from topology and node context alone. Given that four of five")
    print("     attack families in this capture are the SAME (source, victim)")
    print("     pair, the most likely explanation is that it has learned which")
    print("     host pair each attack lives on -- which will not transfer to any")
    print("     other network. Do not report flow-level classification as the")
    print("     contribution until the RandomForest baseline and a host-holdout")
    print("     split have been run.")
else:
    print(f"  The proper global shuffle costs {gs_drop:+.4f} macro F1, so the")
    print("  model IS reading its edge features. The threshold study's weaker")
    print("  within-window control was simply degenerate on class-homogeneous")
    print("  windows and should be replaced by this table in the write-up.")

print(f"\n  Quote the table, not one number. 'topology_only' is the floor: any")
print(f"  score it reaches is available without looking at the traffic at all.")
