"""Building blocks: categorical encoders, edge encoder, robust conv factory."""
from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, SAGEConv
from torch_geometric.nn.aggr import MaxAggregation, MedianAggregation


class CategoricalEdgeEncoder(nn.Module):
    """Ports and protocol as learnable embeddings, not as normalised floats.

    ``port / 65535.0`` asserts that 22 and 23 are nearly identical and that 80
    and 8080 are far apart. The first is a false similarity (SSH vs Telnet are
    different attack surfaces), the second a false distance (both are HTTP).
    An embedding table imposes no geometry at all, so the model is free to
    place 80 and 8080 together if the traffic says they behave alike.
    """

    def __init__(
        self,
        edge_feat_dim: int,
        port_vocab: int,
        port_dim: int,
        proto_vocab: int,
        proto_dim: int,
        out_dim: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.dst_port_emb = nn.Embedding(port_vocab, port_dim, padding_idx=0)
        self.src_port_emb = nn.Embedding(port_vocab, port_dim, padding_idx=0)
        self.proto_emb = nn.Embedding(proto_vocab, proto_dim, padding_idx=0)

        in_dim = edge_feat_dim + 2 * port_dim + proto_dim
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(out_dim, out_dim),
        )
        nn.init.normal_(self.dst_port_emb.weight, std=0.02)
        nn.init.normal_(self.src_port_emb.weight, std=0.02)
        nn.init.normal_(self.proto_emb.weight, std=0.02)

    def forward(
        self,
        edge_attr: torch.Tensor,
        dst_port: torch.Tensor,
        src_port: torch.Tensor,
        proto: torch.Tensor,
    ) -> torch.Tensor:
        parts = [
            edge_attr,
            self.dst_port_emb(dst_port),
            self.src_port_emb(src_port),
            self.proto_emb(proto),
        ]
        return self.mlp(torch.cat(parts, dim=-1))


def make_conv(
    conv_type: str,
    in_dim: int,
    out_dim: int,
    heads: int,
    edge_dim: int,
    dropout: float,
) -> nn.Module:
    """Attention or robust aggregation -- never plain mean.

    ``mean`` suffers neighbourhood dilution: a host talking to one C2 server and
    99 benign web servers has its one informative neighbour averaged into
    irrelevance. GATv2 learns per-edge weights and can put nearly all of its
    mass on that single anomalous edge. Median is the cheap robust alternative
    when attention is too expensive -- it ignores the 99 rather than averaging
    them, though it cannot single out the 1.
    """
    if conv_type == "gatv2":
        assert out_dim % heads == 0, "hidden_channels must be divisible by heads"
        return GATv2Conv(
            in_dim,
            out_dim // heads,
            heads=heads,
            edge_dim=edge_dim,
            dropout=dropout,
            add_self_loops=False,
            share_weights=False,
        )
    if conv_type == "sage_median":
        return SAGEConv(in_dim, out_dim, aggr=MedianAggregation())
    if conv_type == "sage_max":
        return SAGEConv(in_dim, out_dim, aggr=MaxAggregation())
    raise ValueError(f"Unknown conv_type: {conv_type}")


class ResidualBlock(nn.Module):
    """Conv + norm + activation + dropout with an optional residual path.

    The residual is not decoration. Three stacked convs over a dense window give
    almost every node a receptive field covering the whole graph, at which point
    embeddings collapse toward the neighbourhood average and benign and
    malicious nodes stop being separable. Residual paths preserve each node's
    own signal through every hop; combined with two (not three) layers and
    Jumping Knowledge, that is what keeps over-smoothing off.
    """

    def __init__(
        self,
        conv: nn.Module,
        in_dim: int,
        out_dim: int,
        dropout: float,
        residual: bool = True,
        supports_edge_attr: bool = True,
    ):
        super().__init__()
        self.conv = conv
        self.norm = nn.LayerNorm(out_dim)
        self.dropout = dropout
        self.supports_edge_attr = supports_edge_attr
        self.residual = residual
        self.proj = (
            nn.Identity() if (residual and in_dim == out_dim)
            else (nn.Linear(in_dim, out_dim) if residual else None)
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_emb: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if self.supports_edge_attr and edge_emb is not None:
            h = self.conv(x, edge_index, edge_attr=edge_emb)
        else:
            h = self.conv(x, edge_index)
        h = self.norm(h)
        h = F.gelu(h)
        h = F.dropout(h, p=self.dropout, training=self.training)
        if self.proj is not None:
            h = h + self.proj(x)
        return h


class MLPHead(nn.Module):
    def __init__(self, in_dim: int, hidden: int, out_dim: int, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
