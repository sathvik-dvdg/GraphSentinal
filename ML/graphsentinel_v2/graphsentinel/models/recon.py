"""
Graph-native self-supervised heads, trained jointly with the classifier.

    L_total = L_focal + lambda * (w_e L_edge + w_l L_link + w_n L_node)

WHY THESE THREE TASKS AND NOT OTHERS

The selection criterion is not "is it a standard SSL objective" but: **does
solving it require information the focal objective does not already need?** An
auxiliary task that is predictable from the class label alone anchors nothing --
it just adds a second way to compute what the head already computes.

Against that criterion, for the specific failure being targeted (a botnet
beacon collapsing into BENIGN):

  EDGE  masked edge-attribute reconstruction        PRIMARY
        Mask 15% of flows, zero their attributes before message passing, then
        reconstruct them from the two endpoint embeddings plus the port and
        protocol tokens. To solve it, h_u must encode *what kind of traffic
        this host emits* at feature resolution -- small, regular, fixed-port,
        low-volume -- which is exactly the beacon signature. Not class-
        redundant: BENIGN spans wildly different edge profiles, so knowing the
        label tells you almost nothing about the answer.

        Masking BEFORE encoding is essential. Edge attributes are fed to
        GATv2 as edge features, so an unmasked edge can be copied straight
        through attention and the task becomes an identity map.

  LINK  degree-matched neighbourhood reconstruction  SECONDARY
        Predict whether a node pair communicates, against negatives sampled to
        match the positive degree distribution. Forces peer-set identity into
        the embedding, which is the many-to-one C2 topology itself.

        The degree matching is what makes this non-trivial. Uniform negative
        sampling in a network graph is solved perfectly by degree alone -- a
        hub is in most positive pairs -- so the task would collapse to
        "predict degree" and teach the encoder nothing new.

  NODE  structural-profile reconstruction            STABILISER, low weight
        Decode the node's own 16 structural features from its embedding. The
        cheapest anti-collapse anchor, and the most class-redundant of the
        three (a DDoS victim's high in-degree IS its label), so it carries the
        smallest weight. Included because it stabilises early training, not
        because it adds much signal.

REJECTED, and why:

  Next-window forecasting from the memory state is the strongest *temporal*
  candidate and the only thing that would supervise the GRU directly -- a
  beacon is periodic and therefore highly predictable. It needs a second
  forward pass and cross-window gradient plumbing, so it is phase two, not
  phase one.

  Node2vec / random-walk objectives encode community structure, which in a
  network graph is dominated by subnet topology -- almost pure nuisance
  variance for this task.

  Contrastive augmentation (edge dropping, feature jitter) assumes the
  augmentation preserves semantics. Dropping edges from a port scan can turn
  it into benign traffic, so the positive pair is not actually a positive.

WHERE THE HEADS ATTACH

All three decode from the **JK concatenation** -- the same vector the OOD
scorer reads. Anchoring only the final layer would leave the scored
representation unregularised, which would make the whole exercise pointless.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class ReconstructionHeads(nn.Module):
    def __init__(
        self,
        jk_dim: int,
        node_in: int,
        edge_in: int,
        edge_cat_dim: int,
        hidden: int = 128,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.edge_decoder = nn.Sequential(
            nn.Linear(2 * jk_dim + edge_cat_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, edge_in),
        )
        self.link_decoder = nn.Sequential(
            nn.Linear(3 * jk_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )
        self.node_decoder = nn.Sequential(
            nn.Linear(jk_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Linear(hidden, node_in),
        )
        # Learned [MASK] token, as in masked language modelling -- a zero vector
        # is a legitimate feature value here, so it cannot double as the mask.
        self.mask_token = nn.Parameter(torch.zeros(edge_in))
        nn.init.normal_(self.mask_token, std=0.02)

    # ------------------------------------------------------------------
    def edge_loss(
        self,
        h: torch.Tensor,
        edge_index: torch.Tensor,
        edge_cat: torch.Tensor,
        target: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        if mask.sum() == 0:
            return h.new_zeros(())
        src, dst = edge_index[0][mask], edge_index[1][mask]
        pred = self.edge_decoder(torch.cat([h[src], h[dst], edge_cat[mask]], dim=-1))
        # Smooth L1: edge attributes are log-scaled but still heavy-tailed, and
        # plain MSE lets a handful of large-volume flows own the gradient.
        return F.smooth_l1_loss(pred, target[mask])

    def link_loss(
        self,
        h: torch.Tensor,
        edge_index: torch.Tensor,
        num_nodes: int,
        generator: Optional[torch.Generator] = None,
    ) -> torch.Tensor:
        n_pos = edge_index.size(1)
        if n_pos == 0 or num_nodes < 3:
            return h.new_zeros(())
        src, dst = edge_index[0], edge_index[1]

        # Degree-matched negatives: resample sources from the observed source
        # distribution so the negative set has the same degree profile as the
        # positive set. Uniform sampling would make the task solvable by degree.
        idx = torch.randint(0, n_pos, (n_pos,), device=h.device, generator=generator)
        neg_src = src[idx]
        neg_dst = torch.randint(0, num_nodes, (n_pos,), device=h.device, generator=generator)
        keep = neg_dst != neg_src
        neg_src, neg_dst = neg_src[keep], neg_dst[keep]
        if neg_src.numel() == 0:
            return h.new_zeros(())

        def score(a, b):
            return self.link_decoder(torch.cat([h[a], h[b], h[a] * h[b]], dim=-1)).squeeze(-1)

        pos_logit, neg_logit = score(src, dst), score(neg_src, neg_dst)
        logits = torch.cat([pos_logit, neg_logit])
        labels = torch.cat([torch.ones_like(pos_logit), torch.zeros_like(neg_logit)])
        return F.binary_cross_entropy_with_logits(logits, labels)

    def node_loss(self, h: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return F.smooth_l1_loss(self.node_decoder(h), target)

    # ------------------------------------------------------------------
    def sample_edge_mask(
        self, n_edges: int, rate: float, device, generator: Optional[torch.Generator] = None
    ) -> torch.Tensor:
        mask = torch.zeros(n_edges, dtype=torch.bool, device=device)
        k = int(n_edges * rate)
        if k > 0:
            idx = torch.randperm(n_edges, device=device, generator=generator)[:k]
            mask[idx] = True
        return mask

    def apply_mask(self, edge_attr: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        out = edge_attr.clone()
        out[mask] = self.mask_token.to(edge_attr.dtype)
        return out


def recon_weight_schedule(
    epoch: int, total_epochs: int, base: float, warmup: int = 3, floor_frac: float = 0.2
) -> float:
    """Ramp up, then decay toward a floor.

    Reconstruction must not dominate early -- an untrained decoder produces
    enormous gradients that drown the classifier before it has learned anything.
    It must not dominate late either, or the encoder keeps spending capacity on
    reconstructing traffic instead of separating it. The floor is non-zero so
    the anchor never fully releases.
    """
    if epoch <= warmup:
        return base * epoch / max(warmup, 1)
    progress = (epoch - warmup) / max(total_epochs - warmup, 1)
    decayed = base * (floor_frac + (1 - floor_frac) * (1 - min(progress, 1.0)))
    return max(decayed, base * floor_frac)
