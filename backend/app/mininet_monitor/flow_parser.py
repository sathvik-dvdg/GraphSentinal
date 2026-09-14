# [WSL2]
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

# ── Poll status ───────────────────────────────────────────────────────────────
# The parser REPORTS what the switch said. It never invents traffic: substituting
# demo flows is policy, and lives in MininetMonitor._poll. Before this split the
# parser swallowed every failure and returned normally, so an hour-long daemon
# outage was indistinguishable from an hour of quiet traffic.
POLL_OK = "ok"              # daemon answered and at least one flow parsed
POLL_OK_EMPTY = "ok_empty"  # daemon answered, but nothing parseable (quiet network,
                            # or a dump holding only a table-miss rule)
POLL_FAILED = "failed"      # no usable answer: unreachable, timeout, error status,
                            # empty response, invalid JSON


@dataclass
class PollResult:
    status: str
    flows: list[dict[str, Any]] = field(default_factory=list)
    #: Why the poll failed. None unless status == "failed".
    error: str | None = None
    #: Non-empty lines in the dump the daemon returned. Makes a dump holding only
    #: a table-miss rule visible as such. None when the poll failed.
    lines_in_dump: int | None = None
    #: Set by the MONITOR when it replaced a failed poll's (empty) flows with
    #: demo_flows(). The parser itself never sets it.
    demo_substituted: bool = False


def result_from_output(raw: str) -> PollResult:
    """Classify a successful daemon answer: `ok` or `ok_empty`."""
    flows = _parse_output(raw)
    lines = sum(1 for line in raw.splitlines() if line.strip())
    return PollResult(status=POLL_OK if flows else POLL_OK_EMPTY, flows=flows, lines_in_dump=lines)


def poll_ovs_flows(switch: str = "s1") -> PollResult:
    """One poll of the switch via the enforcement daemon. Never raises."""
    import json
    import socket

    try:
        payload = {
            "token": settings.daemon_token,
            "action": "dump_flows",
            "switch": switch,
        }
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

            response = b"".join(response_data).decode("utf-8")
            if not response:
                raise RuntimeError("Empty response from daemon")

            result = json.loads(response)
            if result.get("status") != "success":
                raise RuntimeError(result.get("error", "Unknown error from daemon"))

            return result_from_output(result.get("output", ""))
    except Exception as exc:  # noqa: BLE001 - a poll must report, never raise
        message = f"{type(exc).__name__}: {exc}"
        print(f"[FlowParser] OVS poll failed via daemon: {message}")
        return PollResult(status=POLL_FAILED, error=message)


def parse_ovs_flows(switch: str = "s1") -> list[dict[str, Any]]:
    """The flows from one poll. NO demo substitution -- that is monitor policy
    now (MininetMonitor._poll). Use poll_ovs_flows() to learn whether the poll
    actually succeeded."""
    return poll_ovs_flows(switch).flows


def _parse_output(raw: str) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        # Error.md #31 — verified against real `ovs-ofctl dump-flows -O
        # OpenFlow13` output from this project's own WSL2 Mininet session.
        # ARP entries use arp_spa=/arp_tpa= (source/target protocol address),
        # not nw_src=/nw_dst=, so they were silently dropped entirely before
        # this branch existed. ICMP was already handled correctly by the
        # nw_src=/nw_dst= path below — it just has icmp_type=/icmp_code=
        # instead of tp_src=/tp_dst=, which correctly default ports to 0
        # (ICMP has no ports; that's not a bug). IPv6 (ipv6_src=/ipv6_dst=)
        # is still unhandled — this topology is IPv4-only and never produces
        # IPv6 traffic to verify a fix against, so it's left alone rather
        # than guessed at.
        if "arp_spa=" in line and "arp_tpa=" in line:
            src = _match(line, r"arp_spa=([0-9.]+)")
            dst = _match(line, r"arp_tpa=([0-9.]+)")
            protocol = "ARP"
        elif "nw_src=" in line and "nw_dst=" in line:
            src = _match(line, r"nw_src=([0-9.]+)")
            dst = _match(line, r"nw_dst=([0-9.]+)")
            line_lower = line.lower()
            if "icmp" in line_lower:
                protocol = "ICMP"
            elif "tcp" in line_lower:
                protocol = "TCP"
            elif "udp" in line_lower:
                protocol = "UDP"
            else:
                protocol = "IP"
        else:
            continue
        if not src or not dst:
            continue
        packets = int(_match(line, r"n_packets=(\d+)", "0"))
        bytes_count = int(_match(line, r"n_bytes=(\d+)", "0"))
        src_port = int(_match(line, r"tp_src=(\d+)", "0"))
        dst_port = int(_match(line, r"tp_dst=(\d+)", "0"))
        duration = float(_match(line, r"duration=([0-9.]+)s", "5.0"))
        # `dump-flows` doesn't normally expose per-packet TCP flags — only
        # trust a real tcp_flags= field if OVS actually printed one; never
        # fabricate SYN (Error.md #32).
        flags_hex = _match(line, r"tcp_flags=0x([0-9a-fA-F]+)")
        flags_dec = _match(line, r"tcp_flags=(\d+)")
        if flags_hex is not None:
            tcp_flags = int(flags_hex, 16)
        elif flags_dec is not None:
            tcp_flags = int(flags_dec)
        else:
            tcp_flags = 0
        flows.append(
            {
                "src_ip": src,
                "dst_ip": dst,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": protocol,
                "packet_count": packets,
                "byte_count": bytes_count,
                "duration_sec": max(duration, 0.001),
                "tcp_flags": tcp_flags,
                # Error.md #34 — this is real OVS-dumped traffic, not demo
                # fallback or a manual/simulated submission.
                "data_source": "ovs",
            }
        )
    return flows


def _match(line: str, pattern: str, default: str | None = None) -> str | None:
    match = re.search(pattern, line)
    return match.group(1) if match else default


def demo_flows() -> list[dict[str, Any]]:
    """Generate randomized demo flows across all 10 Mininet hosts with varied
    attack profiles so the dashboard shows realistic multi-source traffic
    instead of the same IP every 5 seconds."""
    import random

    # All 10 hosts from base_topology.py
    all_hosts = [f"10.0.0.{i}" for i in range(1, 11)]

    # Pick a random attacker and a different random victim
    attacker = random.choice(all_hosts)
    victim = random.choice([h for h in all_hosts if h != attacker])

    # Attack profile templates — each poll picks one at random
    attack_profiles = [
        # DDoS flood — high packet count, HTTP/HTTPS ports
        {
            "dst_port": random.choice([80, 443, 8080]),
            "protocol": "TCP",
            "packet_count": random.randint(8000, 25000),
            "byte_count": random.randint(3000000, 8000000),
            "duration_sec": round(random.uniform(1.5, 5.0), 1),
            "tcp_flags": 2,
        },
        # Port Scan — low packets across many ports
        {
            "dst_port": random.randint(20, 1024),
            "protocol": "TCP",
            "packet_count": random.randint(2, 10),
            "byte_count": random.randint(120, 600),
            "duration_sec": round(random.uniform(0.01, 0.1), 3),
            "tcp_flags": 2,
        },
        # SSH Brute Force — repeated attempts on port 22
        {
            "dst_port": 22,
            "protocol": "TCP",
            "packet_count": random.randint(30, 80),
            "byte_count": random.randint(4800, 12800),
            "duration_sec": round(random.uniform(0.8, 2.5), 1),
            "tcp_flags": 2,
        },
        # Botnet C2 — IRC/custom port, moderate traffic
        {
            "dst_port": random.choice([6667, 6668, 8443, 4444]),
            "protocol": "TCP",
            "packet_count": random.randint(200, 1000),
            "byte_count": random.randint(25600, 128000),
            "duration_sec": round(random.uniform(5.0, 15.0), 1),
            "tcp_flags": 0,
        },
        # DNS Amplification — UDP port 53, large responses
        {
            "dst_port": 53,
            "protocol": "UDP",
            "packet_count": random.randint(5000, 20000),
            "byte_count": random.randint(2000000, 10000000),
            "duration_sec": round(random.uniform(2.0, 6.0), 1),
            "tcp_flags": 0,
        },
    ]

    profile = random.choice(attack_profiles)

    # Sometimes generate a second flow from a different attacker for variety
    flows = [
        {
            "src_ip": attacker,
            "dst_ip": victim,
            "src_port": random.randint(40000, 60000),
            **profile,
            "data_source": "demo",
        },
    ]

    # 50% chance of a second simultaneous attack from another host
    if random.random() > 0.5:
        attacker2 = random.choice([h for h in all_hosts if h not in (attacker, victim)])
        victim2 = random.choice([h for h in all_hosts if h != attacker2])
        profile2 = random.choice(attack_profiles)
        flows.append(
            {
                "src_ip": attacker2,
                "dst_ip": victim2,
                "src_port": random.randint(40000, 60000),
                **profile2,
                "data_source": "demo",
            }
        )

    return flows

