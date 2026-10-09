"""
GraphSentinelNet -- the replacement architecture.

What changed versus the 3-layer mean-aggregated SAGE it replaces:

  * nodes are hosts, edges are flows, and flow features live on the edges
  * ports and protocol are embeddings, not normalised floats
  * attention (GATv2) or median aggregation, never mean
  * 2 layers with residuals and Jumping Knowledge, not 3 bare layers
  * a persistent per-host memory carried across window boundaries
  * two heads: per-host classification AND per-flow classification

The second head is the piece that closes the SDN gap. A node-level logit tells
a controller that 10.0.0.7 looks bad; it does not say what to drop. The edge
head scores every individual flow, so the controller receives
``(src_ip, dst_ip, protocol, dst_port)`` and can write an exact OpenFlow match.
"""
from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import Config
from ..data.graph_builder import NUM_EDGE_FEATURES, NUM_NODE_FEATURES
from ..data.ports import PORT_VOCAB_SIZE, PROTO_VOCAB_SIZE
from .layers import CategoricalEdgeEncoder, MLPHead, ResidualBlock, make_conv
from .memory import NodeMemory
from .recon import ReconstructionHeads


class GraphSentinelNet(nn.Module):
    def __init__(
        self,
        node_in: int = NUM_NODE_FEATURES,
        edge_in: int = NUM_EDGE_FEATURES,
        hidden: int = 128,
        edge_hidden: int = 64,
        num_layers: int = 2,
        heads: int = 4,
        num_classes: int = 6,
        dropout: float = 0.3,
        attn_dropout: float = 0.1,
        conv_type: str = "gatv2",
        jumping_knowledge: str = "cat",
        residual: bool = True,
        use_memory: bool = True,
        memory_dim: int = 64,
        memory_capacity: int = 262_144,
        memory_ttl_seconds: int = 1800,
        memory_hash_tail: bool = True,
        port_vocab: int = PORT_VOCAB_SIZE,
        port_dim: int = 16,
        proto_vocab: int = PROTO_VOCAB_SIZE,
        proto_dim: int = 4,
        edge_head: bool = True,
        node_head: bool = True,
        recon_enabled: bool = False,
        edge_mask_rate: float = 0.15,
    ):
        super().__init__()
        self.recon_enabled = recon_enabled
        self.edge_mask_rate = edge_mask_rate
        self.node_in = node_in
        self.edge_in = edge_in
        self.num_classes = num_classes
        self.use_memory = use_memory
        self.memory_dim = memory_dim if use_memory else 0
        self.jk_mode = jumping_knowledge
        self.has_edge_head = edge_head
        self.has_node_head = node_head
        self.conv_type = conv_type

        self.edge_encoder = CategoricalEdgeEncoder(
            edge_feat_dim=edge_in,
            port_vocab=port_vocab,
            port_dim=port_dim,
            proto_vocab=proto_vocab,
            proto_dim=proto_dim,
            out_dim=edge_hidden,
            dropout=attn_dropout,
        )

        self.node_encoder = nn.Sequential(
            nn.Linear(node_in + self.memory_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
        )

        supports_edge = conv_type == "gatv2"
        self.blocks = nn.ModuleList()
        for _ in range(num_layers):
            conv = make_conv(conv_type, hidden, hidden, heads, edge_hidden, attn_dropout)
            self.blocks.append(
                ResidualBlock(conv, hidden, hidden, dropout, residual, supports_edge)
            )

        jk_dim = hidden * (num_layers + 1) if jumping_knowledge == "cat" else hidden
        self.jk_dim = jk_dim

        if use_memory:
            self.memory = NodeMemory(
                memory_dim=memory_dim,
                capacity=memory_capacity,
                ttl_seconds=memory_ttl_seconds,
                hash_tail=memory_hash_tail,
                input_dim=jk_dim,
            )
        else:
            self.memory = None

        if node_head:
            self.node_out = MLPHead(jk_dim, hidden, num_classes, dropout)
        if edge_head:
            # [h_src ; h_dst ; edge_embedding] -> per-flow class
            self.edge_out = MLPHead(2 * jk_dim + edge_hidden, hidden, num_classes, dropout)

        self.recon = (
            ReconstructionHeads(
                jk_dim=jk_dim,
                node_in=node_in,
                edge_in=edge_in,
                edge_cat_dim=2 * port_dim + proto_dim,
                hidden=hidden,
                dropout=attn_dropout,
            )
            if recon_enabled
            else None
        )

    # ------------------------------------------------------------------
    def encode(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        edge_dst_port: torch.Tensor,
        edge_src_port: torch.Tensor,
        edge_proto: torch.Tensor,
        memory_state: Optional[torch.Tensor] = None,
    ):
        edge_emb = self.edge_encoder(edge_attr, edge_dst_port, edge_src_port, edge_proto)

        if self.use_memory:
            if memory_state is None:
                memory_state = x.new_zeros(x.size(0), self.memory_dim)
            h = self.node_encoder(torch.cat([x, memory_state], dim=-1))
        else:
            h = self.node_encoder(x)

        outs = [h]
        for block in self.blocks:
            h = block(h, edge_index, edge_emb)
            outs.append(h)

        if self.jk_mode == "cat":
            h = torch.cat(outs, dim=-1)
        elif self.jk_mode == "max":
            h = torch.stack(outs, dim=0).max(dim=0).values
        else:
            h = outs[-1]
        return h, edge_emb

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        edge_dst_port: torch.Tensor,
        edge_src_port: torch.Tensor,
        edge_proto: torch.Tensor,
        memory_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        h, edge_emb = self.encode(
            x, edge_index, edge_attr, edge_dst_port, edge_src_port, edge_proto, memory_state
        )
        out: Dict[str, torch.Tensor] = {"node_embedding": h}
        if self.has_node_head:
            out["node_logits"] = self.node_out(h)
        if self.has_edge_head:
            src, dst = edge_index[0], edge_index[1]
            out["edge_logits"] = self.edge_out(
                torch.cat([h[src], h[dst], edge_emb], dim=-1)
            )
        return out

    # ------------------------------------------------------------------
    def step_with_memory(self, data, now: Optional[int] = None) -> Dict[str, torch.Tensor]:
        """One window: read memory -> forward -> write memory back.

        This is the training and streaming entry point. Memory is read before
        the forward pass and written after, so window N+1 starts from what
        window N learned about each host -- which is how a brute force spread
        thin across an hour still accumulates evidence.
        """
        ips = getattr(data, "node_ip_int", None)
        prev = None
        slots = cold = None
        if self.use_memory and ips is not None:
            now = int(now if now is not None else getattr(data, "window_end", 0))
            degree = torch.bincount(data.edge_index[0], minlength=data.num_nodes)
            slots, cold = self.memory.slots_for(ips, now, degree)
            prev = self.memory.read(slots, cold, ips)

        out = self.forward(
            data.x,
            data.edge_index,
            data.edge_attr,
            data.edge_dst_port,
            data.edge_src_port,
            data.edge_proto,
            memory_state=prev,
        )

        if self.use_memory and ips is not None:
            new_state = self.memory.gru(out["node_embedding"], prev)
            self.memory.write(slots, new_state, now, ips)
            out["memory_state"] = new_state
        return out

    # ------------------------------------------------------------------
    def step_with_reconstruction(self, data, now: Optional[int] = None) -> Dict[str, torch.Tensor]:
        """Training step with masked-edge self-supervision.

        ONE forward pass, not two. Edges are masked before encoding, and both
        the classification heads and the reconstruction heads read the same
        masked pass -- so the 15% masking doubles as mild augmentation for the
        classifier, exactly as masked language modelling does. Masking is
        training-only; evaluation always sees the full graph.
        """
        if self.recon is None:
            return self.step_with_memory(data, now)

        n_edges = data.edge_index.size(1)
        mask = self.recon.sample_edge_mask(n_edges, self.edge_mask_rate, data.x.device)
        target = data.edge_attr
        masked_attr = self.recon.apply_mask(target, mask)

        ips = getattr(data, "node_ip_int", None)
        prev = slots = cold = None
        if self.use_memory and ips is not None:
            now = int(now if now is not None else getattr(data, "window_end", 0))
            degree = torch.bincount(data.edge_index[0], minlength=data.num_nodes)
            slots, cold = self.memory.slots_for(ips, now, degree)
            prev = self.memory.read(slots, cold, ips)

        h, edge_emb = self.encode(
            data.x, data.edge_index, masked_attr,
            data.edge_dst_port, data.edge_src_port, data.edge_proto, prev,
        )

        out: Dict[str, torch.Tensor] = {"node_embedding": h}
        if self.has_node_head:
            out["node_logits"] = self.node_out(h)
        if self.has_edge_head:
            src, dst = data.edge_index[0], data.edge_index[1]
            out["edge_logits"] = self.edge_out(torch.cat([h[src], h[dst], edge_emb], dim=-1))

        # categorical context for the edge decoder -- the decoder is told WHICH
        # port and protocol the masked flow used, so it reconstructs the traffic
        # profile rather than having to guess the service.
        edge_cat = torch.cat(
            [
                self.edge_encoder.dst_port_emb(data.edge_dst_port),
                self.edge_encoder.src_port_emb(data.edge_src_port),
                self.edge_encoder.proto_emb(data.edge_proto),
            ],
            dim=-1,
        )
        out["recon_edge"] = self.recon.edge_loss(h, data.edge_index, edge_cat, target, mask)
        out["recon_link"] = self.recon.link_loss(h, data.edge_index, data.num_nodes)
        out["recon_node"] = self.recon.node_loss(h, data.x)

        if self.use_memory and ips is not None:
            new_state = self.memory.gru(h, prev)
            self.memory.write(slots, new_state, now, ips)
        return out

    @torch.no_grad()
    def predict(self, data, now: Optional[int] = None) -> Dict[str, torch.Tensor]:
        self.eval()
        out = self.step_with_memory(data, now)
        res: Dict[str, torch.Tensor] = {}
        if "node_logits" in out:
            p = F.softmax(out["node_logits"], dim=-1)
            res["node_probs"] = p
            res["node_pred"] = p.argmax(dim=-1)
            res["node_threat"] = 1.0 - p[:, 0]
        if "edge_logits" in out:
            pe = F.softmax(out["edge_logits"], dim=-1)
            res["edge_probs"] = pe
            res["edge_pred"] = pe.argmax(dim=-1)
            res["edge_threat"] = 1.0 - pe[:, 0]
        return res

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def reset_memory(self) -> None:
        if self.memory is not None:
            self.memory.reset()


def build_model(cfg: Config) -> GraphSentinelNet:
    m = cfg.model
    return GraphSentinelNet(
        node_in=NUM_NODE_FEATURES,
        edge_in=NUM_EDGE_FEATURES,
        hidden=m.hidden_channels,
        edge_hidden=m.edge_hidden,
        num_layers=m.num_layers,
        heads=m.heads,
        num_classes=m.num_classes,
        dropout=m.dropout,
        attn_dropout=m.attn_dropout,
        conv_type=m.conv_type,
        jumping_knowledge=m.jumping_knowledge,
        residual=m.residual,
        use_memory=m.use_memory,
        memory_dim=m.memory_dim,
        memory_capacity=m.memory_capacity,
        memory_ttl_seconds=m.memory_ttl_seconds,
        memory_hash_tail=m.memory_hash_tail,
        port_dim=m.port_embed_dim,
        proto_dim=m.proto_embed_dim,
        edge_head=m.edge_head,
        node_head=m.node_head,
        recon_enabled=m.recon_enabled,
        edge_mask_rate=m.edge_mask_rate,
    )
