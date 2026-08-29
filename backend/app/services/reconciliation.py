# [WSL2]
"""OVS ↔ SQLite reconciliation.

Every 10 seconds, compare `blocked_ips` rows with `ovs-ofctl dump-flows`.
- If SQLite says blocked but OVS rule is missing → reapply the rule.
- If OVS has a GraphSentinel drop rule with no SQLite row → remove it.
"""
from __future__ import annotations

import re
import subprocess
import threading
import time
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.models.incident import BlockedIP, Incident
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.enforcement_log import log_enforcement_action


_RECONCILE_INTERVAL = 10  # seconds


def _send_to_daemon(payload: dict) -> dict:
    import json
    import socket
    payload["token"] = getattr(settings, "daemon_token", None)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3.0)
        sock.connect((settings.daemon_host, settings.daemon_port))
        sock.sendall(json.dumps(payload).encode("utf-8"))
        
        response_data = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data.append(chunk)
            
        response = b"".join(response_data)
        if not response:
            raise RuntimeError("Empty response from daemon")
        return json.loads(response.decode("utf-8"))


def _parse_blocked_from_ovs(switch: str) -> set[str]:
    """Parse OVS dump-flows output for GraphSentinel drop rules (priority=1000)."""
    try:
        result = _send_to_daemon({"action": "dump_flows", "switch": switch})
        if result.get("status") != "success":
            return set()
        raw_flows = result.get("output", "")
    except Exception:
        return set()

    blocked: set[str] = set()
    for line in raw_flows.splitlines():
        if "priority=1000" not in line or "actions=drop" not in line:
            continue
        match = re.search(r"nw_src=([0-9.]+)", line)
        if match:
            blocked.add(match.group(1))
    return blocked


def _sqlite_blocked_ips() -> set[str]:
    db = SessionLocal()
    try:
        return {row.ip_address for row in db.query(BlockedIP).all()}
    finally:
        db.close()


def reconcile_once(switch: str | None = None) -> dict[str, Any]:
    """Run a single OVS reconciliation pass. Returns a summary dict."""
    switch = switch or settings.enforcement_switch
    if settings.enforcement_mode != "ovs":
        return {"status": "skipped", "reason": "enforcement_mode is not ovs"}

    ovs_blocked = _parse_blocked_from_ovs(switch)
    db_blocked = _sqlite_blocked_ips()

    reapplied: list[str] = []
    removed: list[str] = []

    # SQLite says blocked but OVS rule is missing → reapply
    for ip in db_blocked - ovs_blocked:
        try:
            res = _send_to_daemon({"action": "block", "switch": switch, "ip": ip})
            if res.get("status") != "success":
                raise RuntimeError(res.get("error", "Unknown error"))
            reapplied.append(ip)
            print(f"[Reconcile] Reapplied OVS rule for {ip}")
            log_enforcement_action(ip_address=ip, action="block", reason="RECONCILE_REAPPLY", status="enforced")
        except Exception as exc:
            print(f"[Reconcile] Failed to reapply OVS rule for {ip}: {exc}")
            log_enforcement_action(ip_address=ip, action="block", reason="RECONCILE_REAPPLY", status="failed", error=str(exc))

    # OVS has a drop rule but no SQLite row → remove stale rule
    for ip in ovs_blocked - db_blocked:
        try:
            res = _send_to_daemon({"action": "unblock", "switch": switch, "ip": ip})
            if res.get("status") != "success":
                raise RuntimeError(res.get("error", "Unknown error"))
            removed.append(ip)
            print(f"[Reconcile] Removed stale OVS rule for {ip}")
            log_enforcement_action(ip_address=ip, action="unblock", reason="RECONCILE_REMOVE", status="removed")
        except Exception as exc:
            print(f"[Reconcile] Failed to remove stale OVS rule for {ip}: {exc}")
            log_enforcement_action(ip_address=ip, action="unblock", reason="RECONCILE_REMOVE", status="failed", error=str(exc))

    return {
        "status": "ok",
        "reapplied": reapplied,
        "removed": removed,
        "db_blocked": len(db_blocked),
        "ovs_blocked": len(ovs_blocked),
    }


def reconcile_blockchain_outbox(max_batch: int = 10) -> dict[str, Any]:
    """N-05 — Reconcile pending blockchain transactions and retry unwritten incidents.

    1. Pending Reconciliation: For rows with blockchain_tx and status='pending' (or missing incident_id),
       checks live receipt on-chain and updates blockchain_incident_id, block_number, and status.
    2. Outbox Retry: For high-threat / blocked incidents with no blockchain_tx and retry_count < max_retries,
       attempts to store them on-chain once RPC is online.
    """
    adapter = BlockchainAdapter.get_instance()
    if not adapter._connected or adapter.client is None:
        return {"status": "offline", "reason": adapter.error or "blockchain offline"}

    db = SessionLocal()
    pending_reconciled = 0
    retried_success = 0
    retried_failed = 0

    try:
        w3 = adapter.client.w3
        contract = adapter.client.contract

        # ── 1. Reconcile Pending Transactions ────────────────────────────────
        pending_rows = (
            db.query(Incident)
            .filter(
                Incident.blockchain_tx.isnot(None),
                Incident.blockchain_incident_id.is_(None),
                Incident.attack_type != "Manual-Unblock",
            )
            .limit(max_batch)
            .all()
        )

        for row in pending_rows:
            try:
                tx_hash = row.blockchain_tx
                if not tx_hash.startswith("0x"):
                    tx_hash = "0x" + tx_hash
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    row.blockchain_block_number = receipt.get("blockNumber")
                    if receipt.get("status") == 1:
                        processed = contract.events.IncidentLogged().process_receipt(receipt)
                        if processed:
                            row.blockchain_incident_id = processed[0]["args"]["id"]
                        row.blockchain_status = "confirmed"
                        row.blockchain_last_error = None
                        pending_reconciled += 1
                    else:
                        row.blockchain_status = "failed"
                        row.blockchain_last_error = "Transaction reverted on-chain"
                    db.commit()
            except Exception as exc:
                row.blockchain_retry_count = (row.blockchain_retry_count or 0) + 1
                row.blockchain_last_error = str(exc)
                db.commit()

        # ── 2. Retry Unwritten Eligible Incidents (Outbox Backfill) ──────────
        max_retries = getattr(settings, "blockchain_max_retries", 5)
        eligible_unwritten = (
            db.query(Incident)
            .filter(
                Incident.blockchain_tx.is_(None),
                (Incident.threat_score >= settings.threat_threshold) | (Incident.is_blocked == True),  # noqa: E712
                (Incident.blockchain_retry_count < max_retries) | (Incident.blockchain_retry_count.is_(None)),
                Incident.blockchain_status != "permanent_failure",
            )
            .order_by(Incident.id.asc())
            .limit(max_batch)
            .all()
        )

        for row in eligible_unwritten:
            if row.blockchain_tx is not None:
                continue

            result = adapter.store_incident(
                source_ip=row.source_ip,
                attack_type=row.attack_type,
                severity=row.severity,
                is_blocked=row.is_blocked,
                incident_id=row.id,
            )

            if result.get("status") == "confirmed":
                row.blockchain_tx = result.get("tx_hash")
                row.blockchain_incident_id = result.get("incident_id")
                row.blockchain_chain_id = result.get("chain_id")
                row.blockchain_contract_address = result.get("contract_address")
                row.blockchain_block_number = result.get("block_number")
                row.blockchain_status = "confirmed"
                row.blockchain_last_error = None
                retried_success += 1
            elif result.get("status") == "pending" and result.get("tx_hash"):
                row.blockchain_tx = result.get("tx_hash")
                row.blockchain_chain_id = result.get("chain_id")
                row.blockchain_contract_address = result.get("contract_address")
                row.blockchain_status = "pending"
                row.blockchain_last_error = result.get("error")
                retried_success += 1
            else:
                row.blockchain_retry_count = (row.blockchain_retry_count or 0) + 1
                row.blockchain_last_error = result.get("error", "Failed to write to blockchain")
                if row.blockchain_retry_count >= max_retries:
                    row.blockchain_status = "permanent_failure"
                else:
                    row.blockchain_status = "retry"
                retried_failed += 1
            db.commit()

        return {
            "status": "ok",
            "pending_reconciled": pending_reconciled,
            "retried_success": retried_success,
            "retried_failed": retried_failed,
        }
    finally:
        db.close()


class ReconciliationWorker:
    """Background thread that runs OVS ↔ SQLite and Blockchain Outbox reconciliation periodically."""

    def __init__(self, interval: int = _RECONCILE_INTERVAL):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.last_result: dict[str, Any] = {}

    def start(self) -> None:
        self._thread.start()
        print(f"[Reconcile] Worker started, interval={self.interval}s")

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                ovs_result = reconcile_once() if settings.enforcement_mode == "ovs" else {"status": "skipped"}
                bc_result = reconcile_blockchain_outbox()
                self.last_result = {
                    "ovs": ovs_result,
                    "blockchain": bc_result,
                    "status": "ok" if (ovs_result.get("status") != "error" and bc_result.get("status") != "error") else "degraded",
                }
            except Exception as exc:
                self.last_result = {"status": "error", "error": str(exc)}
                print(f"[Reconcile] Error: {exc}")
            time.sleep(self.interval)
