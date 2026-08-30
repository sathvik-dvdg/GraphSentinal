# [WSL2]
from __future__ import annotations

from datetime import timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import require_admin_privilege
from app.database import get_db
from app.models.incident import AuditLog
from app.models.schemas import AuditLogsResponse

router = APIRouter()


@router.get("/audit-logs", response_model=AuditLogsResponse)
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_privilege),
):
    total = db.query(func.count(AuditLog.id)).scalar() or 0
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    records = [
        {
            "id": row.id,
            "actor_identity": row.actor_identity,
            "actor_role": row.actor_role,
            "action": row.action,
            "target_resource": row.target_resource,
            "details": row.details,
            "status": row.status,
            "request_id": row.request_id,
            "timestamp": row.timestamp.replace(tzinfo=timezone.utc).isoformat() if row.timestamp.tzinfo is None else row.timestamp.isoformat(),
        }
        for row in rows
    ]
    return {
        "audit_logs": records,
        "count": len(records),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(records) < total),
    }
