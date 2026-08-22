# [WSL2]
from datetime import timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.config import settings
from app.database import get_db
from app.models.incident import Incident
from app.services.blockchain_adapter import BlockchainAdapter


router = APIRouter()


def _normalize_chain_record(raw: dict) -> dict:
    """Guarantee a stable field set for the frontend regardless of which code
    path in web3_client.get_all_incidents() produced this record (event-log
    path vs. getIncident-count fallback path)."""
    return {
        "id": raw.get("id"),
        "tx_hash": raw.get("tx_hash"),
        "block_number": raw.get("block_number"),
        "incident_hash": raw.get("incident_hash"),
        "timestamp": raw.get("timestamp"),
        "source_ip": raw.get("source_ip"),
        "attack_type": raw.get("attack_type"),
        "severity": raw.get("severity"),
        "is_blocked": raw.get("is_blocked"),
        "gas_used": raw.get("gas_used"),
    }


@router.get("/forensics")
async def get_forensics(db: Session = Depends(get_db), _: None = Depends(require_session_or_api_key)):
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).all()
    adapter = BlockchainAdapter.get_instance()
    chain_records: list[dict] = []
    chain_error: str | None = None
    if adapter._connected and adapter.client is not None:
        try:
            chain_records = [_normalize_chain_record(r) for r in adapter.client.get_all_incidents()]
        except Exception as exc:
            chain_error = str(exc)
    else:
        chain_error = adapter.error or "blockchain offline"

    return {
        "incidents": [
            {
                "id": row.id,
                "source_ip": row.source_ip,
                "attack_type": row.attack_type,
                "threat_score": row.threat_score,
                "severity": row.severity,
                "is_blocked": row.is_blocked,
                "blockchain_tx": row.blockchain_tx,
                "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "enforcement_status": row.enforcement_status,
            }
            for row in incidents
        ],
        "blockchain_records": chain_records,
        "blockchain_error": chain_error,
        "total_incidents": len(incidents),
        "total_on_chain": len(chain_records),
        "chain_id": adapter.chain_id(),
        "contract_address": settings.contract_address or None,
    }

