#!/usr/bin/env python3
"""The presentation sequence: flood, port scan, brute-force shape. One command.

Each attack opens the service it needs on the target (h1) for its own duration:
v1 only scores completed TCP conversations over its threshold, so an attack on a
closed port never appears (attacks/_hosts.py has the measurement).

    python mininet/demo/run_demo.py [--backend-url URL] [--api-key KEY]

Run it where the backend is reachable. On Windows the attacks are sent into WSL
as root (see attacks/_hosts.py); on Linux/WSL run it with sudo.

It needs the long-lived topology (mininet/topologies/base_topology_headless.py),
the enforcement daemon and the backend already running: DEMO_SETUP.md.

Unblocking between attacks is an admin action. Give the backend's admin API key
with --api-key or GS_ADMIN_API_TOKEN. Without one the unblock step is skipped
with a message and the sequence carries on: each attack uses a different host.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "attacks"))
import bruteforce  # noqa: E402
import flood  # noqa: E402
import portscan  # noqa: E402

DEFAULT_BACKEND = os.environ.get("GS_BACKEND_URL", "http://localhost:8000")


def call(method: str, url: str, api_key: str | None = None, body: dict | None = None, timeout: float = 5.0):
    """(status, json-or-None, reason). Never raises."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if api_key:
        request.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                return response.status, json.loads(raw.decode("utf-8")), ""
            except ValueError:
                return response.status, None, "answer was not JSON"
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", "")
        except Exception:  # noqa: BLE001
            detail = ""
        return exc.code, None, f"HTTP {exc.code} {detail}".strip()
    except (urllib.error.URLError, OSError) as exc:
        return None, None, f"no answer: {getattr(exc, 'reason', exc)}"


def preflight(backend: str, allow_blind: bool = False) -> bool:
    status, health, reason = call("GET", f"{backend}/health")
    if status != 200 or not isinstance(health, dict):
        print(f"PREFLIGHT FAILED: {backend}/health -- {reason or f'HTTP {status}'}")
        print("  The backend must be running. If it is on port 8001 (RUN_GUIDE.md section 5), pass "
              "--backend-url http://localhost:8001")
        return False
    monitor = health.get("monitor") or {}
    v1 = health.get("v1") or {}
    v2 = health.get("ml_v2") or {}
    # /health has no "connection_mode": that is the frontend's own state. What
    # the backend can say is whether its last poll of the switch succeeded.
    print(f"backend: {health.get('status')} | switch poll: {monitor.get('last_poll_status')} "
          f"({monitor.get('last_flow_count')} flows)"
          + (f" -- {monitor.get('last_error')}" if monitor.get("last_error") else ""))
    print(f"v1: mode {(health.get('ml') or {}).get('mode')}, threshold {v1.get('threat_threshold')}, "
          f"enforcement {v1.get('enforcement_mode')} | v2: {'on, dry-run' if v2.get('enabled') else 'off'}")
    if v1.get("enforcement_mode") != "simulated":
        print("  WARNING: ENFORCEMENT_MODE is not 'simulated'. Blocks will install real drop rules.")
    if monitor.get("last_poll_status") not in ("ok", "ok_empty"):
        # An attack the backend cannot see is a demo of nothing. Stop here.
        print("PREFLIGHT FAILED: the backend is not reading the switch, so no attack would be seen. "
              "Check the topology and the enforcement daemon (its DAEMON_TOKEN must be the backend's).")
        return allow_blind
    return True


def report_blocked(backend: str, api_key: str | None, ip: str) -> None:
    """What the backend recorded for this source, if we are allowed to ask."""
    if not api_key:
        return
    status, body, reason = call("GET", f"{backend}/api/v1/blocked", api_key)
    if status != 200 or not isinstance(body, dict):
        print(f"  (could not read the blocked list: {reason or f'HTTP {status}'})")
        return
    row = next((r for r in body.get("blocked_ips", []) if r.get("ip") == ip), None)
    if row:
        print(f"  backend: {ip} is recorded as blocked -- label {row.get('attack_type')!r}, "
              f"score {row.get('threat_score')}")
    else:
        print(f"  backend: {ip} is NOT recorded as blocked. v1 did not score it over the threshold.")


def unblock(backend: str, api_key: str | None, ip: str) -> None:
    if not api_key:
        print(f"  skipped: no admin API key (--api-key or GS_ADMIN_API_TOKEN). Unblock {ip} from the "
              "dashboard if you want it clear; the next attacks use other hosts.")
        return
    status, body, reason = call("POST", f"{backend}/api/v1/block", api_key,
                                {"ip": ip, "action": "unblock", "reason": "MANUAL_OVERRIDE"}, timeout=15)
    if status == 200:
        print(f"  {ip} unblocked ({(body or {}).get('status')})")
        print("  note: its flows stay in the switch's table for up to 60 s, and while they do v1 "
              "scores it again on the next poll and blocks it again. The next attacks use other hosts.")
    else:
        print(f"  unblock failed: {reason or f'HTTP {status}'} -- continuing; the next attacks use other hosts.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the three demo attacks in sequence.")
    ap.add_argument("--backend-url", default=DEFAULT_BACKEND)
    ap.add_argument("--api-key", default=os.environ.get("GS_ADMIN_API_TOKEN"),
                    help="the backend's admin API key, for the unblock step (or GS_ADMIN_API_TOKEN)")
    ap.add_argument("--wait", type=float, default=20.0,
                    help="seconds to wait after each attack. v1's score for a source rises over the first "
                         "polls after an attack (measured: over the threshold on the second or third)")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds to pause before the next step")
    ap.add_argument("--ignore-poll", action="store_true",
                    help="run even if the backend's last poll of the switch failed")
    args = ap.parse_args()
    backend = args.backend_url.rstrip("/")

    if not preflight(backend, allow_blind=args.ignore_poll):
        return 1

    print("\n--- FLOOD ATTACK (h2 -> h1) ---")
    if flood.run_attack() != 0:
        return 1
    time.sleep(args.wait)
    print("Check the dashboard -- node h2 / 10.0.0.2 should be red.")
    report_blocked(backend, args.api_key, flood.SOURCE_IP)
    time.sleep(args.pause)

    print("\n--- Unblocking 10.0.0.2 ---")
    unblock(backend, args.api_key, flood.SOURCE_IP)

    print("\n--- PORT SCAN (h3 -> h1) ---")
    if portscan.run_attack() != 0:
        return 1
    time.sleep(args.wait)
    print("Check the dashboard -- node h3 / 10.0.0.3 should be red.")
    report_blocked(backend, args.api_key, portscan.SOURCE_IP)
    time.sleep(args.pause)

    print("\n--- SSH BRUTE FORCE (h4 -> h1) ---")
    if bruteforce.run_attack() != 0:      # prints the note about the label first
        return 1
    time.sleep(args.wait)
    print("Check the dashboard -- node h4 / 10.0.0.4 should be red. Whatever attack type it shows "
          "is the heuristic's, not a model output: the model is binary.")
    report_blocked(backend, args.api_key, bruteforce.SOURCE_IP)
    time.sleep(args.pause)

    print("\n--- Demo complete ---")
    print("Do not run benign traffic. Keep ENFORCEMENT_MODE=simulated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
