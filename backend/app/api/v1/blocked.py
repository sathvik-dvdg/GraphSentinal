# [WSL2]
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import require_api_key
from app.database import get_db
from app.models.incident import BlockedIP, Incident
from app.models.schemas import BlockRequest
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.self_healing import SelfHealingEngine
from app.services.threat_analyzer import score_to_severity_int


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

            # Reflect the unblock in incident history so it doesn't keep
            # claiming the IP is still blocked (Error.md #14), and record a
            # durable closure event through the same ledger pipeline
            # automatic blocks use (Error.md #13).
            db.query(Incident).filter(
                Incident.source_ip == result["ip"], Incident.is_blocked == True  # noqa: E712
            ).update({"is_blocked": False})
            db.commit()

            closure = Incident(
                source_ip=result["ip"],
                attack_type="Manual",
                threat_score=0.0,
                severity=1,
                is_blocked=False,
                enforcement_status=result["enforcement_status"],
                idempotency_key=None,
            )
            db.add(closure)
            db.commit()
            db.refresh(closure)
            tx_result = BlockchainAdapter.get_instance().store_incident(
                source_ip=result["ip"],
                attack_type="Manual-Unblock",
                severity=1,
                is_blocked=False,
                incident_id=closure.id,
            )
            closure.blockchain_tx = tx_result.get("tx_hash")
            db.commit()

            return {
                "status": "unblocked",
                "ip": result["ip"],
                "blockchain_tx": tx_result.get("tx_hash"),
                "enforcement_status": result["enforcement_status"],
            }

        event = healer.block_ip(request.ip, reason=request.reason, db=db)

        incident = Incident(
            source_ip=event["ip"],
            attack_type="Manual",
            threat_score=0.0,
            severity=1,
            is_blocked=True,
            enforcement_status=event["enforcement_status"],
            idempotency_key=None,
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        tx_result = BlockchainAdapter.get_instance().store_incident(
            source_ip=event["ip"],
            attack_type="Manual",
            severity=score_to_severity_int(event.get("trigger_score") or 0.0) or 1,
            is_blocked=True,
            incident_id=incident.id,
        )
        incident.blockchain_tx = tx_result.get("tx_hash")
        db.commit()

        blocked_row = db.query(BlockedIP).filter(BlockedIP.ip_address == event["ip"]).one_or_none()
        if blocked_row is not None and tx_result.get("tx_hash"):
            blocked_row.blockchain_tx = tx_result["tx_hash"]
            db.commit()

        return {
            "status": "blocked",
            "ip": event["ip"],
            "blockchain_tx": tx_result.get("tx_hash"),
            "enforcement_status": event["enforcement_status"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

