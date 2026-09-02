# [WSL2]
# Error.md #19 — real backend endpoints for the one Settings-page control
# that actually maps to live backend behavior. threat_threshold is mutated
# in-memory only (resets to the .env-configured value on restart); a
# durable-config-file rewrite is a bigger, riskier scope than "wire this
# slider to something real."
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_request_id, require_admin_privilege, require_session_or_api_key
from app.config import settings
from app.database import get_db
from app.models.schemas import SettingsResponse, SettingsUpdateRequest, SettingsUpdateResponse
from app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint(_: None = Depends(require_session_or_api_key)):
    return {
        "threat_threshold": settings.threat_threshold,
        "enforcement_mode": settings.enforcement_mode,
        "demo_fallback_flows": settings.demo_fallback_flows,
        "ganache_url": settings.ganache_url,
        "contract_address": settings.contract_address or None,
    }


@router.patch("/settings", response_model=SettingsUpdateResponse)
async def update_settings_endpoint(
    request: SettingsUpdateRequest,
    identity: dict = Depends(require_admin_privilege),
    db: Session = Depends(get_db),
    req: Request = None,
):
    old_threshold = settings.threat_threshold
    settings.threat_threshold = request.threat_threshold
    req_id = get_current_request_id(req)
    log_audit_event(
        db=db,
        actor_identity=identity.get("identity", "admin"),
        actor_role=identity.get("role", "admin"),
        action="settings_update",
        target_resource="threat_threshold",
        details={"old_threat_threshold": old_threshold, "new_threat_threshold": request.threat_threshold},
        status="success",
        request_id=req_id,
    )
    return {"threat_threshold": settings.threat_threshold}


