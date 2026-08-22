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
from app.models.incident import BlockedIP
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
    """Run a single reconciliation pass. Returns a summary dict."""
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


class ReconciliationWorker:
    """Background thread that runs OVS ↔ SQLite reconciliation periodically."""

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
                self.last_result = reconcile_once()
            except Exception as exc:
                self.last_result = {"status": "error", "error": str(exc)}
                print(f"[Reconcile] Error: {exc}")
            time.sleep(self.interval)
