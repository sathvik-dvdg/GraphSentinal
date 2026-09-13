# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident


def timeline_response(last: str = "60min") -> dict:
    minutes, bucket_minutes = _parse_window_minutes(last)
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)

    db = SessionLocal()
    try:
        incidents = (
            db.query(Incident.created_at)
            .filter(Incident.created_at >= start, Incident.created_at <= now)
            .all()
        )
        blocked_ips = (
            db.query(BlockedIP.blocked_at)
            .filter(BlockedIP.blocked_at >= start, BlockedIP.blocked_at <= now)
            .all()
        )

        incident_times = [
            r[0].replace(tzinfo=timezone.utc) if r[0].tzinfo is None else r[0]
            for r in incidents if r[0]
        ]
        blocked_times = [
            r[0].replace(tzinfo=timezone.utc) if r[0].tzinfo is None else r[0]
            for r in blocked_ips if r[0]
        ]

        points = []
        current = start
        while current < now:
            bucket_end = current + timedelta(minutes=bucket_minutes)
            t_count = sum(1 for t in incident_times if current <= t < bucket_end)
            b_count = sum(1 for t in blocked_times if current <= t < bucket_end)
            points.append({
                "time": current.isoformat(),
                "threats": t_count,
                "blocked": b_count,
            })
            current = bucket_end
    finally:
        db.close()

    return {"window": last, "bucket_minutes": bucket_minutes, "data_points": points}


def _parse_window_minutes(value: str) -> tuple[int, int]:
    """Parse time window parameter and return (total_window_minutes, bucket_step_minutes)."""
    val = (value or "60min").strip().lower()
    if val in ("all", "30d"):
        return 30 * 24 * 60, 24 * 60  # 30 days, 1-day buckets
    if val == "14d":
        return 14 * 24 * 60, 12 * 60  # 14 days, 12-hour buckets
    if val == "7d":
        return 7 * 24 * 60, 6 * 60    # 7 days, 6-hour buckets
    if val == "24h":
        return 24 * 60, 60            # 24 hours, 1-hour buckets
    if val == "6h":
        return 6 * 60, 15             # 6 hours, 15-minute buckets
    if val == "1h":
        return 60, 5                  # 1 hour, 5-minute buckets
    if val.endswith("d"):
        try:
            days = max(1, min(int(val[:-1]), 90))
            return days * 24 * 60, 24 * 60
        except ValueError:
            return 7 * 24 * 60, 6 * 60
    if val.endswith("h"):
        try:
            hours = max(1, min(int(val[:-1]), 720))
            bucket = 60 if hours >= 24 else (15 if hours >= 6 else 5)
            return hours * 60, bucket
        except ValueError:
            return 24 * 60, 60
    if val.endswith("min"):
        try:
            mins = max(5, min(int(val[:-3]), 24 * 60))
            bucket = 5 if mins <= 120 else 15
            return mins, bucket
        except ValueError:
            return 60, 5
    return 60, 5
