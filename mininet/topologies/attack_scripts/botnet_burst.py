# [WSL2]
"""Botnet burst demo — multiple attackers sending low-volume bursts to a C2 server.

Simulates the Botnet attack pattern from CICIDS2017:
  - Hosts h4, h6, h8 act as botnet clients.
  - Host h3 acts as the C2 (command-and-control) server.
  - Each bot sends repeated low-volume bursts on typical C2 ports (IRC 6667, HTTP 8080).
  - The pattern triggers byte_asymmetry + C2 port detection in GraphSentinel's threat analyzer.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base_topology import GraphSentinelTopology  # noqa: E402
from mininet.log import info, setLogLevel  # noqa: E402


BOTS = ["10.0.0.4", "10.0.0.6", "10.0.0.8"]
C2_SERVER = "10.0.0.3"
C2_PORTS = [6667, 8080]
BURST_INTERVAL = 2  # seconds between bursts


def main(duration: int = 20):
    setLogLevel("info")
    topology = GraphSentinelTopology()
    topology.start()

    info(f"*** Botnet burst demo: {len(BOTS)} bots → C2 at {C2_SERVER} for {duration}s\n")

    for bot_ip in BOTS:
        bot = topology.hosts[bot_ip]
        for port in C2_PORTS:
            bot.cmd(
                "bash -lc 'end=$((SECONDS+%d)); "
                "while [ $SECONDS -lt $end ]; do "
                "timeout 1 bash -c \"</dev/tcp/%s/%d\" >/dev/null 2>&1; "
                "sleep %d; "
                "done' >/tmp/graphsentinel-botnet-%s-%d.log 2>&1 &"
                % (duration, C2_SERVER, port, BURST_INTERVAL, bot_ip.replace(".", "_"), port)
            )
        info(f"    Bot {bot_ip} started\n")

    info(f"*** Waiting {duration + 2}s for attack to complete...\n")
    time.sleep(duration + 2)
    topology.stop()


if __name__ == "__main__":
    main()
