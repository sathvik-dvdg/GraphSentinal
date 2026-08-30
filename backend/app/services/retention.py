# [WSL2]
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.models.incident import FlowSnapshot

logger = logging.getLogger("graphsentinel.retention")


def cleanup_expired_flow_snapshots(db: Session, retention_hours: int | None = None) -> int:
    """R-04 (M12-F02) — Clean up flow snapshots older than configured retention period.
    Deterministic, transaction-safe, and preserves all active security/incident state."""
    hours = retention_hours if retention_hours is not None else settings.flow_snapshot_retention_hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        deleted = (
            db.query(FlowSnapshot)
            .filter(FlowSnapshot.captured_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted > 0:
            logger.info("Cleaned up %d expired FlowSnapshot rows older than %s (retention: %dh)", deleted, cutoff.isoformat(), hours)
        return deleted
    except Exception as exc:
        db.rollback()
        logger.error("Error during flow snapshot retention cleanup: %s", exc)
        return 0
