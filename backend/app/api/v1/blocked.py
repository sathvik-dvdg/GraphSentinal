# [WSL2]
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import require_api_key
from app.database import get_db
from app.models.incident import BlockedIP
from app.models.schemas import BlockRequest
from app.services.self_healing import SelfHealingEngine


router = APIRouter()


@router.get("/blocked")
async def get_blocked(db: Session = Depends(get_db)):
    rows = db.query(BlockedIP).order_by(BlockedIP.blocked_at.desc()).all()
    blocked = [
        {
            "ip": row.ip_address,
            "blocked_at": row.blocked_at.isoformat(),
            "reason": row.reason,
            "attack_type": row.attack_type,
            "threat_score": row.threat_score,
            "blockchain_tx": row.blockchain_tx,
            "enforcement_status": row.enforcement_status,
        }
        for row in rows
    ]
    return {"blocked_ips": blocked, "count": len(blocked)}


@router.post("/block")
async def block_or_unblock(
    request: BlockRequest,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    healer = SelfHealingEngine()
    try:
        if request.action == "unblock":
            result = healer.unblock_ip(request.ip, db=db)
            return {"status": "unblocked", "ip": result["ip"]}
        event = healer.block_ip(request.ip, reason=request.reason, db=db)
        return {"status": "blocked", "ip": event["ip"], "blockchain_tx": None, "enforcement_status": event["enforcement_status"]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

