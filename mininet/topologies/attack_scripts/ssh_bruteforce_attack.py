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
    info(f"*** SSH brute-force demo: h2 hitting {target_ip}:22 for {duration}s\n")
    attacker.cmd(
        "bash -lc 'end=$((SECONDS+%d)); "
        "while [ $SECONDS -lt $end ]; do "
        "timeout 1 bash -c \"</dev/tcp/%s/22\" >/dev/null 2>&1; "
        "done' >/tmp/graphsentinel-ssh.log 2>&1 &" % (duration, target_ip)
    )
    time.sleep(duration + 1)
    topology.stop()


if __name__ == "__main__":
    main()

