# [WSL2]
from __future__ import annotations

import re
import subprocess
from typing import Any

from app.config import settings


def parse_ovs_flows(switch: str = "s1") -> list[dict[str, Any]]:
    import sys
    try:
        cmd = ["sudo", "ovs-ofctl", "dump-flows", switch]
        if sys.platform == "win32":
            cmd = ["wsl"] + cmd
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        flows = _parse_output(result.stdout)
        if flows:
            return flows
    except Exception as exc:
        print(f"[FlowParser] OVS unavailable: {exc}")
    return demo_flows() if settings.demo_fallback_flows else []


def _parse_output(raw: str) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        src = _match(line, r"nw_src=([0-9.]+)") or _match(line, r"arp_spa=([0-9.]+)")
        dst = _match(line, r"nw_dst=([0-9.]+)") or _match(line, r"arp_tpa=([0-9.]+)")
        if not src:
            continue
        dst = dst or "0.0.0.0"
        packets = int(_match(line, r"n_packets=(\d+)", "0"))
        bytes_count = int(_match(line, r"n_bytes=(\d+)", "0"))
        src_port = int(_match(line, r"tp_src=(\d+)", "0"))
        dst_port = int(_match(line, r"tp_dst=(\d+)", "0"))
        duration = float(_match(line, r"duration=([0-9.]+)s", "5.0"))
        protocol = "TCP" if "tcp" in line.lower() else "UDP" if "udp" in line.lower() else "IP"
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
                "tcp_flags": 2 if protocol == "TCP" else 0,
            }
        )
    return flows


def _match(line: str, pattern: str, default: str | None = None) -> str | None:
    match = re.search(pattern, line)
    return match.group(1) if match else default


def demo_flows() -> list[dict[str, Any]]:
    return [
        {
            "src_ip": "10.0.0.2",
            "dst_ip": "10.0.0.1",
            "src_port": 54321,
            "dst_port": 80,
            "protocol": "TCP",
            "packet_count": 15000,
            "byte_count": 5120000,
            "duration_sec": 3.5,
            "tcp_flags": 2,
        },
        {
            "src_ip": "10.0.0.3",
            "dst_ip": "10.0.0.1",
            "src_port": 53000,
            "dst_port": 443,
            "protocol": "TCP",
            "packet_count": 120,
            "byte_count": 64000,
            "duration_sec": 4.0,
            "tcp_flags": 0,
        },
    ]

