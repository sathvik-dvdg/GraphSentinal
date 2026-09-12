# [WSL2]
"""Error.md H5 — operator triage state for incidents/alerts.

Alert Centre (acknowledge/resolve) and the Forensics "Mark Resolved" button
used to write to per-component React state / localStorage that never agreed
across pages. This endpoint makes the state server-authoritative: one PATCH
updates the row, `/api/v1/alerts` and `/api/v1/forensics` both read it back,
and MTTA gets a real acknowledge timestamp.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_identity, get_current_request_id
from app.database import get_db
from app.models.incident import Incident
from app.models.schemas import IncidentStatusResponse, IncidentStatusUpdateRequest
from app.services.audit_service import log_audit_event


router = APIRouter()


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@router.patch("/incidents/{incident_id}/status", response_model=IncidentStatusResponse)
async def update_incident_status(
    incident_id: int,
    body: IncidentStatusUpdateRequest,
    identity: dict = Depends(get_current_identity),
    db: Session = Depends(get_db),
    req: Request = None,
):
    incident = db.query(Incident).filter(Incident.id == incident_id).one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    now = datetime.now(timezone.utc)
    new_status = body.status
    incident.alert_status = new_status

    # Stamp the first time each transition happens; don't clobber an earlier
    # acknowledge time if the operator later resolves.
    if new_status == "acknowledged" and incident.acknowledged_at is None:
        incident.acknowledged_at = now
    elif new_status == "resolved":
        if incident.acknowledged_at is None:
            incident.acknowledged_at = now
        incident.resolved_at = now
    elif new_status == "open":
        incident.acknowledged_at = None
        incident.resolved_at = None

    db.commit()
    db.refresh(incident)

    log_audit_event(
        db=db,
        actor_identity=identity.get("identity", "operator"),
        actor_role=identity.get("role", "operator"),
        action="incident_status_update",
        target_resource=f"incident:{incident_id}",
        details={"status": new_status},
        status="success",
        request_id=get_current_request_id(req),
    )

    return {
        "id": incident.id,
        "alert_status": incident.alert_status,
        "acknowledged_at": _iso(incident.acknowledged_at),
        "resolved_at": _iso(incident.resolved_at),
    }
