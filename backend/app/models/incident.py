# [WSL2]
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime | None) -> str | None:
    """Serialize a stored datetime as an ISO string that always carries a
    timezone. SQLite drops tzinfo on write, so `created_at` comes back naive;
    without the +00:00 suffix the browser parses it as *local* time and shows
    events hours off. All stored datetimes are UTC by construction (utc_now)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    attack_type: Mapped[str] = mapped_column(String(50), nullable=False)
    threat_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_flow_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockchain_tx: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # N-03: chain context for forensic reconciliation. NULL on pre-N-03 rows
    # (accurate — those rows pre-date the metadata collection).
    blockchain_chain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blockchain_contract_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    blockchain_block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # N-04: exact on-chain incident ID emitted by IncidentLogged event.
    # NULL on pre-N-04 rows or when blockchain transaction fails/is offline.
    blockchain_incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # N-05: blockchain outbox state & retry tracking
    blockchain_status: Mapped[str | None] = mapped_column(String(30), default="no_tx", nullable=True)
    blockchain_retry_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    blockchain_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # N-06: atomic claim lease & pending timeout tracking
    blockchain_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blockchain_pending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    enforcement_status: Mapped[str] = mapped_column(String(40), default="not_requested")
    # Error.md #34 — where the triggering flow data came from: ovs | demo |
    # manual | simulation. Lets forensics/alerts distinguish a real detection
    # from a demo-fallback or frontend-simulated one after the fact.
    data_source: Mapped[str] = mapped_column(String(20), default="manual")
    # Error.md H5 — operator triage state, server-authoritative so it is
    # consistent across Alert Centre / Forensics / Threat Feed and survives a
    # refresh. open | acknowledged | resolved. Timestamps drive a real MTTA.
    alert_status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class BlockedIP(Base):
    __tablename__ = "blocked_ips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), default="GNN_DETECTED")
    attack_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    threat_score: Mapped[float] = mapped_column(Float, default=0.0)
    blockchain_tx: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enforcement_status: Mapped[str] = mapped_column(String(40), default="simulated")
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class EnforcementAction(Base):
    """Error.md #35 — append-only audit trail for every block/unblock attempt,
    covering what `incidents`/`blocked_ips` (current-state tables) can't:
    unblock events, reconciliation-driven reapply/remove actions, and
    failed/pending attempts that never made it into a BlockedIP row."""
    __tablename__ = "enforcement_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # block | unblock
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # GNN_DETECTED | MANUAL_OVERRIDE | RECONCILE_REAPPLY | RECONCILE_REMOVE
    status: Mapped[str] = mapped_column(String(40), nullable=False)  # enforced | simulated | pending_enforcement | pending_unblock | removed | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockchain_tx: Mapped[str | None] = mapped_column(String(120), nullable=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Error.md N2/H1 — real self-healing telemetry, captured at block time and
    # read back by GET /api/v1/healing instead of being hardcoded to None/1.
    # NULL on pre-migration rows and on paths that don't measure it.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edges_severed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    network_stability_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    network_stability_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class FlowSnapshot(Base):
    __tablename__ = "flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    src_port: Mapped[int] = mapped_column(Integer, default=0)
    dst_port: Mapped[int] = mapped_column(Integer, default=0)
    protocol: Mapped[str] = mapped_column(String(12), default="TCP")
    packet_count: Mapped[int] = mapped_column(Integer, default=0)
    byte_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float] = mapped_column(Float, default=1.0)
    tcp_flags: Mapped[int] = mapped_column(Integer, default=0)
    threat_score: Mapped[float] = mapped_column(Float, default=0.0)
    data_source: Mapped[str] = mapped_column(String(20), default="manual")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AuditLog(Base):
    """R-04 (M14-F02) — append-only administrative audit log capturing
    all control-plane mutations, settings adjustments, and manual enforcement actions."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_identity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_resource: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


