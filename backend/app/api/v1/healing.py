from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.database import get_db
from app.models.incident import EnforcementAction, Incident, iso_utc
from app.models.schemas import AttackType, HealingEvent, HealingEventsResponse

router = APIRouter()


@router.get("/healing", response_model=HealingEventsResponse)
async def get_healing_events(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    """Retrieve historical and active healing/isolation events using an efficient SQL join."""
    bounded_limit = max(1, min(limit, 100))

    rows = (
        db.query(EnforcementAction, Incident)
        .outerjoin(Incident, EnforcementAction.incident_id == Incident.id)
        .filter(EnforcementAction.action == "block")
        .order_by(EnforcementAction.created_at.desc())
        .limit(bounded_limit)
        .all()
    )

    events: list[HealingEvent] = []
    for action, incident in rows:
        attack_type: AttackType = "Unknown"
        if incident and incident.attack_type in (
            "DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk", "Manual", "Heuristic", "Unknown"
        ):
            attack_type = incident.attack_type  # type: ignore[assignment]
        elif "MANUAL" in action.reason:
            attack_type = "Manual"
        elif "GNN" in action.reason:
            attack_type = "DDoS"

        threat_score = round(float(incident.threat_score), 4) if incident else 0.0

        events.append(
            HealingEvent(
                id=f"heal-{action.id}",
                timestamp=iso_utc(action.created_at),
                ip=action.ip_address,
                action="ISOLATED",
                attack_type=attack_type,
                trigger_score=threat_score,
                # Error.md N2/H1 — real telemetry captured at block time
                # (enforcement_log columns). NULL on rows written before the
                # telemetry migration, which the frontend renders as '—'.
                edges_severed=action.edges_severed,
                duration_ms=action.duration_ms,
                network_stability_before=action.network_stability_before,
                network_stability_after=action.network_stability_after,
                enforcement_status=action.status,
            )
        )

    return {"events": events, "count": len(events)}
