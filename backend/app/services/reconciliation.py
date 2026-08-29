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
from datetime import datetime, timezone, timedelta
from typing import Any

from web3.exceptions import TransactionNotFound

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
    """N-05 / N-06 — Reconcile pending blockchain transactions and retry unwritten incidents.

    1. Pending Reconciliation: For rows with blockchain_tx and status='pending' (or missing incident_id),
       checks live receipt on-chain. If mined, updates incident_id, block_number, and status='confirmed'.
       If pending exceeds blockchain_pending_timeout_seconds, transitions to retryable state.
    2. Outbox Retry (Atomic Claim): For unwritten incidents, atomically acquires a lease via
       blockchain_status='submitting' to eliminate race conditions between ingestion and worker,
       then stores them on-chain once RPC is online.
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
        now = datetime.now(timezone.utc)
        pending_timeout = getattr(settings, "blockchain_pending_timeout_seconds", 180)
        max_retries = getattr(settings, "blockchain_max_retries", 5)
        claim_timeout = getattr(settings, "blockchain_claim_timeout_seconds", 60)
        lease_cutoff = now - timedelta(seconds=claim_timeout)

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
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                except TransactionNotFound:
                    receipt = None
                if receipt is not None:
                    row.blockchain_block_number = receipt.get("blockNumber")
                    if receipt.get("status") == 1:
                        processed = contract.events.IncidentLogged().process_receipt(receipt)
                        if processed:
                            row.blockchain_incident_id = processed[0]["args"]["id"]
                        row.blockchain_status = "confirmed"
                        row.blockchain_last_error = None
                        row.blockchain_pending_since = None
                        pending_reconciled += 1
                    else:
                        row.blockchain_status = "failed"
                        row.blockchain_last_error = "Transaction reverted on-chain"
                        row.blockchain_pending_since = None
                    db.commit()
                else:
                    # N-06 (N06-SEC-03): Check for stalled/dropped pending transaction timeout
                    pending_since = row.blockchain_pending_since or row.created_at
                    if pending_since is not None:
                        if pending_since.tzinfo is None:
                            pending_since = pending_since.replace(tzinfo=timezone.utc)
                        if (now - pending_since).total_seconds() >= pending_timeout:
                            row.blockchain_retry_count = (row.blockchain_retry_count or 0) + 1
                            if row.blockchain_retry_count >= max_retries:
                                row.blockchain_status = "permanent_failure"
                                row.blockchain_last_error = f"Pending transaction timed out after {pending_timeout}s (max retries reached)"
                            else:
                                row.blockchain_status = "retry"
                                row.blockchain_tx = None
                                row.blockchain_pending_since = None
                                row.blockchain_last_error = f"Pending transaction {tx_hash} timed out after {pending_timeout}s without receipt"
                            db.commit()
            except Exception as exc:
                row.blockchain_retry_count = (row.blockchain_retry_count or 0) + 1
                row.blockchain_last_error = str(exc)
                db.commit()

        # ── 2. Retry Unwritten Eligible Incidents (Atomic Claim Outbox) ──────
        pending_ids = [r.id for r in pending_rows]
        query = db.query(Incident).filter(
            Incident.blockchain_tx.is_(None),
            (Incident.threat_score >= settings.threat_threshold) | (Incident.is_blocked == True),  # noqa: E712
            (Incident.blockchain_retry_count < max_retries) | (Incident.blockchain_retry_count.is_(None)),
            Incident.blockchain_status != "permanent_failure",
            Incident.blockchain_status != "confirmed",
            (Incident.blockchain_status != "submitting") | (Incident.blockchain_claimed_at < lease_cutoff),
        )
        if pending_ids:
            query = query.filter(Incident.id.notin_(pending_ids))

        eligible_unwritten = query.order_by(Incident.id.asc()).limit(max_batch).all()

        for row in eligible_unwritten:
            # N-06 (N06-SEC-02): Atomic database-level claim reservation
            claim_time = datetime.now(timezone.utc)
            claim_lease_cutoff = claim_time - timedelta(seconds=claim_timeout)
            claimed = (
                db.query(Incident)
                .filter(
                    Incident.id == row.id,
                    Incident.blockchain_tx.is_(None),
                    (Incident.blockchain_status != "submitting") | (Incident.blockchain_claimed_at < claim_lease_cutoff),
                )
                .update(
                    {"blockchain_status": "submitting", "blockchain_claimed_at": claim_time},
                    synchronize_session=False,
                )
            )
            db.commit()
            if claimed == 0:
                # Concurrently claimed by ingestion thread or another worker
                continue

            target = db.get(Incident, row.id)
            if not target or target.blockchain_tx is not None:
                continue

            result = adapter.store_incident(
                source_ip=target.source_ip,
                attack_type=target.attack_type,
                severity=target.severity,
                is_blocked=target.is_blocked,
                incident_id=target.id,
            )

            target.blockchain_claimed_at = None
            if result.get("status") == "confirmed":
                target.blockchain_tx = result.get("tx_hash")
                target.blockchain_incident_id = result.get("incident_id")
                target.blockchain_chain_id = result.get("chain_id")
                target.blockchain_contract_address = result.get("contract_address")
                target.blockchain_block_number = result.get("block_number")
                target.blockchain_status = "confirmed"
                target.blockchain_last_error = None
                target.blockchain_pending_since = None
                retried_success += 1
            elif result.get("status") == "pending" and result.get("tx_hash"):
                target.blockchain_tx = result.get("tx_hash")
                target.blockchain_chain_id = result.get("chain_id")
                target.blockchain_contract_address = result.get("contract_address")
                target.blockchain_status = "pending"
                target.blockchain_pending_since = datetime.now(timezone.utc)
                err = result.get("error")
                target.blockchain_last_error = str(err) if err is not None else None
                retried_success += 1
            else:
                target.blockchain_retry_count = (target.blockchain_retry_count or 0) + 1
                err = result.get("error")
                target.blockchain_last_error = str(err) if err is not None else "Failed to write to blockchain"
                if target.blockchain_retry_count >= max_retries:
                    target.blockchain_status = "permanent_failure"
                else:
                    target.blockchain_status = "retry"
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
