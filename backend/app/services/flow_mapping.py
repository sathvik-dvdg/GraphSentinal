# [WSL2]
"""Map a backend `FlowRecord` onto the CICFlowMeter-shaped record the v2 graph
builder consumes.

THIS MODULE IS LOAD-BEARING. Two mappings in particular are not cosmetic:

  byte_count -> "Total Length of Fwd Packets"
        `GraphBuilder.build()` derives `total_bytes_all` from ONLY
        "Total Length of Fwd Packets" + "Total Length of Bwd Packets". Drop this
        mapping and node features 9 (`log_total_bytes_out`) and 10
        (`log_total_bytes_in`) become log1p(0) = 0.0 for every host in the graph,
        silently, with no error anywhere.

  a real timestamp -> "t"
        Node features 11 (`mean_inter_flow_dt`) and 12 (`std_inter_flow_dt`),
        and edge features 14/15/16 (`log_dt_since_pair`, `log_dt_since_src`,
        `window_position`) are all derived from `t`. `FlowRecord` has no
        timestamp field at all, so the caller must supply the observation time.

So four of the sixteen node features die silently if either mapping is dropped
in a refactor. `backend/tests/` asserts both.

WHAT THE LIVE PATH CANNOT SUPPLY (audited against `compute_edge_features`;
`numeric_columns()` fills 0.0 for any absent column):

    derivable (10): log_duration_s, log_total_packets, log_total_bytes,
                    avg_packet_size, log_dt_since_pair, log_dt_since_src,
                    window_position, direction_flag, log_bytes_per_s,
                    log_packets_per_s
    pinned    (2):  fwd_packet_ratio -> 1.0, byte_asymmetry -> +1.0
                    (constant, because OVS gives no directional split)
    zeroed    (8):  log_max_fwd_len, log_max_bwd_len, log_iat_mean,
                    iat_burstiness, and syn/rst/ack/psh_ratio whenever
                    `tcp_flags` is 0 — which is the normal case, since
                    `ovs-ofctl dump-flows` does not print per-packet TCP flags
                    and flow_parser.py refuses to fabricate them.

All 16 NODE features survive intact, given the two mappings above.
"""
from __future__ import annotations

import time
from typing import Any

# IANA protocol numbers. The v2 contract takes `Protocol` as an INT; the
# backend's FlowRecord carries it as a NAME ("TCP"/"UDP"/"ICMP"/"ARP"/"IP").
_PROTO_NUMBERS: dict[str, int] = {
    "TCP": 6,
    "UDP": 17,
    "ICMP": 1,
    "IP": 0,
    "ARP": 0,  # ARP is not an IP protocol; 0 lands in the contract's pad/oov bucket.
}

# TCP flag bits, for turning `tcp_flags` into the per-flag counts the builder
# divides by total packets. A bitmask records PRESENCE, not a count, so the best
# available answer is 1-or-0 — never a fabricated frequency.
_FLAG_BITS: dict[str, int] = {
    "FIN Flag Count": 0x01,
    "SYN Flag Count": 0x02,
    "RST Flag Count": 0x04,
    "PSH Flag Count": 0x08,
    "ACK Flag Count": 0x10,
    "URG Flag Count": 0x20,
}


class FlowMappingError(ValueError):
    """A flow could not be mapped. Carries the field that was wrong."""


def _as_dict(flow: Any) -> dict[str, Any]:
    """Normalise to a dict, validating raw dicts through `FlowRecord`.

    `parse_ovs_flows()` hands the monitor plain dicts. The v1 path validates
    those through `FlowRecord` (IPv4-only addresses, port ranges, finite
    numerics); the v2 path must apply the SAME validation, or one malformed IP
    reaches the inference service, fails `ipv4_to_int` inside the graph builder,
    and loses the entire window instead of the one bad flow.
    """
    if hasattr(flow, "model_dump"):
        return flow.model_dump()
    if hasattr(flow, "dict") and not isinstance(flow, dict):
        return flow.dict()
    # Imported here to keep this module importable without the app schema
    # layer's dependencies for static inspection.
    from app.models.schemas import FlowRecord

    return FlowRecord(**dict(flow)).model_dump()


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def protocol_number(name: Any) -> int:
    """Map a protocol NAME to its IANA number. Unknown names fall to 0."""
    if isinstance(name, (int, float)):
        return int(name)
    return _PROTO_NUMBERS.get(str(name or "").strip().upper(), 0)


def map_flow(flow: Any, observed_at: float | None = None) -> dict[str, Any]:
    """Convert one `FlowRecord` (or dict) to a v2 engine record.

    `observed_at` is the wall-clock time the flow was captured, in epoch
    seconds. It becomes `t`, which drives windowing and five features. Defaults
    to now(), which is correct for the live OVS poll — every flow in one poll
    shares that poll's observation time.

    Raises FlowMappingError when a required field is missing or malformed, so
    the caller can drop that one flow and keep the batch. Never raises for an
    ABSENT optional column — those are legitimately unavailable from OVS and
    the builder zero-fills them by design.
    """
    try:
        f = _as_dict(flow)
    except (TypeError, ValueError) as exc:  # pydantic ValidationError is a ValueError
        raise FlowMappingError(f"flow failed FlowRecord validation: {exc}") from exc
    t = float(observed_at) if observed_at is not None else time.time()

    src_ip = f.get("src_ip")
    dst_ip = f.get("dst_ip")
    if not src_ip or not dst_ip:
        raise FlowMappingError(f"flow missing src_ip/dst_ip: src={src_ip!r} dst={dst_ip!r}")

    # Duration: the builder does `Flow Duration / 1e6` and floors at 1e-3, so it
    # wants MICROSECONDS. FlowRecord carries seconds.
    duration_s = max(_num(f.get("duration_sec"), 1.0), 1e-3)

    packet_count = max(_num(f.get("packet_count")), 0.0)
    byte_count = max(_num(f.get("byte_count")), 0.0)

    # Directional split. OVS reports cumulative per-table-entry counters with no
    # forward/backward breakdown, so when the optional fields are absent we put
    # everything on the forward side and leave backward at 0 — the convention
    # already documented in backend/NODE_FEATURES.md for the v1 model. This is
    # what pins fwd_packet_ratio to 1.0 and byte_asymmetry to +1.0.
    fwd_packets = _num(f.get("fwd_packets"), packet_count)
    bwd_packets = _num(f.get("bwd_packets"), 0.0)
    fwd_bytes = _num(f.get("fwd_bytes"), byte_count)
    bwd_bytes = _num(f.get("bwd_bytes"), 0.0)

    tcp_flags = int(_num(f.get("tcp_flags"), 0.0))

    record: dict[str, Any] = {
        # -- identity: what makes a node and an edge ------------------------
        "Source IP": str(src_ip),
        "Destination IP": str(dst_ip),
        "Source Port": int(_num(f.get("src_port"), 0.0)),
        "Destination Port": int(_num(f.get("dst_port"), 0.0)),
        "Protocol": protocol_number(f.get("protocol")),
        # -- time: drives windowing and 5 features --------------------------
        "t": t,
        # -- volume ---------------------------------------------------------
        "Flow Duration": duration_s * 1e6,          # builder divides by 1e6
        "Total Fwd Packets": fwd_packets,
        "Total Backward Packets": bwd_packets,
        # LOAD-BEARING: node features 9 and 10 read ONLY these two columns.
        "Total Length of Fwd Packets": fwd_bytes,
        "Total Length of Bwd Packets": bwd_bytes,
        # -- rates: derivable, so supply them rather than let them zero-fill -
        "Flow Bytes/s": byte_count / duration_s,
        "Flow Packets/s": packet_count / duration_s,
    }

    # Flag counts, only when OVS actually reported flags. Writing 0 explicitly
    # would be indistinguishable from "no flags seen", which is the truth here,
    # so either way the ratios read 0 — but only emit keys we have a basis for.
    for column, bit in _FLAG_BITS.items():
        record[column] = 1.0 if tcp_flags & bit else 0.0

    return record


def map_flows(flows: list[Any], observed_at: float | None = None) -> tuple[list[dict], list[str]]:
    """Map a batch. Returns (mapped, errors) — one bad flow never kills a poll.

    Errors are returned rather than raised so the caller can log them and still
    score the rest of the window. A silently dropped flow is a missed detection,
    so the caller MUST surface the error list.
    """
    t = float(observed_at) if observed_at is not None else time.time()
    mapped: list[dict] = []
    errors: list[str] = []
    for index, flow in enumerate(flows):
        try:
            mapped.append(map_flow(flow, observed_at=t))
        except (FlowMappingError, TypeError, ValueError) as exc:
            errors.append(f"flow[{index}]: {exc}")
    return mapped, errors
