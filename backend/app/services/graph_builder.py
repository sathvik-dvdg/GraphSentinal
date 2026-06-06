# [WSL2]
from __future__ import annotations

from dataclasses import dataclass
from math import log1p
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import torch


def _import_torch():
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("PyTorch is required for graph construction") from exc
    return torch


@dataclass
class GraphData:
    x: "torch.Tensor"
    edge_index: "torch.Tensor"
    flow_sources: list[str]
    flow_destinations: list[str]
    flow_records: list[dict[str, Any]]


def _flow_dict(flow: Any) -> dict[str, Any]:
    if hasattr(flow, "model_dump"):
        return flow.model_dump()
    if hasattr(flow, "dict"):
        return flow.dict()
    return dict(flow)


def _num(flow: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = flow.get(key, default)
    if value is None:
        return default
    return float(value)


def _feature_row(flow: dict[str, Any]) -> list[float]:
    packet_count = max(_num(flow, "packet_count"), 0.0)
    byte_count = max(_num(flow, "byte_count"), 0.0)
    duration = max(_num(flow, "duration_sec", 1.0), 0.001)
    dst_port = min(max(_num(flow, "dst_port"), 0.0), 65535.0)
    tcp_flags = int(_num(flow, "tcp_flags", 0.0))

    fwd_packets = max(_num(flow, "fwd_packets", packet_count), 0.0)
    bwd_packets = max(_num(flow, "bwd_packets", 0.0), 0.0)
    fwd_bytes = max(_num(flow, "fwd_bytes", byte_count), 0.0)
    bwd_bytes = max(_num(flow, "bwd_bytes", 0.0), 0.0)
    syn_flag_count = max(_num(flow, "syn_flag_count", 1.0 if tcp_flags & 2 else 0.0), 0.0)
    flow_bytes_per_s = max(_num(flow, "flow_bytes_per_s", byte_count / duration), 0.0)

    total_packets = fwd_packets + bwd_packets
    total_bytes = fwd_bytes + bwd_bytes
    eps = 1e-6

    fwd_ratio = fwd_packets / (total_packets + eps)
    avg_packet_size = total_bytes / (total_packets + eps)
    connection_rate = log1p(total_packets / duration)
    port_norm = dst_port / 65535.0
    byte_asymmetry = (fwd_bytes - bwd_bytes) / (total_bytes + eps)
    syn_ratio = min(syn_flag_count / (total_packets + eps), 1.0)
    bytes_rate_norm = log1p(min(flow_bytes_per_s, 3e8)) / log1p(3e8)

    return [
        float(fwd_ratio),
        float(avg_packet_size),
        float(connection_rate),
        float(port_norm),
        float(byte_asymmetry),
        float(syn_ratio),
        float(bytes_rate_norm),
    ]


def _edge_index(flows: list[dict[str, Any]]) -> "torch.Tensor":
    torch = _import_torch()
    edges: list[tuple[int, int]] = []
    last_by_port: dict[int, int] = {}

    for index, flow in enumerate(flows):
        if index > 0:
            edges.append((index - 1, index))

        port = int(_num(flow, "dst_port", 0.0))
        if port in last_by_port:
            edges.append((last_by_port[port], index))
        last_by_port[port] = index

    if not edges:
        return torch.zeros((2, 0), dtype=torch.long)
    return torch.tensor(edges, dtype=torch.long).t().contiguous()


def build_pyg_graph(flows: list[Any]) -> GraphData:
    torch = _import_torch()
    flow_records = [_flow_dict(flow) for flow in flows]
    if not flow_records:
        return GraphData(
            x=torch.zeros((0, 7), dtype=torch.float32),
            edge_index=torch.zeros((2, 0), dtype=torch.long),
            flow_sources=[],
            flow_destinations=[],
            flow_records=[],
        )

    x = torch.tensor([_feature_row(flow) for flow in flow_records], dtype=torch.float32)
    mean = x.mean(dim=0, keepdim=True)
    std = x.std(dim=0, keepdim=True, unbiased=False)
    std = torch.where(std < 1e-6, torch.ones_like(std), std)
    x = torch.nan_to_num((x - mean) / std, nan=0.0, posinf=0.0, neginf=0.0)

    return GraphData(
        x=x,
        edge_index=_edge_index(flow_records),
        flow_sources=[str(flow["src_ip"]) for flow in flow_records],
        flow_destinations=[str(flow["dst_ip"]) for flow in flow_records],
        flow_records=flow_records,
    )

