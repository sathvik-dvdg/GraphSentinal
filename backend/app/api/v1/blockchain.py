# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_session_or_api_key
from app.models.schemas import BlockchainStoreRequest
from app.services.blockchain_adapter import BlockchainAdapter


router = APIRouter()


@router.post("/blockchain/store")
async def store_incident_on_chain(
    request: BlockchainStoreRequest,
    _: None = Depends(require_session_or_api_key),
):
    adapter = BlockchainAdapter.get_instance()
    return adapter.store_incident(
        source_ip=request.source_ip,
        attack_type=request.attack_type,
        severity=request.severity,
        is_blocked=request.is_blocked,
        incident_id=request.sqlite_incident_id,
    )

