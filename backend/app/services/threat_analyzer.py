# [WSL2]
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.enforcement_log import log_enforcement_action
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
    ports = {int(flow.get("dst_port") or 0) for flow in flows}
    total_packets = sum(int(flow.get("packet_count") or 0) for flow in flows)
    http_bytes = sum(int(flow.get("byte_count") or 0) for flow in flows if int(flow.get("dst_port") or 0) in {80, 443, 8080})
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

            related_flows = [flow for flow in flow_dicts if str(flow["src_ip"]) == ip]
            attack_type = infer_attack_type(ip, score, related_flows)
            incident, is_new = self._create_incident(ip, attack_type, score, related_flows)
            if incident is None:
                continue
            # A duplicate landed on an existing incident whose enforcement
            # already completed — nothing new to do. If enforcement is still
            # pending (e.g. the daemon was down on the first attempt), fall
            # through and retry instead of silently dropping the event.
            if not is_new and incident.enforcement_status != "pending_enforcement":
                continue

            healing_event = self.healer.block_ip(
                ip,
                reason="GNN_DETECTED",
                attack_type=attack_type,
                threat_score=score,
            )
            healing_events.append(healing_event)
            tx_result = self.blockchain.store_incident(
                source_ip=ip,
                attack_type=attack_type,
                severity=score_to_severity_int(score),
                is_blocked=True,
                incident_id=incident.id,
            )
            self._update_incident_after_actions(incident.id, tx_result, healing_event)
            log_enforcement_action(
                ip_address=ip,
                action="block",
                reason="GNN_DETECTED",
                status=healing_event.get("enforcement_status", "unknown"),
                blockchain_tx=tx_result.get("tx_hash"),
                incident_id=incident.id,
            )
            alerts.append(self._alert_record(incident.id, ip, attack_type, score, True, tx_result.get("tx_hash"), incident.data_source))

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
                # N-05: persist outbox state and error if pending/failed/offline
                if tx_result.get("status") == "confirmed":
                    incident.blockchain_status = "confirmed"
                    incident.blockchain_last_error = None
                elif tx_result.get("status") == "pending" and tx_result.get("tx_hash"):
                    incident.blockchain_status = "pending"
                    incident.blockchain_last_error = tx_result.get("error")
                else:
                    incident.blockchain_status = tx_result.get("status", "no_tx")
                    incident.blockchain_last_error = tx_result.get("error")
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

