# [WSL2]
from __future__ import annotations

from ipaddress import ip_address
from math import isfinite
from typing import Literal, Optional

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator


NodeStatus = Literal["normal", "suspicious", "malicious", "blocked"]
AttackType = Literal["DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk", "Manual", "Heuristic", "Unknown"]
Severity = Literal["info", "warning", "critical"]
BlockAction = Literal["block", "unblock"]
BlockReason = Literal["GNN_DETECTED", "HEURISTIC_DEGRADED", "MANUAL_OVERRIDE"]
TxStatus = Literal["confirmed", "pending", "failed", "offline", "error"]



class FlowRecord(BaseModel):
    src_ip: str
    dst_ip: str
    src_port: int = Field(default=0, ge=0, le=65535)
    dst_port: int = Field(ge=0, le=65535)
    protocol: str = "TCP"
    packet_count: int = Field(default=0, ge=0)
    byte_count: int = Field(default=0, ge=0)
    duration_sec: float = Field(default=1.0, gt=0)
    tcp_flags: int = Field(default=0, ge=0)
    # Error.md #34 — provenance of this flow: "ovs" (real capture, set by
    # flow_parser.py), "demo" (synthetic fallback, also flow_parser.py),
    # "simulation" (frontend Simulate button), or the default "manual" for
    # any other direct /api/v1/analyze submission.
    data_source: str = "manual"
    fwd_packets: Optional[int] = Field(default=None, ge=0)
    bwd_packets: Optional[int] = Field(default=None, ge=0)
    fwd_bytes: Optional[int] = Field(default=None, ge=0)
    bwd_bytes: Optional[int] = Field(default=None, ge=0)
    syn_flag_count: Optional[int] = Field(default=None, ge=0)
    flow_bytes_per_s: Optional[float] = Field(default=None, ge=0)

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        """R-06 (M11-F01) — Reject malformed IP strings at the Pydantic schema
        boundary before they can reach graph construction, snapshot persistence,
        or enforcement.  Accepts standard IPv4 dotted-decimal addresses only
        (matching the Mininet / OVS deployment target)."""
        try:
            parsed = ip_address(value.strip())
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid IP address: {value!r}") from exc
        # Enforce IPv4 only — the Mininet/OVS topology and enforcement CIDR
        # (10.0.0.0/24) are strictly IPv4.  Accepting IPv6 here would create
        # a validation gap: the address would pass schema validation but be
        # rejected later by validate_mininet_ip() or silently bypass
        # enforcement.
        if parsed.version != 4:
            raise ValueError(f"Only IPv4 addresses are supported, got IPv6: {value!r}")
        return str(parsed)

    @field_validator("duration_sec", "flow_bytes_per_s")
    @classmethod
    def finite_float(cls, value):
        if value is not None and not isfinite(float(value)):
            raise ValueError("flow numeric values must be finite")
        return value


class AnalyzeRequest(BaseModel):
    flows: list[FlowRecord]


class NodeData(BaseModel):
    id: str
    label: str
    status: NodeStatus
    threat_score: float = Field(ge=0.0, le=1.0)
    connections: int = Field(ge=0)
    bytes_total: int = Field(ge=0)
    attack_type: Optional[AttackType] = None
    is_blocked: bool
    source: Literal["configured", "observed"] = "configured"
    # Error.md #34 — provenance of the flow(s) that involved this host this
    # batch; None for a configured-but-unobserved host (no flow to derive it from).
    data_source: Optional[str] = None


class LinkData(BaseModel):
    source: str
    target: str
    value: float = Field(ge=0.0, le=1.0)
    attack_type: Optional[AttackType] = None
    packet_count: int = Field(ge=0)
    data_source: Optional[str] = None


class GraphResponse(BaseModel):
    nodes: list[NodeData]
    links: list[LinkData]
    metadata: dict


class AlertRecord(BaseModel):
    id: str
    timestamp: str
    source_ip: str
    # str, not AttackType: /api/v1/alerts queries the same Incident table
    # manual block/unblock rows land in, and those carry attack_type
    # "Manual"/"Manual-Unblock" — not a GNN-classified attack type. Using
    # the strict Literal here would 500 the whole endpoint the first time a
    # manual block appears in the results.
    attack_type: str
    severity: Severity
    threat_score: float
    description: str
    is_blocked: bool
    blockchain_tx: Optional[str] = None
    data_source: str = "manual"
    # Error.md H5 — server-authoritative triage state
    alert_status: str = "open"
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None


class AlertsResponse(BaseModel):
    alerts: list[AlertRecord]
    total: int


AlertStatus = Literal["open", "acknowledged", "resolved"]


class IncidentStatusUpdateRequest(BaseModel):
    status: AlertStatus


class IncidentStatusResponse(BaseModel):
    id: int
    alert_status: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None


class BlockedIPRecord(BaseModel):
    ip: str
    blocked_at: str
    reason: BlockReason
    attack_type: Optional[AttackType] = None
    threat_score: float
    blockchain_tx: Optional[str] = None
    # Was already returned by GET /blocked but missing from this schema —
    # a real pre-existing drift this pass's response_model= work caught
    # (Error.md #25): applying response_model without this would have
    # silently stripped the field from every response.
    enforcement_status: str = "simulated"


class BlockedResponse(BaseModel):
    blocked_ips: list[BlockedIPRecord]
    count: int


class BlockRequest(BaseModel):
    ip: IPvAnyAddress
    reason: BlockReason = "MANUAL_OVERRIDE"
    action: BlockAction = "block"


class BlockResponse(BaseModel):
    status: Literal["blocked", "unblocked"]
    ip: str
    blockchain_tx: Optional[str] = None
    # Was already returned by POST /block for both actions but missing from
    # this schema — same class of drift response_model= would have silently
    # stripped (Error.md #25).
    enforcement_status: str
    healing_event: Optional[HealingEvent] = None


class BlockchainStoreRequest(BaseModel):
    source_ip: str
    attack_type: AttackType
    severity: int = Field(ge=1, le=10)
    is_blocked: bool
    sqlite_incident_id: int


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class SettingsUpdateRequest(BaseModel):
    # Error.md #19 — the only Settings-page control with a real, single-value
    # backend equivalent. Everything else on that page (a separate
    # detection-vs-isolate threshold, lateral-movement sensitivity, live
    # Ganache reconnection) has no matching backend concept to wire to.
    threat_threshold: float = Field(ge=0.0, le=1.0)


class BlockchainStoreResponse(BaseModel):
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    incident_id: Optional[int] = None
    status: TxStatus
    gas_used: Optional[int] = None
    error: Optional[str] = None


class StatsResponse(BaseModel):
    total_nodes: int
    active_threats: int
    blocked_ips: int
    system_health: int
    total_packets: int
    total_bytes: int
    last_updated: str
    enforcement_mode: str
    demo_fallback_flows: bool
    data_sources: dict[str, int] = Field(default_factory=dict)


class TimelinePoint(BaseModel):
    time: str
    threats: int
    blocked: int


class TimelineResponse(BaseModel):
    window: str
    bucket_minutes: int
    data_points: list[TimelinePoint]


class HealingEvent(BaseModel):
    id: str
    timestamp: str
    ip: str
    action: Literal["ISOLATED"]
    attack_type: AttackType
    trigger_score: float
    edges_severed: Optional[int] = None
    duration_ms: Optional[int] = None
    network_stability_before: Optional[int] = None
    network_stability_after: Optional[int] = None
    enforcement_status: str


class HealingEventsResponse(BaseModel):
    events: list[HealingEvent]
    count: int


class IncidentRecord(BaseModel):
    id: int
    source_ip: str
    attack_type: str
    threat_score: float
    severity: int
    is_blocked: bool
    blockchain_tx: Optional[str] = None
    # N-03: chain context and reconciliation status
    blockchain_chain_id: Optional[int] = None
    blockchain_contract_address: Optional[str] = None
    blockchain_block_number: Optional[int] = None
    # N-04: on-chain incident ID emitted by IncidentLogged event
    blockchain_incident_id: Optional[int] = None
    # N-05: outbox status, retries, and errors
    blockchain_status: Optional[str] = None
    blockchain_retry_count: Optional[int] = None
    blockchain_last_error: Optional[str] = None
    # tx_status: confirmed | missing | wrong_contract | unavailable | no_tx | pending
    tx_status: Optional[str] = None
    created_at: str
    enforcement_status: str
    data_source: str = "manual"
    # Error.md H5 — server-authoritative triage state (shared with alerts)
    alert_status: str = "open"
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None


class ChainRecord(BaseModel):
    id: Optional[int] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    incident_hash: Optional[str] = None
    timestamp: Optional[str] = None
    source_ip: Optional[str] = None
    attack_type: Optional[str] = None
    severity: Optional[int] = None
    is_blocked: Optional[bool] = None
    gas_used: Optional[int] = None
    status: Optional[str] = "confirmed"


class ForensicsResponse(BaseModel):
    incidents: list[IncidentRecord]
    blockchain_records: list[ChainRecord]
    blockchain_error: Optional[str] = None
    total_incidents: int
    total_on_chain: int
    chain_id: Optional[int] = None
    contract_address: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    has_more: Optional[bool] = None


class SettingsResponse(BaseModel):
    threat_threshold: float
    enforcement_mode: str
    demo_fallback_flows: bool
    ganache_url: str
    contract_address: Optional[str] = None


class SettingsUpdateResponse(BaseModel):
    threat_threshold: float


# Error.md #35 — durable enforcement audit trail
# Error.md N3 — `action`/`reason` are stored as free strings in the DB
# (incident.py:71-72). Keeping these as strict Literals here meant a single
# row written with any out-of-set value (a new call site, a migrated older
# DB, a direct API client) would fail FastAPI response validation and 500
# the whole endpoint. These fields are display-only in the UI, so a plain
# str is the correct type — the writers still pass known values.
EnforcementActionType = str
EnforcementActionReason = str


class EnforcementActionRecord(BaseModel):
    id: int
    ip_address: str
    action: str
    reason: str
    status: str
    error: Optional[str] = None
    blockchain_tx: Optional[str] = None
    incident_id: Optional[int] = None
    created_at: str


class EnforcementActionsResponse(BaseModel):
    actions: list[EnforcementActionRecord]
    count: int


class AuditLogRecord(BaseModel):
    id: int
    actor_identity: str
    actor_role: str
    action: str
    target_resource: str
    details: Optional[str] = None
    status: str
    request_id: Optional[str] = None
    timestamp: str


class AuditLogsResponse(BaseModel):
    audit_logs: list[AuditLogRecord]
    count: int
    total: int
    limit: Optional[int] = None
    offset: Optional[int] = None
    has_more: Optional[bool] = None



class FlowScore(BaseModel):
    flow_index: int
    src_ip: str
    dst_ip: str
    score: float


class AnalyzeResponse(BaseModel):
    predictions: dict[str, float]
    flow_scores: list[FlowScore]
    incidents_created: list[str]
    healing_triggered: list[str]
    graph_snapshot: GraphResponse
    alerts: list[AlertRecord]
    healing_events: list[HealingEvent]
    ml_mode: Optional[str] = None
    degraded_reason: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str = "operator"
    expires_in_hours: float


class LogoutResponse(BaseModel):
    status: Literal["logged_out"]


class MeResponse(BaseModel):
    username: str
    role: str = "operator"


class MLReloadResponse(BaseModel):
    status: Literal["ok", "degraded"]
    mode: Literal["model", "degraded"]
    degraded_reason: Optional[str] = None
    weights_path: Optional[str] = None

