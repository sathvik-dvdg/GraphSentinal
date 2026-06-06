# [WSL2]
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base_topology import GraphSentinelTopology  # noqa: E402
from mininet.log import info, setLogLevel  # noqa: E402


def main(duration: int = 15):
    setLogLevel("info")
    topology = GraphSentinelTopology()
    topology.start()
    attacker = topology.hosts["10.0.0.2"]
    target_ip = "10.0.0.1"
    info(f"*** DDoS demo: h2 flooding {target_ip} for {duration}s\n")
    attacker.cmd(f"timeout {duration}s ping -f {target_ip} >/tmp/graphsentinel-ddos.log 2>&1 &")
    time.sleep(duration + 1)
    topology.stop()


if __name__ == "__main__":
    main()

