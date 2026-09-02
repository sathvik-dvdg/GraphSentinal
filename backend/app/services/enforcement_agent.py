# [WSL2]
from __future__ import annotations

import json
import logging
import socket
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network

from app.config import settings


_audit_log = logging.getLogger('graphsentinel.enforcement')
_audit_log.setLevel(logging.INFO)
if not _audit_log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] [ENFORCEMENT] %(message)s'))
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
        _audit_log.warning('REJECTED invalid IP input: %r - %s', value, exc)
        raise ValueError(f'Invalid IP address: {value}') from exc

    if parsed.is_multicast or parsed.is_loopback or parsed.is_unspecified or parsed.is_link_local:
        _audit_log.warning('REJECTED IP %s - non-enforceable class', parsed)
        raise ValueError(f'IP {value} is not enforceable or loopback/link-local')

    protected_infra = {getattr(settings, "backend_host", "127.0.0.1"), getattr(settings, "daemon_host", "127.0.0.1"), "127.0.0.1", "0.0.0.0"}
    if str(parsed) in protected_infra:
        _audit_log.warning('REJECTED attempt to block protected infrastructure IP: %s', parsed)
        raise ValueError(f'Cannot block critical infrastructure IP: {value}')

    network = ip_network(settings.mininet_cidr, strict=False)
    if parsed not in network:
        _audit_log.warning('REJECTED IP %s - outside %s', parsed, network)
        raise ValueError(f'IP {value} is outside {network}')
    if parsed in {network.network_address, network.broadcast_address}:
        _audit_log.warning('REJECTED IP %s - network/broadcast address', parsed)
        raise ValueError(f'IP {value} is not a host address')
    return str(parsed)


class EnforcementAgent:
    def __init__(self, switch: str | None = None, mode: str | None = None):
        self.switch = switch or settings.enforcement_switch
        self.mode = mode or settings.enforcement_mode
        self.last_error: str | None = None
        # Decision #5 (decisions.md) — Option C: a log-visible warning rather
        # than rejecting `simulated` outright. `simulated` stays a legitimate
        # mode (Docker/dev workflows depend on it); this just makes it
        # impossible to miss in the container log that no real OVS rules are
        # being applied. A stronger `require_real_enforcement` guard is
        # deferred until a real-network production deployment is an actual
        # goal (there isn't one defined yet).
        if self.mode != 'ovs':
            _audit_log.warning('Enforcement mode is SIMULATED — no OVS flow rules will be applied.')

    def _send_to_daemon(self, payload: dict) -> dict:
        payload["token"] = getattr(settings, "daemon_token", None)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3.0)
                sock.connect((settings.daemon_host, settings.daemon_port))
                sock.sendall(json.dumps(payload).encode('utf-8'))
                
                response_data = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_data.append(chunk)
                
                response = b"".join(response_data)
                if not response:
                    raise RuntimeError('Empty response from daemon')
                return json.loads(response.decode('utf-8'))
        except Exception as exc:
            raise EnforcementError(f'Daemon communication failed: {exc}') from exc

    def block_ip(self, ip: str) -> str:
        clean_ip = validate_mininet_ip(ip)
        if self.mode != 'ovs':
            _audit_log.info('BLOCK %s - mode=simulated (no OVS action)', clean_ip)
            return 'simulated'
        try:
            payload = {'action': 'block', 'ip': clean_ip, 'switch': self.switch}
            result = self._send_to_daemon(payload)
            if result.get('status') != 'success':
                raise EnforcementError(result.get('error', 'Unknown error from daemon'))
            self.last_error = None
            _audit_log.info('BLOCK %s - OVS rule applied on %s via daemon [OK]', clean_ip, self.switch)
            return 'enforced'
        except Exception as exc:
            self.last_error = str(exc)
            _audit_log.error('BLOCK %s - FAILED: %s', clean_ip, exc)
            raise EnforcementError(str(exc)) from exc

    def unblock_ip(self, ip: str) -> str:
        clean_ip = validate_mininet_ip(ip)
        if self.mode != 'ovs':
            _audit_log.info('UNBLOCK %s - mode=simulated (no OVS action)', clean_ip)
            return 'simulated'
        try:
            payload = {'action': 'unblock', 'ip': clean_ip, 'switch': self.switch}
            result = self._send_to_daemon(payload)
            if result.get('status') != 'success':
                raise EnforcementError(result.get('error', 'Unknown error from daemon'))
            self.last_error = None
            _audit_log.info('UNBLOCK %s - OVS rule removed from %s via daemon [OK]', clean_ip, self.switch)
            return 'removed'
        except Exception as exc:
            self.last_error = str(exc)
            _audit_log.error('UNBLOCK %s - FAILED: %s', clean_ip, exc)
            raise EnforcementError(str(exc)) from exc


def build_enforcement_event(ip: str, action: str, status: str) -> dict:
    return {
        'ip': ip,
        'action': action,
        'status': status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
