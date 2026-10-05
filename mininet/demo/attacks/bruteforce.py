#!/usr/bin/env python3
"""Repeated TCP connections from h4 (10.0.0.4) to h1 (10.0.0.1) port 22.

    sudo python3 mininet/demo/attacks/bruteforce.py [--attempts N] [--closed] [--pid PID]

The SHAPE of a brute-force attempt -- many short connections to the SSH port --
not a login attack: nothing speaks SSH here.

Port 22 is OPENED on h1 for the run, because that is what the backend can see.
Measured 2026-10-05 with v1's own code: against an open port the source scores
0.33, 0.66, 0.80 on three successive polls and the heuristic labels it SSHBrute
(port 22 and more than 250 packets). Against a closed port (--closed) every
attempt is refused, the flow entries carry almost no packets, v1 scores 0.007,
and nothing appears on the dashboard; the label would have been "Botnet", the
heuristic's fall-through.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hosts import TARGET_IP, host_pid, in_host, open_target_ports  # noqa: E402

SOURCE_HOST, SOURCE_IP = "h4", "10.0.0.4"
DEFAULT_ATTEMPTS = 300

LABEL_NOTE = (
    "bruteforce: NOTE -- v1 is a binary model. The attack type on the dashboard is a port/volume "
    "heuristic: 'SSHBrute' needs port 22 and more than 250 packets, and anything it does not "
    "match is called 'Botnet'. Whatever label appears, say that first."
)

_LOOP = """
import socket, sys
for _ in range(int(sys.argv[1])):
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect((sys.argv[2], 22)); s.sendall(b'SSH-2.0-demo' + bytes([13, 10])); s.recv(2048)
    except OSError:
        pass
    s.close()
"""


def run_attack(attempts: int = DEFAULT_ATTEMPTS, pid: int | None = None, open_port: bool = True) -> int:
    pid = host_pid(SOURCE_HOST, pid)
    if pid is None:
        print(f"bruteforce: {SOURCE_HOST} not found -- is base_topology_headless.py running?")
        return 1
    print(LABEL_NOTE)
    if open_port and not open_target_ports([22], seconds=60):
        print("bruteforce: target h1 not found -- is base_topology_headless.py running?")
        return 1
    print(f"bruteforce: {SOURCE_HOST} ({SOURCE_IP}) -> {TARGET_IP}:22, {attempts} TCP connection attempts "
          f"({'port open' if open_port else 'port CLOSED: expect nothing on the dashboard'})")
    done = in_host(pid, ["python3", "-c", _LOOP, str(attempts), TARGET_IP], timeout=300)
    ok = done.returncode == 0
    print(f"bruteforce: {'done' if ok else 'FAILED'}" + ("" if ok else f" -- {done.stderr.strip()[:200]}"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS, help="connection attempts")
    ap.add_argument("--closed", action="store_true", help="do not open port 22 on the target first")
    ap.add_argument("--pid", type=int, default=None, help="PID of the h4 Mininet process (default: found with pgrep)")
    args = ap.parse_args()
    return run_attack(args.attempts, args.pid, open_port=not args.closed)


if __name__ == "__main__":
    sys.exit(main())
