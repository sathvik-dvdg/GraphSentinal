#!/usr/bin/env python3
"""Flood from h2 (10.0.0.2) to h1 (10.0.0.1), inside the running topology.

    sudo python3 mininet/demo/attacks/flood.py                 # TCP/HTTP flood (the demo default)
    sudo python3 mininet/demo/attacks/flood.py --mode icmp     # ping flood

Two modes, and the default is the one the backend can see:

  tcp   --count HTTP requests to a web server opened on h1:80 for the purpose,
        each a new connection. Measured 2026-10-05: v1 scores the source 0.77,
        0.86, 0.90 on three successive polls, and the heuristic labels it DDoS.
  icmp  `ping -f`, one conversation with a large packet counter. Measured the
        same day: v1 scores it 0.02. NOTHING appears on the dashboard. Kept
        because it is the flood most people expect, and to show that.

One host flooding another: a flood, not a distributed one.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hosts import TARGET_IP, host_pid, in_host, open_target_ports  # noqa: E402

SOURCE_HOST, SOURCE_IP = "h2", "10.0.0.2"
DEFAULT_COUNT, DEFAULT_SIZE = 2000, 64

_HTTP_LOOP = """
import socket, sys
CRLF = bytes([13, 10])
for _ in range(int(sys.argv[1])):
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect((sys.argv[2], 80)); s.sendall(b'GET / HTTP/1.0' + CRLF + CRLF); s.recv(2048)
    except OSError:
        pass
    s.close()
"""


def run_attack(count: int = DEFAULT_COUNT, size: int = DEFAULT_SIZE, pid: int | None = None,
               mode: str = "tcp") -> int:
    pid = host_pid(SOURCE_HOST, pid)
    if pid is None:
        print(f"flood: {SOURCE_HOST} not found -- is base_topology_headless.py running?")
        return 1
    if mode == "icmp":
        print(f"flood: {SOURCE_HOST} ({SOURCE_IP}) -> {TARGET_IP}, {count} ICMP packets of {size} bytes "
              "(v1 does not score a ping flood over its threshold: expect nothing on the dashboard)")
        done = in_host(pid, ["ping", "-f", "-c", str(count), "-s", str(size), TARGET_IP], timeout=120)
        # ping exits 1 when replies were lost, which a flood can cause; the
        # packets were still sent. Only a failure to run at all is a failure.
        ok = done.returncode in (0, 1)
        summary = next((l.strip() for l in done.stdout.splitlines() if "packets transmitted" in l), "")
    else:
        if not open_target_ports([80], seconds=60):
            print("flood: target h1 not found -- is base_topology_headless.py running?")
            return 1
        print(f"flood: {SOURCE_HOST} ({SOURCE_IP}) -> {TARGET_IP}:80, {count} HTTP requests, a new connection each")
        done = in_host(pid, ["python3", "-c", _HTTP_LOOP, str(count), TARGET_IP], timeout=300)
        ok, summary = done.returncode == 0, ""
    print(f"flood: {'done' if ok else 'FAILED'}" + (f" -- {summary}" if summary else "")
          + ("" if ok else f" -- {done.stderr.strip()[:200]}"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("tcp", "icmp"), default="tcp")
    ap.add_argument("--count", type=int, default=DEFAULT_COUNT, help="HTTP requests (tcp) or packets (icmp)")
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE, help="icmp only: payload bytes per packet")
    ap.add_argument("--pid", type=int, default=None, help="PID of the h2 Mininet process (default: found with pgrep)")
    args = ap.parse_args()
    return run_attack(args.count, args.size, args.pid, args.mode)


if __name__ == "__main__":
    sys.exit(main())
