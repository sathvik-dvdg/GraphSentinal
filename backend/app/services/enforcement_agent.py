# [WSL2]
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network

from app.config import settings


_audit_log = logging.getLogger("graphsentinel.enforcement")
_audit_log.setLevel(logging.INFO)
if not _audit_log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [ENFORCEMENT] %(message)s"))
    _audit_log.addHandler(handler)


class EnforcementError(RuntimeError):
    pass


def validate_mininet_ip(value: str) -> str:
    """Validate and sanitize an IP for enforcement.

    Rejects:
    - Non-IP strings (command injection attempts)
    - IPs outside the Mininet CIDR
    - Network/broadcast addresses
    - Multicast, loopback, and unspecified addresses
    """
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        _audit_log.warning("REJECTED invalid IP input: %r — %s", value, exc)
        raise ValueError(f"Invalid IP address: {value}") from exc

    network = ip_network(settings.mininet_cidr, strict=False)
    if parsed not in network:
        _audit_log.warning("REJECTED IP %s — outside %s", parsed, network)
        raise ValueError(f"IP {value} is outside {network}")
    if parsed in {network.network_address, network.broadcast_address}:
        _audit_log.warning("REJECTED IP %s — network/broadcast address", parsed)
        raise ValueError(f"IP {value} is not a host address")
    if parsed.is_multicast or parsed.is_loopback or parsed.is_unspecified:
        _audit_log.warning("REJECTED IP %s — non-enforceable class", parsed)
        raise ValueError(f"IP {value} is not enforceable")
    return str(parsed)


class EnforcementAgent:
    def __init__(self, switch: str | None = None, mode: str | None = None):
        self.switch = switch or settings.enforcement_switch
        self.mode = mode or settings.enforcement_mode
        self.last_error: str | None = None

    def block_ip(self, ip: str) -> str:
        clean_ip = validate_mininet_ip(ip)
        if self.mode != "ovs":
            _audit_log.info("BLOCK %s — mode=simulated (no OVS action)", clean_ip)
            return "simulated"
        try:
            subprocess.run(
                [
                    "sudo",
                    "ovs-ofctl",
                    "add-flow",
                    self.switch,
                    f"priority=1000,ip,nw_src={clean_ip},actions=drop",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.last_error = None
            _audit_log.info("BLOCK %s — OVS rule applied on %s ✓", clean_ip, self.switch)
            return "enforced"
        except Exception as exc:
            self.last_error = str(exc)
            _audit_log.error("BLOCK %s — FAILED: %s", clean_ip, exc)
            raise EnforcementError(str(exc)) from exc

    def unblock_ip(self, ip: str) -> str:
        clean_ip = validate_mininet_ip(ip)
        if self.mode != "ovs":
            _audit_log.info("UNBLOCK %s — mode=simulated (no OVS action)", clean_ip)
            return "simulated"
        try:
            subprocess.run(
                ["sudo", "ovs-ofctl", "del-flows", self.switch, f"ip,nw_src={clean_ip}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.last_error = None
            _audit_log.info("UNBLOCK %s — OVS rule removed from %s ✓", clean_ip, self.switch)
            return "removed"
        except Exception as exc:
            self.last_error = str(exc)
            _audit_log.error("UNBLOCK %s — FAILED: %s", clean_ip, exc)
            raise EnforcementError(str(exc)) from exc


