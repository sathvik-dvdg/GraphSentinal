# [WSL2]
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, FlowSnapshot
from app.services.threat_analyzer import infer_attack_type

# The 10-host topology matches mininet/topologies/base_topology.py — this is
# the *configured* network, not observed traffic. Nodes are tagged
# "configured" vs "observed" in _build_nodes() so the UI never confuses a
# baseline placeholder with a host that actually sent/received traffic
# (Error.md #9).
_BASELINE_HOSTS = frozenset(f"10.0.0.{index}" for index in range(1, 11))

# How recent a persisted FlowSnapshot must be to rehydrate in-memory state
# after a backend restart (Error.md #10) — a small multiple of the OVS poll
# interval, so we don't resurrect traffic that's actually gone stale.
_REHYDRATE_WINDOW_MULTIPLIER = 3


def severity_status(score: float, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    if score >= 0.75:
        return "malicious"
    if score >= 0.50:
        return "suspicious"
    return "normal"


def attack_type_for(ip: str, score: float, flows: list[dict[str, Any]] | None = None) -> str | None:
    if score < 0.50:
        return None
    related = [flow for flow in (flows or []) if str(flow.get("src_ip")) == ip]
    if not related:
        return None
    return infer_attack_type(ip, score, related)


def _flow_dict(flow: Any) -> dict[str, Any]:
    if hasattr(flow, "model_dump"):
        return flow.model_dump()
    if hasattr(flow, "dict"):
        return flow.dict()
    return dict(flow)


class GraphState:
    def __init__(self):
        self._lock = Lock()
        self._flows: list[dict[str, Any]] = []
        self._prediction: dict[str, Any] = {"ip_scores": {}, "flow_scores": []}
        self._updated_at = datetime.now(timezone.utc)
        self._rehydrate_from_snapshots()

    def _rehydrate_from_snapshots(self) -> None:
        """On process start, in-memory state is empty even though SQLite has
        recent FlowSnapshot rows (Error.md #10). Pull the most recent window
        back in so a backend restart doesn't show a falsely-empty graph."""
        window = timedelta(seconds=settings.poll_interval_seconds * _REHYDRATE_WINDOW_MULTIPLIER)
        cutoff = datetime.now(timezone.utc) - window
        db = SessionLocal()
        try:
            rows = (
                db.query(FlowSnapshot)
                .filter(FlowSnapshot.captured_at >= cutoff)
                .order_by(FlowSnapshot.captured_at.desc())
                .limit(500)
                .all()
            )
        except Exception:
            rows = []
        finally:
            db.close()

        if not rows:
            return

        flows = []
        ip_scores: dict[str, float] = {}
        for row in rows:
            flows.append(
                {
                    "src_ip": row.src_ip,
                    "dst_ip": row.dst_ip,
                    "src_port": row.src_port,
                    "dst_port": row.dst_port,
                    "protocol": row.protocol,
                    "packet_count": row.packet_count,
                    "byte_count": row.byte_count,
                    "duration_sec": row.duration_sec,
                    "tcp_flags": row.tcp_flags,
                    "data_source": row.data_source,
                }
            )
            ip_scores.setdefault(row.src_ip, row.threat_score)
        self._flows = flows
        self._prediction = {"ip_scores": ip_scores, "flow_scores": []}
        self._updated_at = rows[0].captured_at.replace(tzinfo=timezone.utc)

    def update(self, flows: list[Any], prediction: dict[str, Any]) -> dict:
        flow_dicts = [_flow_dict(flow) for flow in flows]
        with self._lock:
            self._flows = flow_dicts
            self._prediction = prediction
            self._updated_at = datetime.now(timezone.utc)
        self._persist_snapshots(flow_dicts, prediction)
        return self.graph_response()

    def graph_response(self) -> dict:
        with self._lock:
            flows = list(self._flows)
            prediction = dict(self._prediction)
            updated_at = self._updated_at

        blocked = self._blocked_ips()
        ip_scores = dict(prediction.get("ip_scores") or {})
        nodes = self._build_nodes(flows, ip_scores, blocked)
        links = self._build_links(flows, ip_scores)
        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "total_nodes": len(nodes),
                "malicious_nodes": sum(1 for node in nodes if node["status"] == "malicious"),
                "blocked_nodes": sum(1 for node in nodes if node["status"] == "blocked"),
                "last_updated": updated_at.isoformat(),
            },
        }

    def stats_response(self) -> dict:
        graph = self.graph_response()
        nodes = graph["nodes"]
        links = graph["links"]
        active = sum(1 for node in nodes if node["status"] in {"malicious", "suspicious"})
        blocked = sum(1 for node in nodes if node["status"] == "blocked")
        system_health = max(0, 100 - active * 12 - blocked * 4)
        # Error.md #34 — breakdown of the current flow batch by provenance,
        # so an operator can see at a glance whether "live" traffic is
        # actually real OVS capture, or quietly all demo/simulated.
        data_sources: dict[str, int] = {}
        for flow in self._flows:
            key = str(flow.get("data_source") or "manual")
            data_sources[key] = data_sources.get(key, 0) + 1
        return {
            "total_nodes": len(nodes),
            "active_threats": active,
            "blocked_ips": blocked,
            "system_health": system_health,
            "total_packets": sum(link["packet_count"] for link in links),
            "total_bytes": sum(int(flow.get("byte_count") or 0) for flow in self._flows),
            "last_updated": graph["metadata"]["last_updated"],
            "enforcement_mode": settings.enforcement_mode,
            "demo_fallback_flows": settings.demo_fallback_flows,
            "data_sources": data_sources,
        }

    def _build_nodes(self, flows: list[dict[str, Any]], ip_scores: dict[str, float], blocked: set[str]) -> list[dict]:
        observed_hosts: set[str] = set()
        for flow in flows:
            observed_hosts.add(str(flow["src_ip"]))
            observed_hosts.add(str(flow["dst_ip"]))
        hosts = _BASELINE_HOSTS | observed_hosts

        flow_counts: dict[str, int] = {}
        byte_counts: dict[str, int] = {}
        # Error.md #34 — first data_source seen touching each host, so a node
        # that only ever appeared in demo/simulated traffic can be told apart
        # from one that showed up in a real OVS capture. First-seen (not
        # last-seen) so a host doesn't flip labels line-by-line within one
        # mixed batch — in practice a batch is homogeneous anyway (one flow
        # source per analyze_flows() call).
        node_sources: dict[str, str] = {}
        for flow in flows:
            src = str(flow["src_ip"])
            dst = str(flow["dst_ip"])
            byte_count = int(flow.get("byte_count") or 0)
            flow_counts[src] = flow_counts.get(src, 0) + 1
            flow_counts[dst] = flow_counts.get(dst, 0) + 1
            byte_counts[src] = byte_counts.get(src, 0) + byte_count
            byte_counts[dst] = byte_counts.get(dst, 0) + byte_count
            flow_source = str(flow.get("data_source") or "manual")
            node_sources.setdefault(src, flow_source)
            node_sources.setdefault(dst, flow_source)

        nodes = []
        for ip in sorted(hosts, key=self._ip_sort_key):
            score = round(float(ip_scores.get(ip, 0.03)), 4)
            is_blocked = ip in blocked
            nodes.append(
                {
                    "id": ip,
                    "label": self._label(ip),
                    "status": severity_status(score, is_blocked),
                    "threat_score": score,
                    "connections": flow_counts.get(ip, 0),
                    "bytes_total": byte_counts.get(ip, 0),
                    "attack_type": attack_type_for(ip, score, flows),
                    "is_blocked": is_blocked,
                    "source": "observed" if ip in observed_hosts else "configured",
                    "data_source": node_sources.get(ip),
                }
            )
        return nodes

    def _build_links(self, flows: list[dict[str, Any]], ip_scores: dict[str, float]) -> list[dict]:
        aggregates: dict[tuple[str, str], dict[str, Any]] = {}
        for flow in flows:
            key = (str(flow["src_ip"]), str(flow["dst_ip"]))
            row = aggregates.setdefault(key, {"packet_count": 0, "byte_count": 0, "data_source": None})
            row["packet_count"] += int(flow.get("packet_count") or 0)
            row["byte_count"] += int(flow.get("byte_count") or 0)
            if row["data_source"] is None:
                row["data_source"] = str(flow.get("data_source") or "manual")

        links = []
        for (src, dst), aggregate in aggregates.items():
            score = round(max(float(ip_scores.get(src, 0.0)), float(ip_scores.get(dst, 0.0))), 4)
            links.append(
                {
                    "source": src,
                    "target": dst,
                    "value": score,
                    "attack_type": attack_type_for(src, score, flows),
                    "packet_count": aggregate["packet_count"],
                    "data_source": aggregate["data_source"],
                }
            )
        return links

    def _persist_snapshots(self, flows: list[dict[str, Any]], prediction: dict[str, Any]) -> None:
        ip_scores = dict(prediction.get("ip_scores") or {})
        db = SessionLocal()
        try:
            for flow in flows:
                db.add(
                    FlowSnapshot(
                        src_ip=str(flow["src_ip"]),
                        dst_ip=str(flow["dst_ip"]),
                        src_port=int(flow.get("src_port") or 0),
                        dst_port=int(flow.get("dst_port") or 0),
                        protocol=str(flow.get("protocol") or "TCP"),
                        packet_count=int(flow.get("packet_count") or 0),
                        byte_count=int(flow.get("byte_count") or 0),
                        duration_sec=float(flow.get("duration_sec") or 1.0),
                        tcp_flags=int(flow.get("tcp_flags") or 0),
                        threat_score=float(ip_scores.get(str(flow["src_ip"]), 0.0)),
                        data_source=str(flow.get("data_source") or "manual"),
                    )
                )
            db.commit()
            # Retention (Error.md #30) — flow_snapshots would otherwise grow
            # unbounded on a long-running deployment. captured_at is indexed.
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.flow_snapshot_retention_hours)
            db.query(FlowSnapshot).filter(FlowSnapshot.captured_at < cutoff).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _blocked_ips(db: Session | None = None) -> set[str]:
        owns_db = db is None
        db = db or SessionLocal()
        try:
            return {row.ip_address for row in db.query(BlockedIP).all()}
        finally:
            if owns_db:
                db.close()

    @staticmethod
    def _label(ip: str) -> str:
        last = ip.split(".")[-1]
        return f"h{last}" if last.isdigit() else ip

    @staticmethod
    def _ip_sort_key(ip: str):
        parts = ip.split(".")
        if len(parts) == 4 and all(part.isdigit() for part in parts):
            return tuple(int(part) for part in parts)
        return (999, 999, 999, 999, ip)


graph_state = GraphState()

