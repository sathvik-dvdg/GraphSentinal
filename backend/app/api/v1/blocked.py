import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_request_id, require_admin_privilege, require_session_or_api_key
from app.database import get_db
from app.models.incident import BlockedIP, Incident
from app.models.schemas import BlockedResponse, BlockRequest, BlockResponse
from app.services.audit_service import log_audit_event
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.enforcement_log import log_enforcement_action
from app.services.self_healing import SelfHealingEngine
from app.services.threat_analyzer import score_to_severity_int
from app.websocket.server import sio

_logger = logging.getLogger("graphsentinel.blocked")

router = APIRouter()


@router.get("/blocked", response_model=BlockedResponse)
async def get_blocked(db: Session = Depends(get_db), _: None = Depends(require_session_or_api_key)):
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


@router.post("/block", response_model=BlockResponse)
async def block_or_unblock(
    request: BlockRequest,
    identity: dict = Depends(require_admin_privilege),
    db: Session = Depends(get_db),
    req: Request = None,
):
    healer = SelfHealingEngine()
    req_id = get_current_request_id(req)
    clean_ip = str(request.ip)
    try:
        if request.action == "unblock":
            result = await run_in_threadpool(healer.unblock_ip, clean_ip)

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
                data_source="manual",
            )
            db.add(closure)
            db.commit()
            db.refresh(closure)
            try:
                tx_result = await run_in_threadpool(
                    BlockchainAdapter.get_instance().release_node,
                    ip=result["ip"],
                    reason="MANUAL_OVERRIDE",
                )
            except Exception as exc:
                _logger.warning("[req_id=%s] Blockchain release_node failed for %s: %s", req_id, result["ip"], exc)
                tx_result = {"status": "retry", "error": "Blockchain write failed or offline", "tx_hash": None}
            closure.blockchain_tx = tx_result.get("tx_hash")
            # N-03: persist chain context for forensic reconciliation
            closure.blockchain_chain_id = tx_result.get("chain_id")
            closure.blockchain_contract_address = tx_result.get("contract_address")
            closure.blockchain_block_number = tx_result.get("block_number")
            # N-04: releaseNode is an on-chain state transition, not an incident creation
            closure.blockchain_incident_id = None
            # N-05: record outbox status
            closure.blockchain_status = tx_result.get("status", "pending") if tx_result.get("tx_hash") else tx_result.get("status", "retry")
            closure.blockchain_last_error = tx_result.get("error") if tx_result.get("status") != "confirmed" else None
            db.commit()
            log_enforcement_action(
                ip_address=result["ip"],
                action="unblock",
                reason="MANUAL_OVERRIDE",
                status=result["enforcement_status"],
                blockchain_tx=tx_result.get("tx_hash"),
                incident_id=closure.id,
                db=db,
            )
            log_audit_event(
                db=db,
                actor_identity=identity.get("identity", "admin"),
                actor_role=identity.get("role", "admin"),
                action="manual_unblock",
                target_resource=f"ip:{result['ip']}",
                details={"action": "unblock", "reason": request.reason, "enforcement_status": result["enforcement_status"]},
                status="success",
                request_id=req_id,
            )

            return {
                "status": "unblocked",
                "ip": result["ip"],
                "blockchain_tx": tx_result.get("tx_hash"),
                "enforcement_status": result["enforcement_status"],
            }

        event = await run_in_threadpool(healer.block_ip, clean_ip, reason=request.reason)

        now = datetime.now(timezone.utc)
        incident = Incident(
            source_ip=event["ip"],
            attack_type="Manual",
            threat_score=0.0,
            severity=1,
            is_blocked=True,
            enforcement_status=event["enforcement_status"],
            idempotency_key=None,
            # N-06 (N06-SEC-02): Claim reservation on creation
            blockchain_status="submitting",
            blockchain_claimed_at=now,
            data_source="manual",
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        try:
            tx_result = await run_in_threadpool(
                BlockchainAdapter.get_instance().store_incident,
                source_ip=event["ip"],
                attack_type="Manual",
                severity=score_to_severity_int(event.get("trigger_score") or 0.0) or 1,
                is_blocked=True,
                incident_id=incident.id,
            )
        except Exception as exc:
            _logger.warning("[req_id=%s] Blockchain store_incident failed for %s: %s", req_id, event["ip"], exc)
            tx_result = {"status": "retry", "error": "Blockchain write failed or offline", "tx_hash": None}
        incident.blockchain_tx = tx_result.get("tx_hash")
        # N-03: persist chain context for forensic reconciliation
        incident.blockchain_chain_id = tx_result.get("chain_id")
        incident.blockchain_contract_address = tx_result.get("contract_address")
        incident.blockchain_block_number = tx_result.get("block_number")
        # N-04: persist exact on-chain incident ID decoded from receipt event
        incident.blockchain_incident_id = tx_result.get("incident_id")
        # N-06: release claim lease and record outbox status & pending timestamp
        incident.blockchain_claimed_at = None
        if tx_result.get("status") == "confirmed":
            incident.blockchain_status = "confirmed"
            incident.blockchain_last_error = None
        elif tx_result.get("status") == "pending" and tx_result.get("tx_hash"):
            incident.blockchain_status = "pending"
            incident.blockchain_pending_since = datetime.now(timezone.utc)
            incident.blockchain_last_error = tx_result.get("error")
        else:
            incident.blockchain_status = "retry"
            incident.blockchain_retry_count = (incident.blockchain_retry_count or 0) + 1
            incident.blockchain_last_error = tx_result.get("error", "Blockchain write failed or offline")
        db.commit()

        blocked_row = db.query(BlockedIP).filter(BlockedIP.ip_address == event["ip"]).one_or_none()
        if blocked_row is not None and tx_result.get("tx_hash"):
            blocked_row.blockchain_tx = tx_result["tx_hash"]
            db.commit()

        log_enforcement_action(
            ip_address=event["ip"],
            action="block",
            reason=request.reason,
            status=event["enforcement_status"],
            blockchain_tx=tx_result.get("tx_hash"),
            incident_id=incident.id,
            db=db,
        )
        log_audit_event(
            db=db,
            actor_identity=identity.get("identity", "admin"),
            actor_role=identity.get("role", "admin"),
            action="manual_block",
            target_resource=f"ip:{event['ip']}",
            details={"action": "block", "reason": request.reason, "enforcement_status": event["enforcement_status"]},
            status="success",
            request_id=req_id,
        )

        try:
            await sio.emit("healing_triggered", event)
        except Exception as exc:
            _logger.warning("Failed to emit healing_triggered event for IP %s: %s", event.get("ip"), exc)

        return {
            "status": "blocked",
            "ip": event["ip"],
            "blockchain_tx": tx_result.get("tx_hash"),
            "enforcement_status": event["enforcement_status"],
            "healing_event": event,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        _logger.exception("[req_id=%s] Unexpected error in block_or_unblock: %s", req_id, exc)
        raise


