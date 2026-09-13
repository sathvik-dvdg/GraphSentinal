# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from cachetools import TTLCache
# pyrefly: ignore [missing-import]
from fastapi import HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy import Integer, cast, func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.models.incident import BlockedIP, Incident

MAX_WINDOW_MINUTES = 30 * 24 * 60  # 43,200 minutes (30 days)
MAX_TIMELINE_POINTS = 300
_timeline_cache = TTLCache(maxsize=128, ttl=30)
_WINDOW_REGEX = re.compile(r"^(\d+)(min|h|d)$")


def _get_epoch_expr(column, session: Session):
    """Return dialect-specific epoch expression for portable time grouping."""
    dialect_name = "sqlite"
    try:
        bind = session.get_bind()
        if bind is not None and hasattr(bind, "dialect"):
            dialect_name = getattr(bind.dialect, "name", "sqlite")
    except Exception:
        bind = getattr(session, "bind", None)
        if bind is not None and hasattr(bind, "dialect"):
            dialect_name = getattr(bind.dialect, "name", "sqlite")

    if str(dialect_name).lower() in ("postgresql", "postgres"):
        return func.extract("epoch", column)
    return func.strftime("%s", column)


def _parse_window_minutes(value: str) -> tuple[int, int]:
    """Parse and validate time window parameter and return (total_window_minutes, bucket_step_minutes).

    Raises HTTPException(400) if the window exceeds MAX_WINDOW_MINUTES or is malformed.
    """
    val = (value or "60min").strip().lower()
    if len(val) > 20:
        raise HTTPException(
            status_code=400,
            detail=f"Window parameter too long. Maximum allowed window is {MAX_WINDOW_MINUTES} minutes (30 days).",
        )

    # Named standard presets
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
    if val in ("1h", "60min"):
        return 60, 5                  # 1 hour, 5-minute buckets (12 points)

    match = _WINDOW_REGEX.match(val)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid window parameter format. Expected format like '60min', '24h', '7d', '14d', '30d', or 'all'.",
        )

    num_str, unit = match.groups()
    try:
        amount = int(num_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid window number value.")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Window must be greater than zero.")

    if unit == "d":
        minutes = amount * 24 * 60
    elif unit == "h":
        minutes = amount * 60
    elif unit == "min":
        minutes = amount
    else:
        raise HTTPException(status_code=400, detail="Unsupported window time unit.")

    if minutes > MAX_WINDOW_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"Requested window exceeds maximum limit of 30 days ({MAX_WINDOW_MINUTES} minutes).",
        )

    # Determine optimal bucket size based on total duration to keep point count between ~12 and 40
    if minutes <= 60:
        bucket_minutes = 5
    elif minutes <= 360:      # <= 6 hours
        bucket_minutes = 15
    elif minutes <= 1440:     # <= 24 hours
        bucket_minutes = 60
    elif minutes <= 10080:    # <= 7 days
        bucket_minutes = 6 * 60
    elif minutes <= 20160:    # <= 14 days
        bucket_minutes = 12 * 60
    else:                     # <= 30 days
        bucket_minutes = 24 * 60

    return minutes, bucket_minutes


def timeline_response(db: Session, last: str = "60min") -> dict:
    """Generate time-bucketed aggregation for incidents and blocked IPs.

    Requires an injected Session adhering to the Unit of Work pattern.
    """
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

    # SQL-level aggregation for Incidents (portable across SQLite & PostgreSQL)
    epoch_inc = _get_epoch_expr(Incident.created_at, db)
    inc_bucket = cast(cast(epoch_inc, Integer) / bucket_seconds, Integer)
    incident_counts = dict(
        db.query(inc_bucket, func.count(Incident.id))
        .filter(Incident.created_at >= start, Incident.created_at <= now)
        .group_by(inc_bucket)
        .all()
    )

    # SQL-level aggregation for BlockedIPs
    epoch_blk = _get_epoch_expr(BlockedIP.blocked_at, db)
    blk_bucket = cast(cast(epoch_blk, Integer) / bucket_seconds, Integer)
    blocked_counts = dict(
        db.query(blk_bucket, func.count(BlockedIP.id))
        .filter(BlockedIP.blocked_at >= start, BlockedIP.blocked_at <= now)
        .group_by(blk_bucket)
        .all()
    )

    points = []
    current = start
    while current < now and len(points) < MAX_TIMELINE_POINTS:
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
