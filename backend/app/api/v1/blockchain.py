# [WSL2]
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import require_admin_key, require_api_key
from app.models.schemas import BlockchainStoreRequest
from app.services.blockchain_adapter import BlockchainAdapter


router = APIRouter()


@router.post("/blockchain/store")
async def store_incident_on_chain(
    request: BlockchainStoreRequest,
    _: None = Depends(require_admin_key),
):
    adapter = BlockchainAdapter.get_instance()
    return await asyncio.to_thread(
        adapter.store_incident,
        source_ip=request.source_ip,
        attack_type=request.attack_type,
        severity=request.severity,
        is_blocked=request.is_blocked,
        incident_id=request.sqlite_incident_id,
    )


class VerifyRequest(BaseModel):
    incident_id: int = Field(ge=1)
    source_ip: str
    attack_type: str
    severity: int = Field(ge=1, le=10)
    timestamp: int


@router.post("/blockchain/verify")
async def verify_incident_on_chain(
    request: VerifyRequest,
    _: None = Depends(require_api_key),
):
    adapter = BlockchainAdapter.get_instance()
    if not adapter._connected or adapter.client is None:
        raise HTTPException(status_code=503, detail="Blockchain offline")
    try:
        is_valid = await asyncio.to_thread(
            adapter.client.verify_incident,
            request.incident_id, request.source_ip, request.attack_type,
            request.severity, request.timestamp,
        )
        return {"verified": is_valid, "incident_id": request.incident_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class ReleaseRequest(BaseModel):
    ip: str
    reason: str = "MANUAL_RELEASE"


@router.post("/blockchain/release")
async def release_node_on_chain(
    request: ReleaseRequest,
    _: None = Depends(require_admin_key),
):
    adapter = BlockchainAdapter.get_instance()
    if not adapter._connected or adapter.client is None:
        raise HTTPException(status_code=503, detail="Blockchain offline")
    try:
        tx_hash = await asyncio.to_thread(adapter.client.release_node, request.ip, request.reason)
        return {"status": "released", "ip": request.ip, "tx_hash": tx_hash}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class BlockchainConfigRequest(BaseModel):
    ganache_url: str | None = None
    contract_address: str | None = None
    gas_limit: int | None = None


@router.post("/config/blockchain")
async def update_blockchain_config(
    request: BlockchainConfigRequest,
    _: None = Depends(require_admin_key),
):
    adapter = BlockchainAdapter.get_instance()
    try:
        return await asyncio.to_thread(
            adapter.update_config,
            ganache_url=request.ganache_url,
            contract_address=request.contract_address,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
