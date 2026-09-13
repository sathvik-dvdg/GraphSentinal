# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from cachetools import TTLCache
from sqlalchemy import Integer, cast, func

from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident

_timeline_cache = TTLCache(maxsize=32, ttl=15)


def timeline_response(last: str = "60min") -> dict:
    cache_key = (last or "60min").strip().lower()
    cached = _timeline_cache.get(cache_key)
    if cached is not None:
        return cached

    minutes, bucket_minutes = _parse_window_minutes(cache_key)
    bucket_seconds = bucket_minutes * 60
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)

    db = SessionLocal()
    try:
        # SQL-level aggregation for Incidents (O(1) memory, database GROUP BY)
        inc_bucket = cast(cast(func.strftime("%s", Incident.created_at), Integer) / bucket_seconds, Integer)
        incident_counts = dict(
            db.query(inc_bucket, func.count(Incident.id))
            .filter(Incident.created_at >= start, Incident.created_at <= now)
            .group_by(inc_bucket)
            .all()
        )

        # SQL-level aggregation for BlockedIPs
        blk_bucket = cast(cast(func.strftime("%s", BlockedIP.blocked_at), Integer) / bucket_seconds, Integer)
        blocked_counts = dict(
            db.query(blk_bucket, func.count(BlockedIP.id))
            .filter(BlockedIP.blocked_at >= start, BlockedIP.blocked_at <= now)
            .group_by(blk_bucket)
            .all()
        )

        points = []
        current = start
        while current < now:
            epoch = int(current.timestamp())
            b_idx = epoch // bucket_seconds
            t_count = incident_counts.get(b_idx, 0)
            b_count = blocked_counts.get(b_idx, 0)
            points.append({
                "time": current.isoformat(),
                "threats": t_count,
                "blocked": b_count,
            })
            current += timedelta(minutes=bucket_minutes)

        result = {"window": last, "bucket_minutes": bucket_minutes, "data_points": points}
        _timeline_cache[cache_key] = result
        return result
    finally:
        db.close()


def _parse_window_minutes(value: str) -> tuple[int, int]:
    """Parse time window parameter and return (total_window_minutes, bucket_step_minutes)."""
    val = (value or "60min").strip().lower()
    if val in ("all", "30d"):
        return 30 * 24 * 60, 24 * 60  # 30 days, 1-day buckets (30 points)
    if val == "14d":
        return 14 * 24 * 60, 12 * 60  # 14 days, 12-hour buckets (28 points)
    if val == "7d":
        return 7 * 24 * 60, 6 * 60    # 7 days, 6-hour buckets (28 points)
    if val == "24h":
        return 24 * 60, 60            # 24 hours, 1-hour buckets (24 points)
    if val == "6h":
        return 6 * 60, 15             # 6 hours, 15-minute buckets (24 points)
    if val == "1h":
        return 60, 5                  # 1 hour, 5-minute buckets (12 points)
    if val.endswith("d"):
        try:
            days = max(1, min(int(val[:-1]), 30))
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
