#!/usr/bin/env python3
"""
GraphSentinel Enforcement Daemon
Runs as root. Listens on a local UNIX socket for JSON requests from the unprivileged FastAPI process.
Safely executes OVS commands.
"""
import socket
import os
import json
import subprocess
import logging
from ipaddress import ip_address

SOCKET_PATH = "/tmp/graphsentinel-enforcer.sock"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [DAEMON] %(message)s")


def validate_ip(value: str) -> str:
    # Basic structural validation to prevent command injection
    return str(ip_address(value))


def handle_request(payload: dict) -> dict:
    action = payload.get("action")
    ip = payload.get("ip")
    switch = payload.get("switch")

    if not action or not ip or not switch:
        return {"status": "error", "error": "Missing required fields"}

    try:
        clean_ip = validate_ip(ip)
    except ValueError as exc:
        return {"status": "error", "error": f"Invalid IP: {exc}"}

    if action == "block":
        cmd = ["ovs-ofctl", "add-flow", switch, f"priority=1000,ip,nw_src={clean_ip},actions=drop"]
    elif action == "unblock":
        cmd = ["ovs-ofctl", "del-flows", switch, f"ip,nw_src={clean_ip}"]
    else:
        return {"status": "error", "error": "Invalid action"}

    try:
        # Note: We run as root, so no 'sudo' needed here. But if testing locally without root, 
        # using 'sudo' inside the daemon is fine too. However, best practice is run this script as root.
        # We'll use sudo anyway in case it's run as normal user by accident (though that defeats the purpose).
        # Actually, let's just run the command. The env requires this script to be run with root privileges.
        subprocess.run(
            ["sudo"] + cmd,  # Keeping sudo in case the dev runs daemon without root, but array args are safe
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
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET_PATH)
        # Allow any local process to connect and send requests.
        # In a strict environment, change permissions to a specific group.
        os.chmod(SOCKET_PATH, 0o666)
        server.listen()
        logging.info("Enforcement daemon listening on %s", SOCKET_PATH)

        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    data = conn.recv(4096)
                    if not data:
                        continue
                    payload = json.loads(data.decode("utf-8"))
                    response = handle_request(payload)
                    conn.sendall(json.dumps(response).encode("utf-8"))
                except json.JSONDecodeError:
                    conn.sendall(json.dumps({"status": "error", "error": "Invalid JSON"}).encode("utf-8"))
                except Exception as exc:
                    logging.error("Connection error: %s", exc)


if __name__ == "__main__":
    try:
        run_daemon()
    except KeyboardInterrupt:
        logging.info("Daemon stopped.")
    finally:
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
