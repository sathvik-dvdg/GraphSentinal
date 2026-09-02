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


def log_enforcement_action(
    ip_address: str,
    action: str,
    reason: str,
    status: str,
    error: str | None = None,
    blockchain_tx: str | None = None,
    incident_id: int | None = None,
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
            )
        )
        db.commit()
    finally:
        if owns_db:
            db.close()
