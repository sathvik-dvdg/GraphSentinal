# [WSL2]
"""Error.md #35 — read access to the durable enforcement audit trail.

Unlike `blocked_ips` (current state only), `enforcement_actions` is
append-only: every block/unblock attempt is logged here regardless of
whether it succeeded, so an operator can see the full history including
failures and reconciliation-driven corrections.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.database import get_db
from app.models.incident import EnforcementAction
from app.models.schemas import EnforcementActionsResponse


router = APIRouter()


@router.get("/enforcement-actions", response_model=EnforcementActionsResponse)
async def get_enforcement_actions(
    limit: int = 100,
    ip_address: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    query = db.query(EnforcementAction)
    if ip_address:
        query = query.filter(EnforcementAction.ip_address == ip_address)
    rows = query.order_by(EnforcementAction.created_at.desc()).limit(min(limit, 500)).all()
    actions = [
        {
            "id": row.id,
            "ip_address": row.ip_address,
            "action": row.action,
            "reason": row.reason,
            "status": row.status,
            "error": row.error,
            "blockchain_tx": row.blockchain_tx,
            "incident_id": row.incident_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
    return {"actions": actions, "count": len(actions)}
