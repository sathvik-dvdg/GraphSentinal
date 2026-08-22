# [WSL2]
# Error.md #19 — real backend endpoints for the one Settings-page control
# that actually maps to live backend behavior. threat_threshold is mutated
# in-memory only (resets to the .env-configured value on restart); a
# durable-config-file rewrite is a bigger, riskier scope than "wire this
# slider to something real."
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_api_key
from app.config import settings
from app.models.schemas import SettingsUpdateRequest

router = APIRouter()


@router.get("/settings")
async def get_settings_endpoint():
    return {
        "threat_threshold": settings.threat_threshold,
        "enforcement_mode": settings.enforcement_mode,
        "demo_fallback_flows": settings.demo_fallback_flows,
        "ganache_url": settings.ganache_url,
        "contract_address": settings.contract_address or None,
    }


@router.patch("/settings")
async def update_settings_endpoint(
    request: SettingsUpdateRequest,
    _: None = Depends(require_api_key),
):
    settings.threat_threshold = request.threat_threshold
    return {"threat_threshold": settings.threat_threshold}
