# [WSL2]
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    enforcement_status: Mapped[str] = mapped_column(String(40), default="not_requested")
    # Error.md #34 — where the triggering flow data came from: ovs | demo |
    # manual | simulation. Lets forensics/alerts distinguish a real detection
    # from a demo-fallback or frontend-simulated one after the fact.
    data_source: Mapped[str] = mapped_column(String(20), default="manual")
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

