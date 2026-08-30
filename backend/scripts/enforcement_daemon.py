#!/usr/bin/env python3
"""
GraphSentinel Enforcement Daemon
Runs as root. Listens on a local TCP socket for JSON requests from the unprivileged FastAPI process.
Safely executes OVS commands.
"""
import socket
import os
import sys
import json
import subprocess
import logging
from ipaddress import ip_address, ip_network

HOST = os.environ.get("DAEMON_HOST", "127.0.0.1")
PORT = int(os.environ.get("DAEMON_PORT", 50051))
CLIENT_TIMEOUT = 2.0

SHARED_SECRET = os.environ.get("DAEMON_TOKEN")
if not SHARED_SECRET:
    sys.exit("ERROR: DAEMON_TOKEN environment variable must be set.")

MININET_CIDR = os.environ.get("MININET_CIDR", "10.0.0.0/24")
try:
    MININET_NETWORK = ip_network(MININET_CIDR, strict=False)
except ValueError as exc:
    sys.exit(f"ERROR: Invalid MININET_CIDR '{MININET_CIDR}': {exc}")

ALLOWED_SWITCHES = {"s1", "s2", "s3"}

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [DAEMON] %(message)s")


def validate_ip(value: str) -> str:
    """Validate and sanitize an IP for enforcement.

    Independently enforces:
    - IPv4 parsing (rejects non-IP strings and IPv6)
    - Mininet CIDR restriction (must belong to MININET_NETWORK)
    - Rejection of multicast, loopback, and unspecified addresses
    - Rejection of network and broadcast addresses
    """
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        raise ValueError(f"Invalid IP address: {value}") from exc

    if parsed.version != 4:
        raise ValueError(f"IPv6 address {value} is not supported")

    if parsed.is_multicast or parsed.is_loopback or parsed.is_unspecified:
        raise ValueError(f"IP {value} is not enforceable")

    if parsed not in MININET_NETWORK:
        raise ValueError(f"IP {value} is outside {MININET_NETWORK}")

    if parsed in {MININET_NETWORK.network_address, MININET_NETWORK.broadcast_address}:
        raise ValueError(f"IP {value} is not a host address")

    return str(parsed)


def handle_request(payload: dict) -> dict:
    token = payload.get("token")
    if token != SHARED_SECRET:
        return {"status": "error", "error": "Unauthorized"}

    action = payload.get("action")
    switch = payload.get("switch")

    if not action or not switch:
        return {"status": "error", "error": "Missing required fields (action, switch)"}

    if switch not in ALLOWED_SWITCHES:
        return {"status": "error", "error": "Invalid switch"}

    if action == "dump_flows":
        try:
            cmd = ["sudo", "ovs-ofctl", "dump-flows", switch]
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            return {"status": "success", "action": action, "output": result.stdout}
        except subprocess.CalledProcessError as exc:
            logging.error("OVS command failed: %s", exc.stderr)
            return {"status": "error", "error": f"Command failed: {exc.stderr.strip()}"}
        except Exception as exc:
            logging.error("Exception: %s", exc)
            return {"status": "error", "error": str(exc)}

    # For block/unblock, IP is required
    ip = payload.get("ip")
    if not ip:
        return {"status": "error", "error": "Missing required field (ip)"}

    try:
        clean_ip = validate_ip(ip)
    except ValueError as exc:
        return {"status": "error", "error": f"Invalid IP: {exc}"}

    if action == "block":
        cmd = ["sudo", "ovs-ofctl", "add-flow", switch, f"priority=1000,ip,nw_src={clean_ip},actions=drop"]
    elif action == "unblock":
        cmd = ["sudo", "ovs-ofctl", "del-flows", switch, f"ip,nw_src={clean_ip}"]
    else:
        return {"status": "error", "error": "Invalid action"}

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        logging.info("%s successful for %s on %s", action.upper(), clean_ip, switch)
        return {"status": "success", "action": action, "ip": clean_ip}
    except subprocess.CalledProcessError as exc:
        logging.error("OVS command failed: %s", exc.stderr)
        return {"status": "error", "error": f"Command failed: {exc.stderr.strip()}"}
    except Exception as exc:
        logging.error("Exception: %s", exc)
        return {"status": "error", "error": str(exc)}


def run_daemon():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        logging.info("Enforcement daemon listening on TCP %s:%s", HOST, PORT)

        while True:
            conn, addr = server.accept()
            with conn:
                try:
                    conn.settimeout(CLIENT_TIMEOUT)
                    data = conn.recv(4096)
                    if not data:
                        continue
                    payload = json.loads(data.decode("utf-8"))
                    response = handle_request(payload)
                    
                    conn.sendall(json.dumps(response).encode("utf-8"))
                except (socket.timeout, TimeoutError):
                    logging.warning("Connection from %s timed out waiting for data", addr)
                except json.JSONDecodeError:
                    conn.sendall(json.dumps({"status": "error", "error": "Invalid JSON"}).encode("utf-8"))
                except Exception as exc:
                    logging.error("Connection error from %s: %s", addr, exc)


if __name__ == "__main__":
    try:
        run_daemon()
    except KeyboardInterrupt:
        logging.info("Daemon stopped.")
