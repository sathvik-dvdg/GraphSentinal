"""
Evaluation.

Reported metrics changed on purpose. The v1 targets were accuracy >= 0.92,
weighted F1 >= 0.88 and ROC-AUC >= 0.95 -- all three of which a model can hit
while completely failing at the job:

  * ACCURACY on a 69/31 split is beaten by "predict benign" plus a little luck.
  * WEIGHTED F1 weights each class by its support, so DoS Hulk (167k rows) is
    worth 111x Botnet (1.5k rows). A model that never once detects a botnet can
    still post 0.95.
  * ROC-AUC is computed over the whole threshold range including regions no
    SOC would ever operate in, and is famously optimistic under heavy class
    imbalance.

What is reported instead:
  * MACRO F1 and PER-CLASS F1 -- botnet failure is visible, not averaged away.
  * PR-AUC (average precision) per class -- the right curve when positives are
    rare.
  * Recall at a fixed false-positive budget -- the number an analyst actually
    lives with, since 1 % FPR on 250k flows/hour is 2 500 false alerts/hour.
  * Edge-level metrics, because the SDN rule is written from the edge head.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)

from .config import CLASS_NAMES


def _to_numpy(x) -> np.ndarray:
    return x.detach().cpu().numpy() if isinstance(x, torch.Tensor) else np.asarray(x)


def recall_at_fpr(y_true_bin: np.ndarray, scores: np.ndarray, max_fpr: float) -> float:
    """Detection rate when false alerts are capped at ``max_fpr``.

    This is the operational number: everything above the threshold becomes a
    ticket, and an analyst team has a fixed number of tickets per hour.
    """
    if y_true_bin.sum() == 0 or (1 - y_true_bin).sum() == 0:
        return float("nan")
    order = np.argsort(-scores)
    y = y_true_bin[order]
    n_neg = int((1 - y_true_bin).sum())
    budget = max(int(max_fpr * n_neg), 1)
    fp = np.cumsum(1 - y)
    cut = np.searchsorted(fp, budget, side="right")
    return float(y[:cut].sum() / max(y_true_bin.sum(), 1))


def multiclass_metrics(
    y_true, y_pred, y_prob, prefix: str = "", class_names: Optional[List[str]] = None
) -> Dict[str, float]:
    y_true, y_pred = _to_numpy(y_true), _to_numpy(y_pred)
    y_prob = _to_numpy(y_prob)
    names = class_names or CLASS_NAMES
    n = len(names)

    # Macro F1 over the classes actually PRESENT in the ground truth. Averaging
    # over all six when the split only contains two turns a meaningless 1.0 into
    # a headline number -- and averaging over all six when the model simply
    # never predicts a class hides that failure behind the classes it does get.
    present = sorted(set(np.unique(y_true).tolist()))
    out: Dict[str, float] = {
        f"{prefix}macro_f1": float(
            f1_score(y_true, y_pred, average="macro", labels=present, zero_division=0)
        ),
        f"{prefix}macro_f1_all_classes": float(
            f1_score(y_true, y_pred, average="macro", labels=list(range(n)), zero_division=0)
        ),
        f"{prefix}classes_present": float(len(present)),
        f"{prefix}weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        f"{prefix}accuracy": float((y_true == y_pred).mean()),
    }

    per_class = f1_score(y_true, y_pred, average=None, labels=range(n), zero_division=0)
    for i, name in enumerate(names):
        out[f"{prefix}f1_{name}"] = float(per_class[i])

    # binary view: anything not BENIGN
    y_bin = (y_true > 0).astype(int)
    threat = 1.0 - y_prob[:, 0] if y_prob.ndim == 2 else y_prob
    if y_bin.sum() > 0 and (1 - y_bin).sum() > 0:
        out[f"{prefix}binary_pr_auc"] = float(average_precision_score(y_bin, threat))
        out[f"{prefix}binary_roc_auc"] = float(roc_auc_score(y_bin, threat))
        out[f"{prefix}recall_at_fpr_0.01"] = recall_at_fpr(y_bin, threat, 0.01)
        out[f"{prefix}recall_at_fpr_0.001"] = recall_at_fpr(y_bin, threat, 0.001)
    out[f"{prefix}binary_f1"] = float(
        f1_score(y_bin, (_to_numpy(y_pred) > 0).astype(int), zero_division=0)
    )

    # per-class PR-AUC (one-vs-rest)
    if y_prob.ndim == 2 and y_prob.shape[1] == n:
        for i, name in enumerate(names[1:], start=1):
            pos = (y_true == i).astype(int)
            if pos.sum() > 0:
                out[f"{prefix}pr_auc_{name}"] = float(
                    average_precision_score(pos, y_prob[:, i])
                )
    return out


@torch.no_grad()
def run_inference(model, graphs, device, use_memory: bool = True):
    """Chronological pass over windows, collecting node and edge predictions."""
    model.eval()
    node_true, node_pred, node_prob = [], [], []
    edge_true, edge_pred, edge_prob = [], [], []

    for data in graphs:
        data = data.to(device)
        out = model.step_with_memory(data, now=int(getattr(data, "window_end", 0)))

        if "node_logits" in out:
            p = torch.softmax(out["node_logits"].float(), dim=-1)
            node_prob.append(p.cpu())
            node_pred.append(p.argmax(-1).cpu())
            node_true.append(data.y.cpu())

        if "edge_logits" in out:
            mask = getattr(data, "real_edge_mask", None)
            logits = out["edge_logits"].float()
            ey = data.edge_y
            if mask is not None:
                logits, ey = logits[mask], ey[mask]
            pe = torch.softmax(logits, dim=-1)
            edge_prob.append(pe.cpu())
            edge_pred.append(pe.argmax(-1).cpu())
            edge_true.append(ey.cpu())

    cat = lambda xs: torch.cat(xs).numpy() if xs else np.zeros(0)  # noqa: E731
    return {
        "node_true": cat(node_true),
        "node_pred": cat(node_pred),
        "node_prob": torch.cat(node_prob).numpy() if node_prob else np.zeros((0, 1)),
        "edge_true": cat(edge_true),
        "edge_pred": cat(edge_pred),
        "edge_prob": torch.cat(edge_prob).numpy() if edge_prob else np.zeros((0, 1)),
    }


def evaluate_model(model, graphs, device) -> Dict[str, float]:
    res = run_inference(model, graphs, device)
    metrics: Dict[str, float] = {}
    if len(res["node_true"]):
        metrics.update(
            multiclass_metrics(res["node_true"], res["node_pred"], res["node_prob"], "node_")
        )
    if len(res["edge_true"]):
        metrics.update(
            multiclass_metrics(res["edge_true"], res["edge_pred"], res["edge_prob"], "edge_")
        )
    return metrics


def full_report(model, graphs, device) -> dict:
    res = run_inference(model, graphs, device)
    report = {"metrics": {}}
    for kind in ("node", "edge"):
        yt, yp, pr = res[f"{kind}_true"], res[f"{kind}_pred"], res[f"{kind}_prob"]
        if not len(yt):
            continue
        report["metrics"].update(multiclass_metrics(yt, yp, pr, f"{kind}_"))
        report[f"{kind}_confusion"] = confusion_matrix(
            yt, yp, labels=list(range(len(CLASS_NAMES)))
        ).tolist()
        report[f"{kind}_classification_report"] = classification_report(
            yt, yp, labels=list(range(len(CLASS_NAMES))),
            target_names=CLASS_NAMES, zero_division=0, output_dict=True,
        )
    return report


# --------------------------------------------------------------------------
# Open-set metrics
# --------------------------------------------------------------------------
def fpr_at_tpr(y_ood: np.ndarray, score: np.ndarray, target_tpr: float = 0.95) -> float:
    """False-positive rate at the threshold that catches ``target_tpr`` of unknowns.

    The standard OOD operating-point metric. AUROC averages over thresholds no
    SOC would ever run at; this reports the cost at the one you would.
    """
    y_ood = np.asarray(y_ood).astype(bool)
    score = np.asarray(score, dtype=np.float64)
    pos, neg = score[y_ood], score[~y_ood]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    thr = np.quantile(pos, 1.0 - target_tpr)
    return float((neg >= thr).mean())


def oscr_curve(
    known_correct: np.ndarray, known_score: np.ndarray, unknown_score: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Open Set Classification Rate curve (Dhamija et al., 2018).

    Sweeps the rejection threshold and reports, jointly:

      CCR  fraction of KNOWN samples that are both accepted AND classified
           correctly -- so rejecting knowns to look safe is penalised
      FPR  fraction of UNKNOWN samples wrongly accepted

    This is the metric that closed-set F1 and OOD AUROC each miss half of. A
    detector can post excellent OOD AUROC while rejecting so aggressively that
    it stops classifying known attacks; OSCR makes that visible.

    Returns (fpr, ccr, oscr_auc). Score convention: HIGH = more out-of-
    distribution, so a sample is accepted when score <= threshold.
    """
    known_score = np.asarray(known_score, dtype=np.float64)
    unknown_score = np.asarray(unknown_score, dtype=np.float64)
    known_correct = np.asarray(known_correct).astype(bool)
    if known_score.size == 0 or unknown_score.size == 0:
        return np.zeros(0), np.zeros(0), float("nan")

    thresholds = np.unique(np.concatenate([known_score, unknown_score]))
    thresholds = np.concatenate([[-np.inf], thresholds, [np.inf]])

    n_k, n_u = len(known_score), len(unknown_score)
    ccr = np.empty(len(thresholds))
    fpr = np.empty(len(thresholds))
    for i, t in enumerate(thresholds):
        ccr[i] = np.sum(known_correct & (known_score <= t)) / n_k
        fpr[i] = np.sum(unknown_score <= t) / n_u

    order = np.argsort(fpr)
    fpr, ccr = fpr[order], ccr[order]
    return fpr, ccr, float(np.trapezoid(ccr, fpr))


def open_set_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ood_score: np.ndarray,
    unknown_label: int,
    prefix: str = "",
) -> Dict[str, float]:
    """Full open-set report for one held-out family."""
    y_true = _to_numpy(y_true)
    y_pred = _to_numpy(y_pred)
    ood_score = _to_numpy(ood_score).astype(np.float64)

    is_unknown = y_true == unknown_label
    is_known = ~is_unknown
    if is_unknown.sum() == 0 or is_known.sum() == 0:
        return {}

    known_correct = (y_pred == y_true)[is_known]
    fpr, ccr, oscr = oscr_curve(known_correct, ood_score[is_known], ood_score[is_unknown])

    # ID vs OOD separation, restricted to BENIGN vs the unknown family: the
    # question an analyst actually faces is whether novel traffic is
    # distinguishable from the background, not from other attacks.
    benign_vs_unknown = (y_true == 0) | is_unknown
    yb = is_unknown[benign_vs_unknown].astype(int)
    sb = ood_score[benign_vs_unknown]

    out = {
        f"{prefix}oscr_auc": oscr,
        f"{prefix}fpr_at_95tpr": fpr_at_tpr(is_unknown, ood_score, 0.95),
        f"{prefix}fpr_at_80tpr": fpr_at_tpr(is_unknown, ood_score, 0.80),
        f"{prefix}closed_set_acc_on_knowns": float(known_correct.mean()),
    }
    if yb.sum() > 0 and (1 - yb).sum() > 0:
        out[f"{prefix}ood_auroc"] = float(roc_auc_score(yb, sb))
        out[f"{prefix}ood_ap"] = float(average_precision_score(yb, sb))
        out[f"{prefix}ood_fpr_at_95tpr_vs_benign"] = fpr_at_tpr(yb.astype(bool), sb, 0.95)
    return out


@torch.no_grad()
def collect_embeddings(model, graphs, device):
    """Logits, JK embeddings and labels for every node, in window order."""
    model.eval()
    model.reset_memory()
    L, E, Y = [], [], []
    for g in graphs:
        g = g.to(device)
        out = model.step_with_memory(g, now=int(getattr(g, "window_end", 0)))
        L.append(out["node_logits"].float().cpu())
        E.append(out["node_embedding"].float().cpu())
        Y.append(g.y.cpu())
    return (
        torch.cat(L).numpy() if L else np.zeros((0, 1)),
        torch.cat(E).numpy() if E else np.zeros((0, 1)),
        torch.cat(Y).numpy() if Y else np.zeros(0),
    )


@torch.no_grad()
def evasion_ablation(model, graphs, device, volumetric_idx: List[int]) -> dict:
    """How much does the model lose when volumetric features are neutralised?

    Attackers control ``Flow Bytes/s`` and ``Flow Duration`` directly -- rate
    limit the payload, fragment the packets, and those columns say whatever the
    attacker wants. This zeroes them and re-measures. A model that collapses
    here was reading spoofable headers; a model that mostly holds is reading
    topology, which an attacker cannot fake without giving up the attack (a
    port scan that does not contact many ports is not a port scan).
    """
    import copy

    baseline = evaluate_model(model, graphs, device)
    ablated_graphs = []
    for g in graphs:
        g2 = copy.copy(g)
        ea = g.edge_attr.clone()
        ea[:, volumetric_idx] = 0.0
        g2.edge_attr = ea
        ablated_graphs.append(g2)
    ablated = evaluate_model(model, ablated_graphs, device)

    keys = ["node_macro_f1", "edge_macro_f1", "node_binary_pr_auc", "edge_binary_pr_auc"]
    delta = {
        k: float(ablated.get(k, np.nan) - baseline.get(k, np.nan))
        for k in keys
        if k in baseline
    }
    return {"baseline": baseline, "ablated": ablated, "delta": delta}


# --------------------------------------------------------------------------
# Per-class logit adjustment
# --------------------------------------------------------------------------
def fit_logit_adjustment(
    y_true: np.ndarray,
    prob: np.ndarray,
    n_classes: int,
    rounds: int = 4,
    grid: int = 33,
    span: float = 8.0,
    max_class_drop: float = 0.05,
    holdout_frac: float = 0.4,
    min_gain: float = 0.02,
    min_holdout_per_class: int = 200,
    seed: int = 0,
    verbose: bool = False,
) -> np.ndarray:
    """Per-class log-space offsets that fix an argmax the ranking already got
    right -- fitted on one half of validation and KEPT ONLY IF they hold up on
    the other half.

    WHY OFFSETS AT ALL. A class can be well separated and still never win the
    argmax. Measured 2026-08-29: DoSHulk edge PR-AUC 0.7813 with F1 exactly
    0.0000, every one of its edges labelled DDoS. Good ranking, wrong boundary.

    WHY THE HOLDOUT. Version 1 optimised macro F1 with no floor and traded a
    working class for two zeros (DDoS 0.5404 -> 0.1183). Version 2 added a
    per-class floor -- but enforced it on the data it was fitting, which is no
    protection at all. On the 2026-08-29 (5th) run that produced:

        SSHBrute  0.8647 -> 0.2308   (-0.63 on TEST, while val looked fine)
        MACRO     0.5955 -> 0.5865   (the "improvement" was negative)

    Offsets fitted on validation had simply overfitted it. So the fit now runs
    on `1 - holdout_frac` of validation and is scored on the rest. If the
    held-out half does not improve, or any class collapses there, the offsets
    are DISCARDED and zeros are returned -- meaning plain argmax, unchanged.

    OTHER CONSTRAINTS:
      * validation only, never test;
      * the held-out gain must clear `min_gain`, because a bare "positive"
        is within the noise of a random split;
      * BENIGN (index 0) pinned at zero, so this cannot buy attack recall by
        biasing the model away from benign;
      * stored in the checkpoint and model card, so the backend reproduces the
        reported numbers exactly.
    """
    from sklearn.metrics import f1_score

    y_true = np.asarray(y_true).astype(int)
    labels = list(range(n_classes))
    rng = np.random.default_rng(seed)

    # stratified halves, so a rare class is present on both sides
    fit_idx, chk_idx = [], []
    for c in labels:
        idx = np.flatnonzero(y_true == c)
        if idx.size == 0:
            continue
        rng.shuffle(idx)
        cut = max(1, int(round(idx.size * (1.0 - holdout_frac))))
        fit_idx.append(idx[:cut])
        chk_idx.append(idx[cut:])
    fit_idx = np.concatenate(fit_idx) if fit_idx else np.arange(len(y_true))
    chk_idx = np.concatenate(chk_idx) if chk_idx else np.arange(len(y_true))
    if chk_idx.size < n_classes * 2:          # too little to check on
        chk_idx = fit_idx

    # A class with only a handful of held-out examples cannot be measured: its
    # F1 there is estimated from a few dozen samples and swings wildly. On the
    # 2026-08-29 (6th) run the held-out half held ~18 Botnet edges, the gate
    # passed at +0.0467, and Botnet still went 0.1398 -> 0.0000 on test.
    support = np.bincount(y_true[chk_idx], minlength=n_classes)
    thin = [c for c in range(n_classes)
            if 0 < support[c] < min_holdout_per_class]
    if thin:
        if verbose:
            names = ", ".join(f"class {c} (n={support[c]})" for c in thin)
            print(f"    offsets DISCARDED: too few held-out examples to measure "
                  f"-- {names}; need {min_holdout_per_class}")
        return np.zeros(n_classes, dtype=np.float64)

    logp = np.log(np.clip(prob, 1e-12, None))

    def per_class(b, idx):
        pred = (logp[idx] + b).argmax(1)
        return np.asarray(f1_score(y_true[idx], pred, average=None,
                                   labels=labels, zero_division=0))

    zero = np.zeros(n_classes, dtype=np.float64)
    base_fit = per_class(zero, fit_idx)
    bias, best = zero.copy(), float(base_fit.mean())

    def score(b):
        f = per_class(b, fit_idx)
        if np.any(f < base_fit - max_class_drop):     # no class may collapse
            return -np.inf
        return float(f.mean())

    step = span
    for _ in range(rounds):
        for c in range(1, n_classes):                 # BENIGN stays pinned
            base = bias[c]
            for delta in np.linspace(-step, step, grid):
                trial = bias.copy()
                trial[c] = base + delta
                sc = score(trial)
                if sc > best:
                    best, bias = sc, trial
        step /= 3.0

    # ---- the gate: does it survive data it was NOT fitted on? -------------
    chk_before = per_class(zero, chk_idx)
    chk_after = per_class(bias, chk_idx)
    gain = float(chk_after.mean() - chk_before.mean())
    worst = float((chk_after - chk_before).min())

    if verbose:
        print(f"    offsets: held-out macro F1 {chk_before.mean():.4f} -> "
              f"{chk_after.mean():.4f} ({gain:+.4f}), worst class {worst:+.4f}")

    # `gain > 0` is too weak: on pure noise the held-out half still swings by
    # +/-0.01 by chance, so a bare positive would keep offsets that mean
    # nothing. Requiring a MEANINGFUL gain also matches the honest framing --
    # an extra post-processing step the backend must reproduce has to earn its
    # place, and +0.0008 does not.
    if gain < min_gain or worst < -max_class_drop:
        if verbose:
            reason = (f"held-out gain {gain:+.4f} below the {min_gain:.2f} "
                      f"threshold" if gain < min_gain
                      else f"a class fell {-worst:.4f} on held-out data")
            print(f"    offsets DISCARDED ({reason}) -- using plain argmax")
        return zero

    return bias


def apply_logit_adjustment(prob: np.ndarray, bias: np.ndarray) -> np.ndarray:
    """Argmax of log-probabilities plus the fitted per-class bias."""
    if bias is None:
        return prob.argmax(1)
    return (np.log(np.clip(prob, 1e-12, None)) + bias).argmax(1)


def adjusted_metrics(y_true, prob, bias, prefix: str, n_classes: int) -> dict:
    """Metrics after adjustment. Ranking metrics are unchanged by construction
    (an additive bias cannot reorder a single class's scores), so only the
    argmax-dependent ones move -- which is the honest way to report this."""
    pred = apply_logit_adjustment(prob, bias)
    return multiclass_metrics(y_true, pred, prob, prefix)
