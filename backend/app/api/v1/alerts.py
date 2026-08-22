# [WSL2]
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.database import get_db
from app.models.incident import Incident
from app.models.schemas import AlertsResponse
from app.services.threat_analyzer import score_to_severity_label


router = APIRouter()

_SEVERITY_THRESHOLDS = {
    "critical": (0.75, 1.01),
    "warning": (0.50, 0.75),
    "info": (0.0, 0.50),
}


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    limit: int = 50,
    severity: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    query = db.query(Incident)
    if severity and severity in _SEVERITY_THRESHOLDS:
        low, high = _SEVERITY_THRESHOLDS[severity]
        query = query.filter(Incident.threat_score >= low, Incident.threat_score < high)
    rows = query.order_by(Incident.created_at.desc()).limit(min(limit, 200)).all()
    alerts = [
        {
            "id": f"alert-{row.id}",
            "timestamp": row.created_at.isoformat(),
            "source_ip": row.source_ip,
            "attack_type": row.attack_type,
            "severity": score_to_severity_label(row.threat_score),
            "threat_score": row.threat_score,
            "description": f"{row.attack_type} detected from {row.source_ip} (score: {row.threat_score:.2f})",
            "is_blocked": row.is_blocked,
            "blockchain_tx": row.blockchain_tx,
            "data_source": row.data_source,
        }
        for row in rows
    ]
    return {"alerts": alerts, "total": len(alerts)}


