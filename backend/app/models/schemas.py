# [WSL2]
from math import isfinite
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


NodeStatus = Literal["normal", "suspicious", "malicious", "blocked"]
AttackType = Literal["DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk"]
Severity = Literal["info", "warning", "critical"]
BlockAction = Literal["block", "unblock"]
BlockReason = Literal["GNN_DETECTED", "MANUAL_OVERRIDE"]
TxStatus = Literal["confirmed", "pending", "failed", "mock", "error"]


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
    fwd_packets: Optional[int] = Field(default=None, ge=0)
    bwd_packets: Optional[int] = Field(default=None, ge=0)
    fwd_bytes: Optional[int] = Field(default=None, ge=0)
    bwd_bytes: Optional[int] = Field(default=None, ge=0)
    syn_flag_count: Optional[int] = Field(default=None, ge=0)
    flow_bytes_per_s: Optional[float] = Field(default=None, ge=0)

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


class LinkData(BaseModel):
    source: str
    target: str
    value: float = Field(ge=0.0, le=1.0)
    attack_type: Optional[AttackType] = None
    packet_count: int = Field(ge=0)


class GraphResponse(BaseModel):
    nodes: list[NodeData]
    links: list[LinkData]
    metadata: dict


class AlertRecord(BaseModel):
    id: str
    timestamp: str
    source_ip: str
    attack_type: AttackType
    severity: Severity
    threat_score: float
    description: str
    is_blocked: bool
    blockchain_tx: Optional[str] = None


class AlertsResponse(BaseModel):
    alerts: list[AlertRecord]
    total: int


class BlockedIPRecord(BaseModel):
    ip: str
    blocked_at: str
    reason: BlockReason
    attack_type: Optional[AttackType] = None
    threat_score: float
    blockchain_tx: Optional[str] = None


class BlockedResponse(BaseModel):
    blocked_ips: list[BlockedIPRecord]
    count: int


class BlockRequest(BaseModel):
    ip: str
    reason: BlockReason = "MANUAL_OVERRIDE"
    action: BlockAction = "block"


class BlockResponse(BaseModel):
    status: Literal["blocked", "unblocked"]
    ip: str
    blockchain_tx: Optional[str] = None


class BlockchainStoreRequest(BaseModel):
    source_ip: str
    attack_type: AttackType
    severity: int = Field(ge=1, le=10)
    is_blocked: bool
    sqlite_incident_id: int


class BlockchainStoreResponse(BaseModel):
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
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
    edges_severed: int
    duration_ms: int
    network_stability_before: int
    network_stability_after: int

