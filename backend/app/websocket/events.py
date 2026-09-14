# [WSL2]
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("graphsentinel.websocket")

# R-06 (M16-F02) — Maximum number of nodes and links included in the
# compact graph_update broadcast.  Clients that need the full graph
# snapshot should use the REST API (/api/v1/stats or the AnalyzeResponse).
_MAX_BROADCAST_NODES = 50
_MAX_BROADCAST_LINKS = 100


def _compact_graph_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """R-06 (M16-F02) — Produce a bounded compact projection of the full
    graph snapshot for Socket.IO broadcast.

    Instead of emitting the complete nodes[] and links[] arrays (which can
    grow proportionally to flow batch size and observed topology), emit:

    1.  metadata    — always small and fixed-size
    2.  top_nodes   — at most _MAX_BROADCAST_NODES, sorted by descending
                      threat_score so the most security-relevant hosts
                      are always included
    3.  top_links   — at most _MAX_BROADCAST_LINKS, sorted by descending
                      value (max endpoint threat score)
    4.  total_nodes — total count so the client knows if the list was
                      truncated
    5.  total_links — total count for the same reason
    6.  truncated   — boolean flag for client awareness

    This bounds per-broadcast payload to a deterministic maximum size
    regardless of how large the underlying graph is, reducing the O(M×N)
    broadcast amplification to O(M × K) where K is a small constant.
    """
    if not isinstance(snapshot, dict):
        return snapshot

    nodes = snapshot.get("nodes") or []
    links = snapshot.get("links") or []
    metadata = snapshot.get("metadata") or {}

    # Sort by threat_score descending — most dangerous hosts first
    sorted_nodes = sorted(nodes, key=lambda n: n.get("threat_score", 0), reverse=True)
    sorted_links = sorted(links, key=lambda l: l.get("value", 0), reverse=True)

    top_nodes = sorted_nodes[:_MAX_BROADCAST_NODES]
    top_links = sorted_links[:_MAX_BROADCAST_LINKS]

    return {
        "nodes": top_nodes,
        "links": top_links,
        "metadata": metadata,
        "total_nodes": len(nodes),
        "total_links": len(links),
        "truncated": len(nodes) > _MAX_BROADCAST_NODES or len(links) > _MAX_BROADCAST_LINKS,
    }


async def emit_analysis_events(sio: Any, result: dict) -> None:
    """R-05 (M16-F02, M17-F01) — Defensive Socket.IO event emission with
    error isolation.
    R-06 (M16-F02) — Emit compact bounded graph projections instead of full
    snapshots to mitigate O(M×N) broadcast amplification."""
    if not sio or not isinstance(result, dict):
        return

    try:
        if "graph_snapshot" in result and result["graph_snapshot"] is not None:
            compact = _compact_graph_snapshot(result["graph_snapshot"])
            await sio.emit("graph_update", compact)
    except Exception as exc:
        _logger.warning("Failed to emit graph_update event: %s", exc)

    for alert in result.get("alerts") or []:
        try:
            await sio.emit("alert", alert)
        except Exception as exc:
            _logger.warning("Failed to emit alert event: %s", exc)

    for event in result.get("healing_events") or []:
        try:
            await sio.emit("healing_triggered", event)
        except Exception as exc:
            _logger.warning("Failed to emit healing_triggered event: %s", exc)

