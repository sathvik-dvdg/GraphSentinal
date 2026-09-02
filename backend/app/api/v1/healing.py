from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.database import get_db
from app.models.incident import BlockedIP, EnforcementAction, Incident
from app.models.schemas import HealingEvent, HealingEventsResponse

router = APIRouter()


@router.get("/healing", response_model=HealingEventsResponse)
async def get_healing_events(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    """Retrieve historical and active healing/isolation events from durable storage."""
    actions = (
        db.query(EnforcementAction)
        .filter(EnforcementAction.action == "block")
        .order_by(EnforcementAction.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )

    incident_ids = [a.incident_id for a in actions if a.incident_id]
    incidents_by_id = {}
    if incident_ids:
        incidents = db.query(Incident).filter(Incident.id.in_(incident_ids)).all()
        incidents_by_id = {inc.id: inc for inc in incidents}

    missing_ips = [a.ip_address for a in actions if not a.incident_id or a.incident_id not in incidents_by_id]
    latest_incidents_by_ip = {}
    if missing_ips:
        fallback_incidents = (
            db.query(Incident)
            .filter(Incident.source_ip.in_(missing_ips))
            .order_by(Incident.created_at.desc())
            .all()
        )
        for inc in fallback_incidents:
            if inc.source_ip not in latest_incidents_by_ip:
                latest_incidents_by_ip[inc.source_ip] = inc

    events: list[HealingEvent] = []
    for action in actions:
        inc = incidents_by_id.get(action.incident_id) or latest_incidents_by_ip.get(action.ip_address)
        attack_type = inc.attack_type if inc else ("Manual" if "MANUAL" in action.reason else "DDoS")
        threat_score = round(float(inc.threat_score), 4) if inc else 0.0
        duration_ms = 100 if action.status == "simulated" else 245

        events.append(
            HealingEvent(
                id=f"heal-{action.id}",
                timestamp=action.created_at.isoformat(),
                ip=action.ip_address,
                action="ISOLATED",
                attack_type=attack_type,
                trigger_score=threat_score,
                edges_severed=1,
                duration_ms=duration_ms,
                network_stability_before=88,
                network_stability_after=94,
                enforcement_status=action.status,
            )
        )

    # Edge case: Ensure currently blocked IPs without a prior action record are also included
    blocked_rows = db.query(BlockedIP).order_by(BlockedIP.blocked_at.desc()).all()
    seen_ips = {e.ip for e in events}
    for b in blocked_rows:
        if b.ip_address not in seen_ips:
            events.insert(
                0,
                HealingEvent(
                    id=f"heal-blocked-{b.id}",
                    timestamp=b.blocked_at.isoformat(),
                    ip=b.ip_address,
                    action="ISOLATED",
                    attack_type=b.attack_type or ("Manual" if b.reason == "MANUAL_OVERRIDE" else "DDoS"),
                    trigger_score=round(float(b.threat_score), 4),
                    edges_severed=1,
                    duration_ms=100 if b.enforcement_status == "simulated" else 245,
                    network_stability_before=88,
                    network_stability_after=94,
                    enforcement_status=b.enforcement_status,
                ),
            )
            seen_ips.add(b.ip_address)

    return {"events": events[:limit], "count": len(events[:limit])}
