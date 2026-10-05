#!/usr/bin/env python3
"""TCP port scan from h3 (10.0.0.3) to h1 (10.0.0.1), inside the running topology.

    sudo python3 mininet/demo/attacks/portscan.py [--ports 20-30] [--closed] [--pid PID]

Eleven destination ports by default; the backend's heuristic says "PortScan" at
five or more distinct destination ports from one source.

The scanned ports are OPENED on h1 for the scan, because that is what the backend
can see. Measured 2026-10-05 with v1's own code: scanning open ports, the source
scores 0.28, 0.83, 0.93 on three successive polls; scanning closed ports
(--closed), 0.004, and nothing appears on the dashboard.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hosts import TARGET_IP, available, host_pid, in_host, open_target_ports  # noqa: E402

SOURCE_HOST, SOURCE_IP = "h3", "10.0.0.3"
DEFAULT_PORTS = "20-30"

# Used when nmap is not installed: the same TCP connects, from Python.
_FALLBACK = """
import socket, sys
for p in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    s = socket.socket(); s.settimeout(0.2); s.connect_ex((sys.argv[3], p)); s.close()
"""


def run_attack(ports: str = DEFAULT_PORTS, pid: int | None = None, open_ports: bool = True) -> int:
    pid = host_pid(SOURCE_HOST, pid)
    if pid is None:
        print(f"portscan: {SOURCE_HOST} not found -- is base_topology_headless.py running?")
        return 1
    lo, _, hi = ports.partition("-")
    lo, hi = int(lo), int(hi or lo)
    if open_ports and not open_target_ports(list(range(lo, hi + 1)), seconds=45):
        print("portscan: target h1 not found -- is base_topology_headless.py running?")
        return 1
    with_nmap = available("nmap")
    print(f"portscan: {SOURCE_HOST} ({SOURCE_IP}) -> {TARGET_IP}, TCP connect to ports {lo}-{hi} "
          f"({hi - lo + 1} ports, {'open' if open_ports else 'CLOSED: expect nothing on the dashboard'}, "
          f"{'nmap' if with_nmap else 'python sockets'})")
    if with_nmap:
        # -Pn -n: no ping, no DNS; nothing but the scan should leave the host
        done = in_host(pid, ["nmap", "-sT", "-Pn", "-n", "-p", f"{lo}-{hi}",
                             "--max-rtt-timeout", "200ms", TARGET_IP], timeout=120)
    else:
        done = in_host(pid, ["python3", "-c", _FALLBACK, str(lo), str(hi), TARGET_IP], timeout=120)
    ok = done.returncode == 0
    print(f"portscan: {'done' if ok else 'FAILED'}" + ("" if ok else f" -- {done.stderr.strip()[:200]}"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ports", default=DEFAULT_PORTS, help="port range LOW-HIGH")
    ap.add_argument("--closed", action="store_true", help="do not open the ports on the target first")
    ap.add_argument("--pid", type=int, default=None, help="PID of the h3 Mininet process (default: found with pgrep)")
    args = ap.parse_args()
    return run_attack(args.ports, args.pid, open_ports=not args.closed)


if __name__ == "__main__":
    sys.exit(main())
