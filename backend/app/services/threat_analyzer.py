# [WSL2]
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident, utc_now
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.enforcement_agent import validate_mininet_ip
from app.services.enforcement_log import capture_network_stability, count_host_edges, log_enforcement_action
from app.services.self_healing import SelfHealingEngine


def score_to_severity_label(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.50:
        return "warning"
    return "info"


def score_to_severity_int(score: float) -> int:
    return max(1, min(10, int(round(score * 10))))


def infer_attack_type(ip: str, score: float, flows: list[dict[str, Any]]) -> str:
    """R-05 (M09-F01) — Robust deterministic heuristic attack classification with defensive attribute extraction."""
    ports = set()
    total_packets = 0
    http_bytes = 0

    for flow in flows:
        if not isinstance(flow, dict):
            continue
        try:
            p = int(flow.get("dst_port") or 0)
            if 0 <= p <= 65535:
                ports.add(p)
        except (ValueError, TypeError):
            pass

        try:
            pkt = int(flow.get("packet_count") or 0)
            if pkt > 0:
                total_packets += pkt
        except (ValueError, TypeError):
            pass

        try:
            b = int(flow.get("byte_count") or 0)
            p = int(flow.get("dst_port") or 0)
            if p in {80, 443, 8080} and b > 0:
                http_bytes += b
        except (ValueError, TypeError):
            pass

    if 22 in ports and total_packets > 250:
        return "SSHBrute"
    if len(ports) >= 5:
        return "PortScan"
    if http_bytes > 1_000_000:
        return "DoSHulk"
    if total_packets > 5000 or score >= 0.90:
        return "DDoS"
    return "Botnet"


class ThreatAnalyzer:
    def __init__(self):
        self.threshold = settings.threat_threshold
        self.healer = SelfHealingEngine()
        self.blockchain = BlockchainAdapter.get_instance()

    def evaluate(self, prediction: dict[str, Any], flows: list[Any]) -> tuple[list[dict], list[dict]]:
        flow_dicts = [flow.model_dump() if hasattr(flow, "model_dump") else dict(flow) for flow in flows]
        source_scores = dict(prediction.get("source_scores") or prediction.get("ip_scores") or {})
        alerts: list[dict] = []
        healing_events: list[dict] = []

        for ip, score_value in source_scores.items():
            score = float(score_value)
            if score < self.threshold:
                continue

            clean_ip = validate_mininet_ip(ip)
            related_flows = [flow for flow in flow_dicts if str(flow["src_ip"]) == ip]
            attack_type = infer_attack_type(clean_ip, score, related_flows)
            incident, is_new = self._create_incident(clean_ip, attack_type, score, related_flows)
            if incident is None:
                continue
            # A duplicate landed on an existing incident. If enforcement
            # already completed (enforced / simulated / already_blocked),
            # nothing new to do. If enforcement was not requested (e.g. crashed
            # before enforcement action) or is pending / failed, fall through
            # and retry instead of silently dropping the event.
            if not is_new and incident.enforcement_status not in ("not_requested", "pending_enforcement", "failed"):
                continue

            detection_reason = "HEURISTIC_DEGRADED" if prediction.get("ml_mode") == "degraded" else "GNN_DETECTED"
            # Error.md N2/H1 — capture real healing telemetry around the block.
            stability_before = capture_network_stability()
            edges_severed = count_host_edges(clean_ip)
            healing_event = self.healer.block_ip(
                clean_ip,
                reason=detection_reason,
                attack_type=attack_type,
                threat_score=score,
            )
            stability_after = capture_network_stability()
            # Surface the telemetry on the live event too, so the WebSocket
            # push carries it before the next REST poll reconciles from the DB.
            healing_event["edges_severed"] = edges_severed if edges_severed is not None else healing_event.get("edges_severed")
            healing_event["network_stability_before"] = stability_before
            healing_event["network_stability_after"] = stability_after
            healing_events.append(healing_event)
            tx_result = self.blockchain.store_incident(
                source_ip=clean_ip,
                attack_type=attack_type,
                severity=score_to_severity_int(score),
                is_blocked=True,
                incident_id=incident.id,
            )
            self._update_incident_after_actions(incident.id, tx_result, healing_event)
            log_enforcement_action(
                ip_address=clean_ip,
                action="block",
                reason=detection_reason,
                status=healing_event.get("enforcement_status", "unknown"),
                blockchain_tx=tx_result.get("tx_hash"),
                incident_id=incident.id,
                duration_ms=healing_event.get("duration_ms"),
                edges_severed=edges_severed,
                network_stability_before=stability_before,
                network_stability_after=stability_after,
            )
            alerts.append(self._alert_record(incident.id, clean_ip, attack_type, score, True, tx_result.get("tx_hash"), incident.data_source))


        return alerts, healing_events

    def _create_incident(
        self, ip: str, attack_type: str, score: float, flows: list[dict]
    ) -> tuple[Incident | None, bool]:
        """Returns (incident, is_new). On an idempotency-key collision, the
        existing row is returned instead of None so callers can decide
        whether to retry enforcement (see #15 in Error.md)."""
        key = self._idempotency_key(ip, attack_type, score, flows)
        db = SessionLocal()
        try:
            incident = Incident(
                source_ip=ip,
                attack_type=attack_type,
                threat_score=score,
                severity=score_to_severity_int(score),
                is_blocked=False,
                raw_flow_json=json.dumps(flows),
                idempotency_key=key,
                # N-06 (N06-SEC-02): Claim reservation on creation to prevent outbox double-submission race
                blockchain_status="submitting",
                blockchain_claimed_at=utc_now(),
                # Error.md #34 — every related flow was tagged by
                # flow_parser.py/simulateAttack() with where it came from;
                # take the first one's (they're all from the same batch).
                data_source=str(flows[0].get("data_source") or "manual") if flows else "manual",
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            return incident, True
        except IntegrityError:
            db.rollback()
            existing = db.query(Incident).filter(Incident.idempotency_key == key).one_or_none()
            return existing, False
        finally:
            db.close()

    @staticmethod
    def _update_incident_after_actions(incident_id: int, tx_result: dict, healing_event: dict) -> None:
        db = SessionLocal()
        try:
            incident = db.get(Incident, incident_id)
            if incident is not None:
                incident.is_blocked = True
                incident.blockchain_tx = tx_result.get("tx_hash")
                incident.enforcement_status = healing_event.get("enforcement_status", "unknown")
                # N-03: persist chain context so forensic reconciliation can
                # validate this tx against the correct chain/contract later.
                incident.blockchain_chain_id = tx_result.get("chain_id")
                incident.blockchain_contract_address = tx_result.get("contract_address")
                incident.blockchain_block_number = tx_result.get("block_number")
                # N-04: persist exact on-chain incident ID decoded from receipt event
                incident.blockchain_incident_id = tx_result.get("incident_id")
                # N-06: release claim lease and record final outbox status & pending timestamp
                incident.blockchain_claimed_at = None
                if tx_result.get("status") == "confirmed":
                    incident.blockchain_status = "confirmed"
                    incident.blockchain_last_error = None
                elif tx_result.get("status") == "pending" and tx_result.get("tx_hash"):
                    incident.blockchain_status = "pending"
                    incident.blockchain_pending_since = utc_now()
                    incident.blockchain_last_error = tx_result.get("error")
                else:
                    incident.blockchain_status = "retry"
                    incident.blockchain_retry_count = (incident.blockchain_retry_count or 0) + 1
                    incident.blockchain_last_error = tx_result.get("error", "Blockchain submission offline or failed")
                db.commit()

            # Keep BlockedIP.blockchain_tx in sync — self_healing.block_ip()
            # runs before the blockchain write completes, so it can never
            # know the tx hash itself (see Error.md #6).
            blocked_row = db.query(BlockedIP).filter(BlockedIP.ip_address == healing_event.get("ip")).one_or_none()
            if blocked_row is not None and tx_result.get("tx_hash"):
                blocked_row.blockchain_tx = tx_result["tx_hash"]
                db.commit()
        finally:
            db.close()


    @staticmethod
    def _alert_record(
        incident_id: int,
        ip: str,
        attack_type: str,
        score: float,
        is_blocked: bool,
        blockchain_tx: str | None,
        data_source: str = "manual",
    ) -> dict:
        return {
            "id": f"alert-{incident_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_ip": ip,
            "attack_type": attack_type,
            "severity": score_to_severity_label(score),
            "threat_score": round(score, 4),
            "description": f"{attack_type} detected from {ip} (score: {score:.2f})",
            "is_blocked": is_blocked,
            "blockchain_tx": blockchain_tx,
            "data_source": data_source,
        }

    @staticmethod
    def _idempotency_key(ip: str, attack_type: str, score: float, flows: list[dict] | None = None) -> str:
        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        # Include the actual targets/ports being attacked so two genuinely
        # different attack instances from the same IP in the same minute
        # don't collide into one suppressed incident (Error.md #15).
        targets = sorted({f"{f.get('dst_ip')}:{f.get('dst_port')}" for f in (flows or [])})
        evidence = "|".join(targets) or "no-evidence"
        raw = f"{ip}|{attack_type}|{round(score, 2)}|{score_to_severity_label(score)}|{bucket}|{evidence}"
        return sha256(raw.encode("utf-8")).hexdigest()

