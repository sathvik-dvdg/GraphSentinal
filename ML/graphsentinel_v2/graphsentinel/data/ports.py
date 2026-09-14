"""
Port and protocol vocabularies.

Fixes the "semantic destruction of categorical features" defect: the old
pipeline fed ``port / 65535.0`` to the network, which asserts that port 22 and
port 23 are nearly the same thing and that port 80 and port 8080 are opposites.
Both claims are false and neither is learnable.

Here every port becomes an integer *token*. Tokens are consumed by an
``nn.Embedding`` in the model, so the network learns its own geometry over
ports -- and it can place 80 and 8080 next to each other if the data says so.

Token layout (stable, versioned -- changing it invalidates trained weights):

    0                       PAD / unknown-missing
    1                       OOV / anything unmapped
    2 .. 2+len(WELL_KNOWN)  one dedicated token per named service port
    then                    coarse buckets for the unnamed remainder

The bucket tail matters: 65 536 dedicated embeddings would be mostly
untrained noise, since ephemeral client ports are drawn ~uniformly and carry
no per-value meaning. Grouping them preserves the only signal they do carry
(which *range* they came from).
"""
from __future__ import annotations

from typing import Dict, Iterable

import numpy as np

PAD_TOKEN = 0
OOV_TOKEN = 1

# Service ports that actually mean something to an IDS. Grouped by the attack
# surface they expose, which is the relationship we want the embedding to be
# free to discover.
WELL_KNOWN_PORTS: tuple[int, ...] = (
    # remote administration / lateral movement
    21, 22, 23, 3389, 5900, 5985, 5986,
    # web
    80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 8081, 9090,
    # mail
    25, 110, 143, 465, 587, 993, 995,
    # naming / discovery / infrastructure
    53, 67, 68, 123, 137, 138, 139, 161, 162, 389, 636, 445,
    # databases
    1433, 1521, 3306, 5432, 6379, 9200, 11211, 27017, 5984, 7000, 9042,
    # file transfer / sharing
    69, 115, 989, 990, 2049, 873,
    # messaging / queues / orchestration
    1883, 5672, 9092, 2181, 2375, 2376, 6443, 10250,
    # tunnelling / VPN / proxy
    500, 1194, 1701, 1723, 4500, 1080, 3128,
    # misc frequently abused
    111, 135, 512, 513, 514, 515, 520, 631, 1900, 5060, 5061, 6660, 6667, 6697,
    31337, 12345, 4444, 5555, 6666, 8291, 49152,
)

_WELL_KNOWN_BASE = 2
_PORT_TO_TOKEN: Dict[int, int] = {
    p: _WELL_KNOWN_BASE + i for i, p in enumerate(sorted(set(WELL_KNOWN_PORTS)))
}
_BUCKET_BASE = _WELL_KNOWN_BASE + len(_PORT_TO_TOKEN)

# Coarse buckets for everything unnamed. Boundaries follow IANA ranges plus a
# log-ish split of the ephemeral space.
_BUCKET_EDGES = np.array(
    [0, 1, 512, 1024, 2048, 4096, 8192, 16384, 32768, 49152, 65536], dtype=np.int64
)
NUM_BUCKETS = len(_BUCKET_EDGES) - 1
PORT_VOCAB_SIZE = _BUCKET_BASE + NUM_BUCKETS


def port_to_token(port: int) -> int:
    """Single-port lookup. Vectorised callers should use :func:`ports_to_tokens`."""
    if port is None or port < 0 or port > 65535:
        return OOV_TOKEN
    tok = _PORT_TO_TOKEN.get(int(port))
    if tok is not None:
        return tok
    bucket = int(np.searchsorted(_BUCKET_EDGES, port, side="right") - 1)
    bucket = min(max(bucket, 0), NUM_BUCKETS - 1)
    return _BUCKET_BASE + bucket


def ports_to_tokens(ports: Iterable[int] | np.ndarray) -> np.ndarray:
    """Vectorised port -> token. O(n), no Python loop over rows.

    Builds a 65 536-entry lookup table once and indexes it, which is orders of
    magnitude faster than a per-row dict hit and is what the graph builder uses.
    """
    table = _lookup_table()
    arr = np.asarray(ports)
    if arr.size == 0:
        return np.zeros(0, dtype=np.int64)
    # NaN -> PAD, out-of-range -> OOV.
    if arr.dtype.kind == "f":
        bad = ~np.isfinite(arr)
        arr = np.where(bad, -1, arr)
    arr = arr.astype(np.int64, copy=False)
    out = np.full(arr.shape, OOV_TOKEN, dtype=np.int64)
    valid = (arr >= 0) & (arr <= 65535)
    out[valid] = table[arr[valid]]
    return out


_TABLE_CACHE: np.ndarray | None = None


def _lookup_table() -> np.ndarray:
    global _TABLE_CACHE
    if _TABLE_CACHE is None:
        table = np.empty(65536, dtype=np.int64)
        buckets = np.searchsorted(_BUCKET_EDGES, np.arange(65536), side="right") - 1
        np.clip(buckets, 0, NUM_BUCKETS - 1, out=buckets)
        table[:] = _BUCKET_BASE + buckets
        for p, tok in _PORT_TO_TOKEN.items():
            table[p] = tok
        _TABLE_CACHE = table
    return _TABLE_CACHE


# --------------------------------------------------------------------------
# Protocol
# --------------------------------------------------------------------------
# CICFlowMeter writes the IANA protocol number. Only a handful ever appear.
PROTO_TO_TOKEN: Dict[int, int] = {0: 1, 1: 2, 6: 3, 17: 4, 47: 5, 50: 6}
PROTO_VOCAB_SIZE = 8
PROTO_OOV = 7


def protos_to_tokens(protos: Iterable[int] | np.ndarray) -> np.ndarray:
    arr = np.asarray(protos)
    if arr.size == 0:
        return np.zeros(0, dtype=np.int64)
    if arr.dtype.kind == "f":
        arr = np.where(np.isfinite(arr), arr, -1)
    arr = arr.astype(np.int64, copy=False)
    out = np.full(arr.shape, PROTO_OOV, dtype=np.int64)
    for raw, tok in PROTO_TO_TOKEN.items():
        out[arr == raw] = tok
    return out


def vocab_summary() -> dict:
    return {
        "port_vocab_size": PORT_VOCAB_SIZE,
        "named_ports": len(_PORT_TO_TOKEN),
        "num_buckets": NUM_BUCKETS,
        "bucket_edges": _BUCKET_EDGES.tolist(),
        "pad_token": PAD_TOKEN,
        "oov_token": OOV_TOKEN,
        "proto_vocab_size": PROTO_VOCAB_SIZE,
    }
