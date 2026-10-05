"""
Focal loss with class-balanced alpha, degree-aware reweighting, and a
node/edge consistency term. Standard cross-entropy is gone entirely.

Why the old setup could not work. Scalar class weights (~1.59 malicious,
~0.72 benign) multiply the gradient of every sample in a class by a constant.
That treats a 200 000-flow DDoS burst and a 1 500-flow botnet beacon as equally
informative once they are both "malicious" -- so the optimiser takes the cheap
win, nails the volumetric attacks, and leaves the stealthy ones unlearned while
the aggregate F1 still looks respectable.

Focal loss reweights per *sample*, by how wrong the model currently is:

    FL(p_t) = -alpha_t (1 - p_t)^gamma log(p_t)

An easy DDoS node at p_t = 0.99 contributes (0.01)^2 = 1e-4 of its usual
gradient. A botnet node the model is guessing at p_t = 0.5 keeps 0.25 of its
gradient -- 2 500x more attention per sample. The optimiser is forced onto the
hard minority rather than being allowed to buy F1 with the easy majority.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def effective_number_alpha(
    class_counts: Sequence[int], beta: float = 0.9999, normalise: bool = True
) -> torch.Tensor:
    """Class-balanced weights from Cui et al., 2019.

    ``(1 - beta) / (1 - beta^n)`` rather than ``1/n``. With hundreds of
    thousands of DDoS samples, plain inverse frequency produces a weight so
    small it effectively deletes the class; the effective-number formulation
    saturates instead, because the 200 000th near-duplicate DDoS flow carries
    almost no new information but is not worthless either.
    """
    counts = np.asarray(class_counts, dtype=np.float64)
    counts = np.maximum(counts, 1.0)
    eff = (1.0 - np.power(beta, counts)) / (1.0 - beta)
    w = 1.0 / eff
    if normalise:
        w = w / w.sum() * len(w)
    return torch.tensor(w, dtype=torch.float32)


class FocalLoss(nn.Module):
    """Multi-class focal loss with optional per-sample weights."""

    def __init__(
        self,
        alpha: Optional[torch.Tensor] = None,
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
        reduction: str = "mean",
    ):
        super().__init__()
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        if alpha is not None:
            self.register_buffer("alpha", alpha)
        else:
            self.alpha = None

    def forward(
        self,
        logits: torch.Tensor,
        target: torch.Tensor,
        sample_weight: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        log_p = F.log_softmax(logits, dim=-1)
        if self.label_smoothing > 0:
            n = logits.size(-1)
            eps = self.label_smoothing
            true_dist = torch.full_like(log_p, eps / (n - 1))
            true_dist.scatter_(1, target.unsqueeze(1), 1.0 - eps)
            ce = -(true_dist * log_p).sum(dim=-1)
        else:
            ce = F.nll_loss(log_p, target, reduction="none")

        with torch.no_grad():
            p_t = log_p.gather(1, target.unsqueeze(1)).squeeze(1).exp()
            focal = (1.0 - p_t).clamp(min=0).pow(self.gamma)

        loss = focal * ce
        if self.alpha is not None:
            loss = loss * self.alpha.to(logits.device)[target]
        if sample_weight is not None:
            loss = loss * sample_weight

        if self.reduction == "mean":
            denom = (
                sample_weight.sum().clamp(min=1e-6)
                if sample_weight is not None
                else loss.numel()
            )
            return loss.sum() / denom
        if self.reduction == "sum":
            return loss.sum()
        return loss


def degree_weights(
    edge_index: torch.Tensor, num_nodes: int, rho: float = 0.5, clamp: float = 5.0
) -> torch.Tensor:
    """Per-node weights that stop hubs from owning the loss.

    A DDoS victim with 50 000 incident flows and a quiet workstation with 3 are
    both exactly one node in the node-level loss -- but the hub's embedding is
    the average of a huge neighbourhood, so it is easy, confident, and would
    otherwise dominate through sheer numbers of similar hub nodes. Weighting by
    ``deg^-rho`` restores the low-degree hosts (beacons, slow scanners) to a
    comparable share of the gradient.
    """
    deg = torch.bincount(edge_index[0], minlength=num_nodes).float()
    deg += torch.bincount(edge_index[1], minlength=num_nodes).float()
    deg = deg.clamp(min=1.0)
    w = deg.pow(-rho)
    w = w / w.mean().clamp(min=1e-6)
    return w.clamp(max=clamp)


class GraphAwareLoss(nn.Module):
    """Node focal + edge focal + degree reweighting + node/edge consistency.

    The consistency term is the graph-aware piece: a host predicted benign
    while one of its own flows is predicted DDoS is an internally incoherent
    answer, and an SOC analyst receiving it cannot act. Penalising the
    disagreement pushes the two heads to agree on the same story.
    """

    def __init__(
        self,
        node_alpha: Optional[torch.Tensor] = None,
        edge_alpha: Optional[torch.Tensor] = None,
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
        edge_weight: float = 0.5,
        degree_penalty_weight: float = 0.05,
        degree_rho: float = 0.5,
        consistency_weight: float = 0.05,
    ):
        super().__init__()
        self.node_loss = FocalLoss(node_alpha, gamma, label_smoothing)
        self.edge_loss = FocalLoss(edge_alpha, gamma, label_smoothing)
        self.edge_weight = edge_weight
        self.degree_penalty_weight = degree_penalty_weight
        self.degree_rho = degree_rho
        self.consistency_weight = consistency_weight

    def forward(self, out: dict, data) -> dict:
        parts: dict = {}
        total = out.get("node_logits", out.get("edge_logits")).new_zeros(())

        if "node_logits" in out and hasattr(data, "y"):
            w = None
            if self.degree_penalty_weight > 0:
                w = degree_weights(
                    data.edge_index, data.num_nodes, self.degree_rho
                ).to(out["node_logits"].device)
                w = 1.0 + self.degree_penalty_weight * (w - 1.0)
            ln = self.node_loss(out["node_logits"], data.y, w)
            parts["node"] = ln
            total = total + ln

        if "edge_logits" in out and hasattr(data, "edge_y"):
            mask = getattr(data, "real_edge_mask", None)
            logits, targets = out["edge_logits"], data.edge_y
            if mask is not None:
                logits, targets = logits[mask], targets[mask]
            le = self.edge_loss(logits, targets)
            parts["edge"] = le
            total = total + self.edge_weight * le

        if (
            self.consistency_weight > 0
            and "node_logits" in out
            and "edge_logits" in out
        ):
            node_p = F.softmax(out["node_logits"], dim=-1)
            edge_p = F.softmax(out["edge_logits"], dim=-1)
            src = data.edge_index[0]
            # a flow's threat should not exceed what either endpoint admits to
            edge_threat = 1.0 - edge_p[:, 0]
            node_threat = 1.0 - node_p[:, 0]
            gap = F.relu(edge_threat - node_threat[src]).mean()
            parts["consistency"] = gap
            total = total + self.consistency_weight * gap

        parts["total"] = total
        return parts


def build_loss(cfg, node_counts, edge_counts) -> GraphAwareLoss:
    lc = cfg.loss
    alpha = (
        torch.tensor(lc.focal_alpha, dtype=torch.float32)
        if lc.focal_alpha
        else effective_number_alpha(node_counts, lc.effective_number_beta)
    )
    edge_alpha = effective_number_alpha(edge_counts, lc.effective_number_beta)
    return GraphAwareLoss(
        node_alpha=alpha,
        edge_alpha=edge_alpha,
        gamma=lc.focal_gamma,
        label_smoothing=lc.label_smoothing,
        edge_weight=lc.edge_loss_weight,
        degree_penalty_weight=lc.degree_penalty_weight,
    )
