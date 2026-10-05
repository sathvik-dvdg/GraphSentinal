"""Reach a host of the ALREADY RUNNING Mininet topology.

Nothing here imports Mininet or builds a network: the long-lived topology
(mininet/topologies/base_topology_headless.py) owns the switch, and an attack
only enters one of its host namespaces with `mnexec -a <pid>`.

Run on Linux/WSL as root, commands are executed directly. Run on Windows (where
the backend of this project normally is), the same commands are sent into WSL as
root, so the controller can sit beside the backend:

    GS_WSL_DISTRO   the WSL distribution holding Mininet   (default: Ubuntu)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

# base_topology_headless.py: h<i> has address 10.0.0.<i>, for i in 1..10.
TARGET_HOST, TARGET_IP = "h1", "10.0.0.1"


def _prefix() -> list[str]:
    if sys.platform == "win32":
        return ["wsl.exe", "-d", os.environ.get("GS_WSL_DISTRO", "Ubuntu"), "-u", "root", "--"]
    return []


def run(argv: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    """Run a command where Mininet lives. Never raises for a missing binary or a
    timeout: the caller gets a non-zero return code and the reason in stderr."""
    try:
        done = subprocess.run(_prefix() + argv, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(argv, 127, "", f"not found: {exc.filename}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout:.0f}s")
    # wsl.exe can answer in UTF-16; strip the NULs rather than guess an encoding
    out = done.stdout.decode("utf-8", "replace").replace("\x00", "")
    err = done.stderr.decode("utf-8", "replace").replace("\x00", "")
    return subprocess.CompletedProcess(argv, done.returncode, out, err)


def host_pid(host: str, pid: int | None = None) -> int | None:
    """PID of the Mininet process for `host` (e.g. "h2"), or None if the topology
    is not running. The pattern is anchored: "mininet:h1" alone also matches h10."""
    if pid:
        return int(pid)
    found = run(["pgrep", "-f", f"mininet:{host}$"], timeout=10)
    for line in found.stdout.split():
        if line.strip().isdigit():
            return int(line)
    return None


def in_host(pid: int, argv: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    """Run argv inside the network namespace of the host with this PID."""
    return run(["mnexec", "-a", str(pid)] + argv, timeout=timeout)


def available(binary: str) -> bool:
    return run(["which", binary], timeout=10).returncode == 0


# ── The target's services ────────────────────────────────────────────────────
# Nothing listens on any port in the stock topology. Measured on 2026-10-05 with
# the backend's own v1 code: a connection REFUSED by a closed port leaves a
# flow-table entry with almost no packets, and v1 scores such a source at 0.02 or
# less -- far under its 0.75 threshold -- so the attack never appears. v1 responds
# to COMPLETED TCP conversations. So an attack that needs a service on the target
# opens it for its own duration: a web server to flood, ports for a scan to find,
# an SSH port to hammer. That is the realistic case as well as the visible one.
#
# The code avoids quote and backslash characters so that it survives being
# passed as one argument through wsl.exe.
_LISTENER = """
import socket, sys, threading, time
ports = [int(p) for p in sys.argv[1].split(',')]
end = time.time() + float(sys.argv[2])
CRLF = bytes([13, 10])
def serve(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(512); s.settimeout(0.5)
    while time.time() < end:
        try:
            c, _ = s.accept(); c.settimeout(0.2)
            try:
                c.recv(2048); c.sendall(b'HTTP/1.0 200 OK' + CRLF + CRLF + b'x' * 512)
            except OSError:
                pass
            c.close()
        except OSError:
            pass
for p in ports:
    threading.Thread(target=serve, args=(p,), daemon=True).start()
time.sleep(max(0.0, end - time.time()))
"""


def open_target_ports(ports: list[int], seconds: float = 45.0) -> bool:
    """Listen on these TCP ports on the target (h1) for `seconds`, then stop by
    itself. Returns False if the target host is not found."""
    pid = host_pid(TARGET_HOST)
    if pid is None:
        return False
    subprocess.Popen(
        _prefix() + ["mnexec", "-a", str(pid), "python3", "-c", _LISTENER,
                     ",".join(str(p) for p in ports), str(seconds)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
    )
    time.sleep(1.5)     # let it bind before the first connection arrives
    return True
