# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from cachetools import TTLCache
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident

_timeline_cache = TTLCache(maxsize=64, ttl=30)


def _get_epoch_expr(column, bind):
    """Return dialect-specific epoch expression for portable time grouping."""
    dialect = bind.dialect.name if bind else "sqlite"
    if dialect in ("postgresql", "postgres"):
        return func.extract("epoch", column)
    return func.strftime("%s", column)


def timeline_response(last: str = "60min", db: Optional[Session] = None) -> dict:
    raw_window = (last or "60min").strip().lower()
    minutes, bucket_minutes = _parse_window_minutes(raw_window)
    bucket_seconds = bucket_minutes * 60

    # Snap time to nearest bucket boundary to stabilize caching and chart alignment
    now_ts = int(datetime.now(timezone.utc).timestamp())
    snapped_now_ts = (now_ts // bucket_seconds) * bucket_seconds
    now = datetime.fromtimestamp(snapped_now_ts, tz=timezone.utc)
    start = now - timedelta(minutes=minutes)

    cache_key = f"{raw_window}_{snapped_now_ts}"
    cached = _timeline_cache.get(cache_key)
    if cached is not None:
        return cached

    owns_db = db is None
    session = db or SessionLocal()
    try:
        bind = session.get_bind() if hasattr(session, "get_bind") else session.bind

        # SQL-level aggregation for Incidents (portable across SQLite & PostgreSQL)
        epoch_inc = _get_epoch_expr(Incident.created_at, bind)
        inc_bucket = cast(cast(epoch_inc, Integer) / bucket_seconds, Integer)
        incident_counts = dict(
            session.query(inc_bucket, func.count(Incident.id))
            .filter(Incident.created_at >= start, Incident.created_at <= now)
            .group_by(inc_bucket)
            .all()
        )

        # SQL-level aggregation for BlockedIPs
        epoch_blk = _get_epoch_expr(BlockedIP.blocked_at, bind)
        blk_bucket = cast(cast(epoch_blk, Integer) / bucket_seconds, Integer)
        blocked_counts = dict(
            session.query(blk_bucket, func.count(BlockedIP.id))
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
        if owns_db:
            session.close()


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
