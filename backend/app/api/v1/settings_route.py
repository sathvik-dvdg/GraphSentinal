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
async def get_settings_endpoint(req: Request = None, _: None = Depends(require_session_or_api_key)):
    gs2 = getattr(req.app.state, "gs2", None) if req is not None else None
    points = gs2.operating_points if gs2 is not None and gs2.enabled else None
    return {
        "threat_threshold": settings.threat_threshold,
        "enforcement_mode": settings.enforcement_mode,
        "demo_fallback_flows": settings.demo_fallback_flows,
        "ganache_url": settings.ganache_url,
        "contract_address": settings.contract_address or None,
        # Read-only: reported so the UI can distinguish the operator-tunable
        # heuristic threshold from the model's fitted gate. None here means no
        # fitted operating point exists yet and the v2 path raises no alerts.
        "ml_binary_gate": points.binary_gate if points else None,
        "ml_binary_gate_source": points.source if points else None,
        "ml_gate_mutable": False,
    }


@router.patch("/settings", response_model=SettingsUpdateResponse)
async def update_settings_endpoint(
    request: SettingsUpdateRequest,
    identity: dict = Depends(require_admin_privilege),
    db: Session = Depends(get_db),
    req: Request = None,
):
    # SCOPE: this moves the v1/heuristic gate ONLY (ThreatAnalyzer, graph_state
    # severity banding). It deliberately cannot move the v2 model's binary gate:
    # that gate is an operating point fitted against measured precision and
    # recall, read from ML/threshold_study.json, and an operator dragging a
    # slider has no measurement behind the new value. The v2 gate is not stored
    # on `settings`, so there is nothing here to reassign — the separation is
    # structural, not a guard that can be forgotten. GET /settings reports it
    # read-only with its provenance.
    old_threshold = settings.threat_threshold
    settings.threat_threshold = request.threat_threshold
    req_id = get_current_request_id(req)
    log_audit_event(
        db=db,
        actor_identity=identity.get("identity", "admin"),
        actor_role=identity.get("role", "admin"),
        action="settings_update",
        target_resource="threat_threshold",
        details={
            "old_threat_threshold": old_threshold,
            "new_threat_threshold": request.threat_threshold,
            # Recorded explicitly so an audit reader can tell which gate moved.
            "scope": "v1_heuristic_gate_only",
            "model_gate_changed": False,
        },
        status="success",
        request_id=req_id,
    )
    return {"threat_threshold": settings.threat_threshold}


