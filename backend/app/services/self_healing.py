import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.incident import BlockedIP
from app.services.enforcement_agent import EnforcementAgent, EnforcementError, validate_mininet_ip


class SelfHealingEngine:
    def __init__(self, agent: EnforcementAgent | None = None):
        self.agent = agent or EnforcementAgent()

    def block_ip(
        self,
        ip: str,
        reason: str = "GNN_DETECTED",
        attack_type: str | None = None,
        threat_score: float = 0.0,
        db: Session | None = None,
    ) -> dict:
        clean_ip = validate_mininet_ip(ip)
        owns_db = db is None
        db = db or SessionLocal()
        try:
            start_time = time.perf_counter()
            status = self._enforce_block(clean_ip)
            duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            stmt = (
                sqlite_upsert(BlockedIP)
                .values(
                    ip_address=clean_ip,
                    reason=reason,
                    attack_type=attack_type,
                    threat_score=float(threat_score),
                    enforcement_status=status,
                    blocked_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_update(
                    index_elements=[BlockedIP.ip_address],
                    set_={
                        "reason": reason,
                        "attack_type": attack_type,
                        "threat_score": float(threat_score),
                        "enforcement_status": status,
                    },
                )
            )
            db.execute(stmt)
            db.commit()
            return self._healing_event(
                ip=clean_ip,
                attack_type=attack_type or ("Manual" if reason == "MANUAL_OVERRIDE" else "DDoS"),
                threat_score=threat_score,
                status=status,
                duration_ms=duration_ms,
            )
        finally:
            if owns_db:
                db.close()

    def unblock_ip(self, ip: str, db: Session | None = None) -> dict:
        clean_ip = validate_mininet_ip(ip)
        owns_db = db is None
        db = db or SessionLocal()
        try:
            try:
                status = self.agent.unblock_ip(clean_ip)
            except EnforcementError:
                status = "pending_unblock"
            db.query(BlockedIP).filter(BlockedIP.ip_address == clean_ip).delete()
            db.commit()
            return {"status": "unblocked", "ip": clean_ip, "enforcement_status": status}
        finally:
            if owns_db:
                db.close()

    def _enforce_block(self, clean_ip: str) -> str:
        try:
            return self.agent.block_ip(clean_ip)
        except EnforcementError:
            return "pending_enforcement"

    @staticmethod
    def _healing_event(
        ip: str,
        attack_type: str,
        threat_score: float,
        status: str,
        duration_ms: int | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": f"heal-{uuid4().hex[:10]}",
            "timestamp": now,
            "ip": ip,
            "action": "ISOLATED",
            "attack_type": attack_type,
            "trigger_score": round(float(threat_score), 4),
            "edges_severed": 1,
            "duration_ms": duration_ms,
            "network_stability_before": None,
            "network_stability_after": None,
            "enforcement_status": status,
        }

