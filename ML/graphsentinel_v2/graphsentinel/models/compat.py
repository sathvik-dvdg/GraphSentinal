"""
Backward-compatibility shim for the frozen ``in_channels=7`` contract.

The old notebook hard-coded ``GraphSAGEClassifier`` with a raise on any
``in_channels != 7`` because the backend did ``from model import
GraphSAGEClassifier``. That coupling meant no architecture change was possible
without breaking a teammate's service -- the ML work was pinned by an import
statement.

This file exists so the migration is not a flag day:

  * ``GraphSAGEClassifier`` still exists, still has the same name and defaults,
    still loads v1 weights. Nothing crashes on import.
  * It emits a DeprecationWarning pointing at the v2 inference service.
  * ``LegacyBinaryAdapter`` wraps a v2 model and exposes the v1 method names
    (``predict_proba`` -> per-node malicious probability), so a backend can move
    to the new model in one line before moving to the service properly.

The real decoupling is in ``graphsentinel/export.py`` and
``graphsentinel/inference/service.py``: the backend should speak HTTP/JSON to
an inference service and never import a Python class at all.
"""
from __future__ import annotations

import warnings
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

_DEPRECATION = (
    "GraphSAGEClassifier is the v1 architecture and is frozen for "
    "backward compatibility only. It treats flows as nodes, normalises ports as "
    "floats, and cannot emit per-flow SDN rules. Migrate to the v2 inference "
    "service (graphsentinel.inference.service) or load GraphSentinelNet directly."
)


class GraphSAGEClassifier(nn.Module):
    """v1 architecture, preserved verbatim so old checkpoints still load."""

    def __init__(
        self,
        in_channels: int = 7,
        hidden_channels: int = 256,
        out_channels: int = 2,
        num_layers: int = 3,
        dropout: float = 0.3,
        aggr: str = "mean",
        warn: bool = True,
    ):
        super().__init__()
        if warn:
            warnings.warn(_DEPRECATION, DeprecationWarning, stacklevel=2)
        # NOTE: the v1 ValueError on in_channels != 7 is deliberately removed.
        # It was the mechanism that froze the contract in the first place.
        self.num_layers = num_layers
        self.dropout = dropout
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        self.convs.append(SAGEConv(in_channels, hidden_channels, aggr=aggr))
        self.bns.append(nn.BatchNorm1d(hidden_channels))
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels, aggr=aggr))
            self.bns.append(nn.BatchNorm1d(hidden_channels))
        self.convs.append(SAGEConv(hidden_channels, out_channels, aggr=aggr))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        for conv, bn in zip(self.convs[:-1], self.bns):
            x = F.dropout(F.relu(bn(conv(x, edge_index))), p=self.dropout, training=self.training)
        return self.convs[-1](x, edge_index)

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.forward(x, edge_index), dim=1)[:, 1]

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class LegacyBinaryAdapter(nn.Module):
    """Expose a v2 model through the v1 method surface.

    ``predict_proba`` returns ``1 - P(BENIGN)`` per node, which is what the old
    backend thresholded at 0.75. The multi-class detail is available through
    ``predict_full`` when the backend is ready for it.
    """

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    @torch.no_grad()
    def predict_proba(self, data, now: Optional[int] = None) -> torch.Tensor:
        out = self.model.predict(data, now)
        return out["node_threat"]

    @torch.no_grad()
    def predict_full(self, data, now: Optional[int] = None) -> dict:
        return self.model.predict(data, now)

    def forward(self, *args, **kwargs):
        return self.model(*args, **kwargs)
