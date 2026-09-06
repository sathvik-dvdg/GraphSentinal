# [WSL2]
from datetime import timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.config import settings
from app.database import get_db
from app.models.incident import Incident
from app.models.schemas import ForensicsResponse
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
        "status": "confirmed",
    }


@router.get("/forensics", response_model=ForensicsResponse)
async def get_forensics(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    total_count = db.query(func.count(Incident.id)).scalar() or 0
    incidents = (
        db.query(Incident)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    adapter = BlockchainAdapter.get_instance()
    chain_records: list[dict] = []
    chain_error: str | None = None

    # Current active contract address (from settings, loaded from /shared at
    # backend startup) — used as the expected target for reconciliation.
    active_contract = settings.contract_address or None
    active_chain_id = adapter.chain_id() if adapter._connected else None

    if adapter._connected and adapter.client is not None:
        try:
            chain_records = [_normalize_chain_record(r) for r in adapter.client.get_all_incidents()]
        except Exception as exc:
            chain_error = str(exc)
    else:
        chain_error = adapter.error or "blockchain offline"

    # ── O-F04: Read authoritative persisted reconciliation state from SQLite ──
    # Instead of calling adapter.reconcile_tx() in an N+1 synchronous loop that
    # fires live RPC calls for every incident row, use the durable fields
    # maintained by ReconciliationWorker and ingestion pipelines.
    reconciled_incidents = []
    for row in incidents:
        status = getattr(row, "blockchain_status", None)
        if not row.blockchain_tx:
            tx_status = "no_tx"
        elif status and status not in ("no_tx", "submitting"):
            tx_status = status
        elif not adapter._connected or adapter.client is None:
            tx_status = "unavailable"
        else:
            tx_status = status or "pending"

        reconciled_incidents.append({
            "id": row.id,
            "source_ip": row.source_ip,
            "attack_type": row.attack_type,
            "threat_score": row.threat_score,
            "severity": row.severity,
            "is_blocked": row.is_blocked,
            "blockchain_tx": row.blockchain_tx,
            "blockchain_chain_id": row.blockchain_chain_id,
            "blockchain_contract_address": row.blockchain_contract_address,
            "blockchain_block_number": row.blockchain_block_number,
            "blockchain_incident_id": row.blockchain_incident_id,
            "blockchain_status": status or tx_status,
            "blockchain_retry_count": getattr(row, "blockchain_retry_count", 0) or 0,
            "blockchain_last_error": getattr(row, "blockchain_last_error", None),
            "tx_status": tx_status,
            "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "enforcement_status": row.enforcement_status,
            "data_source": row.data_source,
            # Error.md H5 — server-authoritative triage state (shared with alerts)
            "alert_status": getattr(row, "alert_status", None) or "open",
            "acknowledged_at": row.acknowledged_at.replace(tzinfo=timezone.utc).isoformat() if getattr(row, "acknowledged_at", None) else None,
            "resolved_at": row.resolved_at.replace(tzinfo=timezone.utc).isoformat() if getattr(row, "resolved_at", None) else None,
        })

    return {
        "incidents": reconciled_incidents,
        "blockchain_records": chain_records,
        "blockchain_error": chain_error,
        "total_incidents": total_count,
        "total_on_chain": len(chain_records),
        "chain_id": active_chain_id,
        "contract_address": active_contract,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(reconciled_incidents) < total_count),
    }

