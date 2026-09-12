# [WSL2]
# Error.md #35 — shared writer for the enforcement_actions audit trail.
# Every code path that blocks/unblocks an IP (GNN-triggered, manual operator
# action, or reconciliation drift-correction) calls this so there's one
# durable, append-only record of what was requested and what actually
# happened — independent of blocked_ips (current-state only) and incidents
# (only covers GNN-triggered detections).
from __future__ import annotations

from app.database import SessionLocal
from app.models.incident import EnforcementAction


def capture_network_stability() -> int | None:
    """Error.md N2/H1 — a real "network stability %" for a healing event:
    the same system_health figure the dashboard shows, sampled at the moment
    it's called (once before a block, once after). Returns None if the graph
    state can't be read so the frontend shows '—' rather than a fake number."""
    try:
        from app.services.graph_state import graph_state

        return int(graph_state.stats_response().get("system_health", 0))
    except Exception:
        return None


def count_host_edges(ip: str) -> int | None:
    """Error.md N2/H1 — how many live traffic edges currently touch this host,
    i.e. how many connections isolating it severs. None if unavailable."""
    try:
        from app.services.graph_state import graph_state

        links = graph_state.graph_response().get("links", [])
        return sum(1 for link in links if ip in (link.get("source"), link.get("target")))
    except Exception:
        return None


def log_enforcement_action(
    ip_address: str,
    action: str,
    reason: str,
    status: str,
    error: str | None = None,
    blockchain_tx: str | None = None,
    incident_id: int | None = None,
    duration_ms: int | None = None,
    edges_severed: int | None = None,
    network_stability_before: int | None = None,
    network_stability_after: int | None = None,
    db=None,
) -> None:
    owns_db = db is None
    db = db or SessionLocal()
    try:
        db.add(
            EnforcementAction(
                ip_address=ip_address,
                action=action,
                reason=reason,
                status=status,
                error=error,
                blockchain_tx=blockchain_tx,
                incident_id=incident_id,
                duration_ms=duration_ms,
                edges_severed=edges_severed,
                network_stability_before=network_stability_before,
                network_stability_after=network_stability_after,
            )
        )
        db.commit()
    finally:
        if owns_db:
            db.close()
