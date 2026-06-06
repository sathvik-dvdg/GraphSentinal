# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident


def timeline_response(last: str = "60min") -> dict:
    minutes = _parse_window_minutes(last)
    bucket_minutes = 5
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    points = []
    current = start

    db = SessionLocal()
    try:
        while current < now:
            bucket_end = current + timedelta(minutes=bucket_minutes)
            threats = (
                db.query(Incident)
                .filter(Incident.created_at >= current)
                .filter(Incident.created_at < bucket_end)
                .count()
            )
            blocked = (
                db.query(BlockedIP)
                .filter(BlockedIP.blocked_at >= current)
                .filter(BlockedIP.blocked_at < bucket_end)
                .count()
            )
            points.append({"time": current.strftime("%H:%M"), "threats": threats, "blocked": blocked})
            current = bucket_end
    finally:
        db.close()

    return {"window": last, "bucket_minutes": bucket_minutes, "data_points": points}


def _parse_window_minutes(value: str) -> int:
    if value.endswith("min"):
        try:
            return max(5, min(int(value[:-3]), 24 * 60))
        except ValueError:
            return 60
    return 60

