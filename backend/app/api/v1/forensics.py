import asyncio
from datetime import timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_api_key
from app.config import settings
from app.database import get_db
from app.models.incident import Incident
from app.services.blockchain_adapter import BlockchainAdapter


router = APIRouter()


@router.get("/forensics", dependencies=[Depends(require_api_key)])
async def get_forensics(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).all()
    chain_records = []
    adapter = BlockchainAdapter.get_instance()
    if adapter._connected and adapter.client is not None:
        try:
            chain_records = await asyncio.to_thread(adapter.client.get_all_incidents)
        except Exception:
            chain_records = []

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
        "total_incidents": len(incidents),
        "total_on_chain": len(chain_records),
        "chain_id": 1337,
        "contract_address": settings.contract_address or None,
    }

