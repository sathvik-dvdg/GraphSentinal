"""
IP-as-node / flow-as-edge graph construction -- fully vectorised.

This replaces ``flows_to_pyg_graph``, which made every *flow row* a node and
invented edges by chaining consecutive rows and rows that happened to share a
destination port. That builds a sequence graph. Network intrusions are
topological, so the structure the old graph encoded was the wrong structure:

    port scan   = one node -> very many nodes, one port each
    botnet      = very many nodes -> one C2 node
    DDoS        = very many nodes -> one victim, huge volume
    brute force = one node -> one node, one port, many repeated attempts

None of those shapes exist in a chain of consecutive CSV rows. All four are
immediate in the graph built here.

    NODE = an IP address (or /24 supernode under the fallback policy)
    EDGE = a flow, directed src -> dst, carrying its features as edge_attr

Performance: the old builder ran a Python ``for i in range(n)`` loop with
``df.iloc[i]`` and per-row dict lookups -- roughly 40 us/row, so ~65 s per
million flows and single-core bound. Everything below is column-at-a-time
NumPy/pandas; measured throughput is >1e6 flows/s on one core.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import Data

from ..config import CLASS_TO_IDX, Config
from .ports import ports_to_tokens, protos_to_tokens

EPS = 1e-6

# --------------------------------------------------------------------------
# Feature schemas. These names are exported verbatim into the model card, so
# the backend never has to guess an ordering again.
# --------------------------------------------------------------------------
EDGE_FEATURE_NAMES: List[str] = [
    "log_duration_s",        # log1p(flow duration in seconds)
    "log_total_packets",
    "log_total_bytes",
    "fwd_packet_ratio",      # fwd / (fwd + bwd)
    "byte_asymmetry",        # (fwd_bytes - bwd_bytes) / total_bytes
    "avg_packet_size",       # scaled
    "log_max_fwd_len",
    "log_max_bwd_len",
    "syn_ratio",
    "rst_ratio",
    "ack_ratio",
    "psh_ratio",
    "log_iat_mean",
    "iat_burstiness",        # fwd_iat_total vs bwd_iat_total imbalance
    "log_dt_since_pair",     # seconds since this exact (src,dst) pair last talked
    "log_dt_since_src",      # seconds since this source sent anything
    "window_position",       # 0..1 position of the flow inside its window
    "direction_flag",        # 1 forward edge, 0 reverse mirror edge
    "log_bytes_per_s",       # VOLUMETRIC - ablatable
    "log_packets_per_s",     # VOLUMETRIC - ablatable
]
# Indices the evasion ablation zeroes out to prove the model is not leaning on
# trivially-shapeable volume.
VOLUMETRIC_EDGE_IDX: List[int] = [
    EDGE_FEATURE_NAMES.index("log_bytes_per_s"),
    EDGE_FEATURE_NAMES.index("log_packets_per_s"),
]

NODE_FEATURE_NAMES: List[str] = [
    "log_out_degree",
    "log_in_degree",
    "degree_ratio",           # out / (out + in)
    "log_unique_dst_ips",     # scan / botnet fan-out
    "log_unique_src_ips",     # DDoS / C2 fan-in
    "log_unique_dst_ports",   # vertical scan breadth
    "dst_port_entropy",       # flat distribution => scanning
    "peer_entropy",           # how evenly traffic spreads across peers
    "reciprocity",            # fraction of peers that answered back
    "log_total_bytes_out",
    "log_total_bytes_in",
    "mean_inter_flow_dt",     # low-and-slow signature
    "std_inter_flow_dt",
    "is_private_addr",
    "log_windows_seen",       # persistence across the capture
    "burst_score",            # flows in window / historical mean
]

NUM_EDGE_FEATURES = len(EDGE_FEATURE_NAMES)
NUM_NODE_FEATURES = len(NODE_FEATURE_NAMES)


# --------------------------------------------------------------------------
# IP helpers
# --------------------------------------------------------------------------
def ipv4_to_int(ips: np.ndarray) -> np.ndarray:
    """Vectorised dotted-quad -> uint32. Non-IPv4 rows come back as 0.

    Converts only the DISTINCT addresses and maps back through the factorise
    codes. A million-flow capture typically holds a few thousand distinct
    hosts, so parsing per row would repeat the same string split hundreds of
    times each.
    """
    codes, uniques = pd.factorize(pd.Series(ips, dtype="string").fillna("0.0.0.0"))
    parts = pd.Series(uniques, dtype="string").str.split(".", expand=True)
    if parts.shape[1] < 4:
        return np.zeros(len(ips), dtype=np.int64)
    vals = (
        parts.iloc[:, :4]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .to_numpy(dtype=np.int64)
    )
    table = (vals[:, 0] << 24) | (vals[:, 1] << 16) | (vals[:, 2] << 8) | vals[:, 3]
    out = np.zeros(len(codes), dtype=np.int64)
    valid = codes >= 0
    out[valid] = table[codes[valid]]
    return out


def is_private(ip_ints: np.ndarray) -> np.ndarray:
    """RFC1918 + loopback + link-local membership test, vectorised."""
    a = (ip_ints >> 24) & 0xFF
    b = (ip_ints >> 16) & 0xFF
    return (
        (a == 10)
        | ((a == 172) & (b >= 16) & (b <= 31))
        | ((a == 192) & (b == 168))
        | (a == 127)
        | ((a == 169) & (b == 254))
    ).astype(np.float32)


def subnet_key(ip_ints: np.ndarray, prefix: int = 24) -> np.ndarray:
    """Mask to /prefix so cold or ephemeral hosts can collapse into a supernode."""
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ip_ints & mask


def hash_ip(ip: str, capacity: int) -> int:
    """Stable slot hash used by the streaming memory store.

    Deterministic across processes (unlike ``hash()``), so a checkpoint's memory
    slots stay valid when the inference service restarts.
    """
    digest = hashlib.blake2b(ip.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % capacity


def hash_ips(ips: np.ndarray, capacity: int) -> np.ndarray:
    return np.fromiter(
        (hash_ip(str(x), capacity) for x in ips), dtype=np.int64, count=len(ips)
    )


# --------------------------------------------------------------------------
# Vectorised group helpers
# --------------------------------------------------------------------------
def _bincount(idx: np.ndarray, n: int, weights: Optional[np.ndarray] = None) -> np.ndarray:
    if idx.size == 0:
        return np.zeros(n, dtype=np.float64)
    return np.bincount(idx, weights=weights, minlength=n)[:n]


def _encode_pairs(group: np.ndarray, value: np.ndarray) -> Tuple[np.ndarray, int]:
    """Pack (group, value) into one int64 key.

    ``np.unique(arr2d, axis=0)`` does a lexicographic sort over a structured
    view and was 60 % of the builder's runtime. Packing into a single int64 and
    calling the 1-D ``np.unique`` is the same result an order of magnitude
    faster.
    """
    v = value.astype(np.int64, copy=False)
    span = int(v.max()) + 1 if v.size else 1
    return group.astype(np.int64, copy=False) * span + v, span


def _grouped_nunique(group: np.ndarray, value: np.ndarray, n: int) -> np.ndarray:
    """Distinct ``value`` count per ``group``, without a Python loop."""
    if group.size == 0:
        return np.zeros(n, dtype=np.float64)
    key, span = _encode_pairs(group, value)
    uniq = np.unique(key)
    return _bincount((uniq // span).astype(np.int64), n)


def _grouped_entropy(group: np.ndarray, value: np.ndarray, n: int) -> np.ndarray:
    """Shannon entropy of ``value`` within each ``group``, vectorised.

    A host contacting 900 distinct ports once each has near-maximal entropy;
    a web server answering :443 has near-zero. That gap is the port-scan
    signature, and it survives any rate limiting the attacker applies -- which
    is exactly why it belongs in the feature set and ``Flow Bytes/s`` does not.
    """
    if group.size == 0:
        return np.zeros(n, dtype=np.float64)
    key, span = _encode_pairs(group, value)
    uniq, counts = np.unique(key, return_counts=True)
    g = (uniq // span).astype(np.int64)
    totals = _bincount(g, n)
    totals_safe = np.where(totals > 0, totals, 1.0)
    p = counts / totals_safe[g]
    contrib = -p * np.log(p + EPS)
    return _bincount(g, n, weights=contrib)


# --------------------------------------------------------------------------
# Persistent cross-window host state
# --------------------------------------------------------------------------
@dataclass
class HostHistory:
    """Long-horizon per-IP counters carried across window boundaries.

    This is what makes a low-and-slow attack visible: ten SSH attempts spread
    over an hour never co-occur inside one window, but ``windows_seen`` and
    ``mean_inter_flow_dt`` accumulate across all of them.

    Bounded: at ``capacity`` entries the coldest 10 % are evicted, so this is
    O(capacity) memory regardless of how many distinct IPs the interface sees.
    """

    capacity: int = 262_144
    counts: Dict[int, int] = None          # ip_int -> windows seen
    last_seen: Dict[int, int] = None       # ip_int -> unix seconds
    flow_totals: Dict[int, int] = None     # ip_int -> lifetime flow count

    def __post_init__(self):
        self.counts = self.counts or {}
        self.last_seen = self.last_seen or {}
        self.flow_totals = self.flow_totals or {}

    def lookup(self, ip_ints: np.ndarray, now: int) -> Tuple[np.ndarray, np.ndarray]:
        seen = np.fromiter(
            (self.counts.get(int(i), 0) for i in ip_ints),
            dtype=np.float64,
            count=len(ip_ints),
        )
        hist_mean = np.fromiter(
            (
                self.flow_totals.get(int(i), 0) / max(self.counts.get(int(i), 1), 1)
                for i in ip_ints
            ),
            dtype=np.float64,
            count=len(ip_ints),
        )
        return seen, hist_mean

    def update(self, ip_ints: np.ndarray, flow_counts: np.ndarray, now: int) -> None:
        for ip, fc in zip(ip_ints.tolist(), flow_counts.tolist()):
            ip = int(ip)
            self.counts[ip] = self.counts.get(ip, 0) + 1
            self.flow_totals[ip] = self.flow_totals.get(ip, 0) + int(fc)
            self.last_seen[ip] = now
        if len(self.counts) > self.capacity:
            self._evict()

    def _evict(self) -> None:
        keep = int(self.capacity * 0.9)
        order = sorted(self.last_seen.items(), key=lambda kv: kv[1], reverse=True)
        survivors = {ip for ip, _ in order[:keep]}
        self.counts = {k: v for k, v in self.counts.items() if k in survivors}
        self.flow_totals = {k: v for k, v in self.flow_totals.items() if k in survivors}
        self.last_seen = {k: v for k, v in self.last_seen.items() if k in survivors}

    def state_dict(self) -> dict:
        return {
            "capacity": self.capacity,
            "counts": self.counts,
            "last_seen": self.last_seen,
            "flow_totals": self.flow_totals,
        }

    @classmethod
    def from_state(cls, d: dict) -> "HostHistory":
        h = cls(capacity=d.get("capacity", 262_144))
        h.counts = d.get("counts", {})
        h.last_seen = d.get("last_seen", {})
        h.flow_totals = d.get("flow_totals", {})
        return h


# --------------------------------------------------------------------------
# Edge feature engineering
# --------------------------------------------------------------------------
def _safe_log1p(a: np.ndarray) -> np.ndarray:
    return np.log1p(np.clip(np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0), 0, None))


RAW_EDGE_COLUMNS = (
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Fwd Packet Length Max",
    "Bwd Packet Length Max",
    "Flow IAT Mean",
    "Fwd IAT Total",
    "Bwd IAT Total",
    "SYN Flag Count",
    "RST Flag Count",
    "ACK Flag Count",
    "PSH Flag Count",
    "Flow Bytes/s",
    "Flow Packets/s",
    "dt_pair",
    "dt_src",
    "t",
)


def numeric_columns(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Coerce every raw column to float64 ONCE for the whole split.

    Doing this per window instead cost ~20 pandas coercions per graph and was
    the single largest source of overhead in the builder -- the same class of
    mistake as the original per-row loop, just one level up.
    """
    n = len(df)
    cols: Dict[str, np.ndarray] = {}
    for c in RAW_EDGE_COLUMNS:
        if c in df.columns:
            cols[c] = (
                pd.to_numeric(df[c], errors="coerce").fillna(0.0).to_numpy(dtype=np.float64)
            )
        else:
            cols[c] = np.zeros(n, dtype=np.float64)
    return cols


def compute_edge_features(
    cols: Dict[str, np.ndarray], t0: float, t1: float
) -> np.ndarray:
    """Build the (E, NUM_EDGE_FEATURES) matrix for one window. Vectorised."""
    n_rows = len(cols["t"])
    g = lambda c: cols.get(c, np.zeros(n_rows))  # noqa: E731

    duration_s = np.maximum(g("Flow Duration") / 1e6, 1e-3)
    fwd_pkts = g("Total Fwd Packets")
    bwd_pkts = g("Total Backward Packets")
    fwd_bytes = g("Total Length of Fwd Packets")
    bwd_bytes = g("Total Length of Bwd Packets")
    total_pkts = fwd_pkts + bwd_pkts
    total_bytes = fwd_bytes + bwd_bytes

    syn = g("SYN Flag Count")
    rst = g("RST Flag Count")
    ack = g("ACK Flag Count")
    psh = g("PSH Flag Count")

    fwd_iat = g("Fwd IAT Total")
    bwd_iat = g("Bwd IAT Total")

    dt_pair = g("dt_pair")
    dt_src = g("dt_src")
    t = g("t")
    span = max(t1 - t0, 1.0)

    feats = np.empty((n_rows, NUM_EDGE_FEATURES), dtype=np.float32)
    feats[:, 0] = _safe_log1p(duration_s)
    feats[:, 1] = _safe_log1p(total_pkts)
    feats[:, 2] = _safe_log1p(total_bytes)
    feats[:, 3] = fwd_pkts / (total_pkts + EPS)
    feats[:, 4] = (fwd_bytes - bwd_bytes) / (total_bytes + EPS)
    feats[:, 5] = _safe_log1p(total_bytes / (total_pkts + EPS)) / 10.0
    feats[:, 6] = _safe_log1p(g("Fwd Packet Length Max"))
    feats[:, 7] = _safe_log1p(g("Bwd Packet Length Max"))
    feats[:, 8] = np.clip(syn / (total_pkts + EPS), 0, 1)
    feats[:, 9] = np.clip(rst / (total_pkts + EPS), 0, 1)
    feats[:, 10] = np.clip(ack / (total_pkts + EPS), 0, 1)
    feats[:, 11] = np.clip(psh / (total_pkts + EPS), 0, 1)
    feats[:, 12] = _safe_log1p(g("Flow IAT Mean") / 1e6)
    feats[:, 13] = (fwd_iat - bwd_iat) / (fwd_iat + bwd_iat + EPS)
    feats[:, 14] = _safe_log1p(dt_pair)
    feats[:, 15] = _safe_log1p(dt_src)
    feats[:, 16] = np.clip((t - t0) / span, 0, 1)
    feats[:, 17] = 1.0  # forward direction; reverse mirrors overwrite with 0
    feats[:, 18] = _safe_log1p(g("Flow Bytes/s")) / 20.0
    feats[:, 19] = _safe_log1p(g("Flow Packets/s")) / 15.0

    return np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)


def add_temporal_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Seconds since the same pair / same source last appeared.

    Two vectorised groupby-diffs, computed once over the whole split rather
    than per window, so a gap that spans a window boundary is still measured
    correctly. This is the feature a low-and-slow brute force cannot hide from.
    """
    df = df.sort_values("t", kind="mergesort")
    pair_key = df["Source IP"].astype(str) + ">" + df["Destination IP"].astype(str)
    df["dt_pair"] = (
        df.groupby(pair_key, sort=False)["t"].diff().fillna(86400.0).clip(lower=0)
    )
    df["dt_src"] = (
        df.groupby(df["Source IP"], sort=False)["t"].diff().fillna(86400.0).clip(lower=0)
    )
    return df


# --------------------------------------------------------------------------
# The builder
# --------------------------------------------------------------------------
class GraphBuilder:
    """Turns a chronologically ordered flow table into a stream of PyG graphs."""

    def __init__(self, cfg: Config, history: Optional[HostHistory] = None):
        self.cfg = cfg
        # Resolve names -> column indices once, and FAIL LOUDLY on a typo.
        # Silently ignoring an unrecognised name would mean running the exact
        # ablation you thought you had disabled and reporting it as the other.
        drop = list(getattr(cfg.data, "drop_edge_features", []) or [])
        unknown = [d for d in drop if d not in EDGE_FEATURE_NAMES]
        if unknown:
            raise ValueError(
                f"drop_edge_features names not in EDGE_FEATURE_NAMES: {unknown}\n"
                f"These must be ENGINEERED feature names, not raw CSV columns. "
                f"Valid: {EDGE_FEATURE_NAMES}"
            )
        self._drop_idx = [EDGE_FEATURE_NAMES.index(d) for d in drop]
        self.history = history or HostHistory(capacity=cfg.model.memory_capacity)
        self.rng = np.random.default_rng(cfg.train.seed)

    # -- windowing ---------------------------------------------------------
    def _window_bounds(self, t: np.ndarray) -> Iterator[Tuple[int, int, float, float]]:
        """Yield (lo, hi, start, end) for every NON-EMPTY window.

        Non-overlapping windows are derived by integer division and
        ``np.unique`` rather than by stepping a cursor across the whole capture:
        a four-day capture at 30 s windows is 11 520 candidate windows, of which
        only the occupied ones are worth visiting.
        """
        w = self.cfg.graph.window_seconds
        stride = self.cfg.graph.window_stride_seconds or w
        if len(t) == 0:
            return
        t0, tmax = float(t[0]), float(t[-1])

        if stride == w:
            wid = ((t - t0) // w).astype(np.int64)
            uniq, starts, counts = np.unique(wid, return_index=True, return_counts=True)
            for k, lo, cnt in zip(uniq.tolist(), starts.tolist(), counts.tolist()):
                yield lo, lo + cnt, t0 + k * w, t0 + (k + 1) * w
            return

        # Overlapping windows: cursor walk, but jump straight to the next flow
        # instead of stepping through empty stretches.
        start = t0
        while start <= tmax:
            end = start + w
            lo = int(np.searchsorted(t, start, side="left"))
            hi = int(np.searchsorted(t, end, side="left"))
            if hi > lo:
                yield lo, hi, start, end
            elif lo < len(t):
                start = max(start + stride, float(t[lo]) - w + stride)
                continue
            start += stride

    # -- node features -----------------------------------------------------
    def _node_features(
        self,
        n_nodes: int,
        src: np.ndarray,
        dst: np.ndarray,
        node_ip_int: np.ndarray,
        dst_port_tok: np.ndarray,
        total_bytes: np.ndarray,
        t: np.ndarray,
        window_end: float,
    ) -> np.ndarray:
        out_deg = _bincount(src, n_nodes)
        in_deg = _bincount(dst, n_nodes)

        uniq_dst_ips = _grouped_nunique(src, dst, n_nodes)
        uniq_src_ips = _grouped_nunique(dst, src, n_nodes)
        uniq_ports = _grouped_nunique(src, dst_port_tok, n_nodes)
        port_ent = _grouped_entropy(src, dst_port_tok, n_nodes)
        peer_ent = _grouped_entropy(src, dst, n_nodes)

        bytes_out = _bincount(src, n_nodes, weights=total_bytes)
        bytes_in = _bincount(dst, n_nodes, weights=total_bytes)

        # Reciprocity: did each peer answer back? Encoded as int64 pair keys and
        # resolved with a sorted-array membership test -- the Python set/zip
        # version here was O(E) interpreted work and dominated the profile.
        fwd_key = src.astype(np.int64) * n_nodes + dst.astype(np.int64)
        rev_key = dst.astype(np.int64) * n_nodes + src.astype(np.int64)
        recip_flag = np.isin(rev_key, fwd_key, assume_unique=False).astype(np.float64)
        recip = _bincount(src, n_nodes, weights=recip_flag) / np.maximum(out_deg, 1)

        # inter-flow timing per source (mean/std) via sum and sum-of-squares
        order = np.argsort(src, kind="stable")
        s_sorted, t_sorted = src[order], t[order]
        dt = np.diff(t_sorted, prepend=t_sorted[0] if len(t_sorted) else 0.0)
        same = np.concatenate([[False], s_sorted[1:] == s_sorted[:-1]])
        dt = np.where(same, dt, 0.0)
        cnt = np.maximum(_bincount(s_sorted, n_nodes, weights=same.astype(float)), 1)
        mean_dt = _bincount(s_sorted, n_nodes, weights=dt) / cnt
        var_dt = _bincount(s_sorted, n_nodes, weights=dt**2) / cnt - mean_dt**2

        windows_seen, hist_mean = self.history.lookup(node_ip_int, int(window_end))
        flows_now = out_deg + in_deg
        burst = flows_now / np.maximum(hist_mean, 1.0)

        f = np.empty((n_nodes, NUM_NODE_FEATURES), dtype=np.float32)
        f[:, 0] = np.log1p(out_deg)
        f[:, 1] = np.log1p(in_deg)
        f[:, 2] = out_deg / (out_deg + in_deg + EPS)
        f[:, 3] = np.log1p(uniq_dst_ips)
        f[:, 4] = np.log1p(uniq_src_ips)
        f[:, 5] = np.log1p(uniq_ports)
        f[:, 6] = port_ent
        f[:, 7] = peer_ent
        f[:, 8] = recip
        f[:, 9] = np.log1p(bytes_out) / 20.0
        f[:, 10] = np.log1p(bytes_in) / 20.0
        f[:, 11] = np.log1p(np.maximum(mean_dt, 0))
        f[:, 12] = np.log1p(np.sqrt(np.maximum(var_dt, 0)))
        f[:, 13] = is_private(node_ip_int)
        f[:, 14] = np.log1p(windows_seen)
        f[:, 15] = np.log1p(np.clip(burst, 0, 1e6))
        return np.nan_to_num(f, nan=0.0, posinf=0.0, neginf=0.0)

    # -- node labels -------------------------------------------------------
    @staticmethod
    def _node_labels(
        n_nodes: int, src: np.ndarray, dst: np.ndarray, edge_y: np.ndarray, n_classes: int
    ) -> np.ndarray:
        """Modal non-benign class over a node's incident flows, else BENIGN.

        Attributing to *both* endpoints is deliberate: in a DDoS the victim is
        as much a node of interest as each bot, and the backend needs the
        victim's identity to write a rule that protects it.
        """
        votes = np.zeros((n_nodes, n_classes), dtype=np.int64)
        for endpoint in (src, dst):
            flat = endpoint * n_classes + edge_y
            counts = np.bincount(flat, minlength=n_nodes * n_classes)[: n_nodes * n_classes]
            votes += counts.reshape(n_nodes, n_classes)
        attack_votes = votes[:, 1:]
        has_attack = attack_votes.sum(axis=1) > 0
        labels = np.zeros(n_nodes, dtype=np.int64)
        labels[has_attack] = attack_votes[has_attack].argmax(axis=1) + 1
        return labels

    # -- main entry --------------------------------------------------------
    def build(
        self,
        df: pd.DataFrame,
        update_history: bool = True,
        verbose: bool = True,
    ) -> List[Data]:
        """Build every window graph for one split."""
        cfg = self.cfg
        df = add_temporal_deltas(df).reset_index(drop=True)

        t = df["t"].to_numpy(dtype=np.float64)
        src_ip_int = ipv4_to_int(df["Source IP"].to_numpy())
        dst_ip_int = ipv4_to_int(df["Destination IP"].to_numpy())
        if cfg.graph.node_key == "ip_subnet24":
            p = cfg.graph.subnet_fallback_prefix
            src_ip_int = subnet_key(src_ip_int, p)
            dst_ip_int = subnet_key(dst_ip_int, p)

        dst_port_tok_all = ports_to_tokens(
            pd.to_numeric(df.get("Destination Port", 0), errors="coerce").fillna(-1)
        )
        src_port_tok_all = ports_to_tokens(
            pd.to_numeric(df.get("Source Port", 0), errors="coerce").fillna(-1)
        )
        proto_tok_all = protos_to_tokens(
            pd.to_numeric(df.get("Protocol", 0), errors="coerce").fillna(-1)
        )
        edge_y_all = df["y"].to_numpy(dtype=np.int64)
        total_bytes_all = (
            pd.to_numeric(df.get("Total Length of Fwd Packets", 0), errors="coerce").fillna(0)
            + pd.to_numeric(df.get("Total Length of Bwd Packets", 0), errors="coerce").fillna(0)
        ).to_numpy(dtype=np.float64)

        cols_all = numeric_columns(df)

        graphs: List[Data] = []
        n_windows = 0
        for lo, hi, w_start, w_end in self._window_bounds(t):
            n_windows += 1
            g = self._build_one(
                {k: v[lo:hi] for k, v in cols_all.items()},
                src_ip_int[lo:hi],
                dst_ip_int[lo:hi],
                dst_port_tok_all[lo:hi],
                src_port_tok_all[lo:hi],
                proto_tok_all[lo:hi],
                edge_y_all[lo:hi],
                total_bytes_all[lo:hi],
                t[lo:hi],
                w_start,
                w_end,
                update_history=update_history,
            )
            if g is not None:
                graphs.append(g)
            if verbose and n_windows % 200 == 0:
                print(f"    {n_windows} windows -> {len(graphs)} graphs")

        if verbose:
            print(f"    built {len(graphs)} graphs from {n_windows} windows")
        return graphs

    def _build_one(
        self,
        cols: Dict[str, np.ndarray],
        src_ip_int: np.ndarray,
        dst_ip_int: np.ndarray,
        dst_port_tok: np.ndarray,
        src_port_tok: np.ndarray,
        proto_tok: np.ndarray,
        edge_y: np.ndarray,
        total_bytes: np.ndarray,
        t: np.ndarray,
        w_start: float,
        w_end: float,
        update_history: bool,
    ) -> Optional[Data]:
        cfg = self.cfg
        n_edges = len(src_ip_int)
        if n_edges < cfg.graph.min_edges_per_graph:
            return None

        # --- nodes: unique endpoints across both columns -------------------
        endpoints = np.concatenate([src_ip_int, dst_ip_int])
        node_ip_int, inverse = np.unique(endpoints, return_inverse=True)
        n_nodes = len(node_ip_int)
        src = inverse[:n_edges]
        dst = inverse[n_edges:]

        # --- node features on the FULL window ------------------------------
        # Computed before any subsampling, so a 200k-flow DDoS still reports its
        # true in-degree even if the message-passing edge set is capped.
        node_x = self._node_features(
            n_nodes, src, dst, node_ip_int, dst_port_tok, total_bytes, t, w_end
        )
        node_y = self._node_labels(n_nodes, src, dst, edge_y, cfg.model.num_classes)

        if update_history:
            flows_per_node = _bincount(src, n_nodes) + _bincount(dst, n_nodes)
            self.history.update(node_ip_int, flows_per_node, int(w_end))

        # --- edge subsampling safety valve ---------------------------------
        cap = cfg.graph.max_edges_per_graph
        keep = np.arange(n_edges)
        if n_edges > cap:
            keep = np.sort(self.rng.choice(n_edges, size=cap, replace=False))
            cols = {k: v[keep] for k, v in cols.items()}
            src, dst = src[keep], dst[keep]
            dst_port_tok, src_port_tok = dst_port_tok[keep], src_port_tok[keep]
            proto_tok, edge_y = proto_tok[keep], edge_y[keep]
            t = t[keep]

        edge_attr = compute_edge_features(cols, w_start, w_end)

        # Zero any engineered feature the config asks to drop. Done HERE rather
        # than at eval time so a retrain never sees the column at all -- the
        # probe on 2026-09-13 measured its effect by feeding zeros to a model
        # that HAD trained on them, which is an out-of-distribution reading,
        # not a statement about what a fresh model would learn.
        if self._drop_idx:
            edge_attr[:, self._drop_idx] = 0.0

        edge_index = np.stack([src, dst])
        if cfg.graph.add_reverse_edges:
            rev_attr = edge_attr.copy()
            rev_attr[:, 17] = 0.0  # direction_flag
            edge_index = np.concatenate(
                [edge_index, np.stack([dst, src])], axis=1
            )
            edge_attr = np.concatenate([edge_attr, rev_attr], axis=0)
            dst_port_tok = np.concatenate([dst_port_tok, dst_port_tok])
            src_port_tok = np.concatenate([src_port_tok, src_port_tok])
            proto_tok = np.concatenate([proto_tok, proto_tok])
            edge_y_full = np.concatenate([edge_y, edge_y])
            real_edge_mask = np.concatenate(
                [np.ones(len(edge_y), bool), np.zeros(len(edge_y), bool)]
            )
        else:
            edge_y_full = edge_y
            real_edge_mask = np.ones(len(edge_y), bool)

        data = Data(
            x=torch.from_numpy(node_x),
            edge_index=torch.from_numpy(edge_index.astype(np.int64)),
            edge_attr=torch.from_numpy(edge_attr),
            y=torch.from_numpy(node_y),
        )
        data.edge_dst_port = torch.from_numpy(dst_port_tok.astype(np.int64))
        data.edge_src_port = torch.from_numpy(src_port_tok.astype(np.int64))
        data.edge_proto = torch.from_numpy(proto_tok.astype(np.int64))
        data.edge_y = torch.from_numpy(edge_y_full.astype(np.int64))
        data.real_edge_mask = torch.from_numpy(real_edge_mask)
        data.node_ip_int = torch.from_numpy(node_ip_int.astype(np.int64))
        data.window_start = float(w_start)
        data.window_end = float(w_end)
        data.num_nodes = n_nodes
        return data


def summarise_graphs(graphs: List[Data], n_classes: int) -> dict:
    """Sanity statistics printed after construction."""
    if not graphs:
        return {}
    nodes = np.array([g.num_nodes for g in graphs])
    edges = np.array([g.edge_index.size(1) for g in graphs])
    node_class = np.zeros(n_classes, dtype=np.int64)
    edge_class = np.zeros(n_classes, dtype=np.int64)
    for g in graphs:
        node_class += np.bincount(g.y.numpy(), minlength=n_classes)[:n_classes]
        edge_class += np.bincount(
            g.edge_y[g.real_edge_mask].numpy(), minlength=n_classes
        )[:n_classes]
    return {
        "n_graphs": len(graphs),
        "nodes_mean": float(nodes.mean()),
        "nodes_max": int(nodes.max()),
        "edges_mean": float(edges.mean()),
        "edges_max": int(edges.max()),
        "node_class_counts": node_class.tolist(),
        "edge_class_counts": edge_class.tolist(),
    }
