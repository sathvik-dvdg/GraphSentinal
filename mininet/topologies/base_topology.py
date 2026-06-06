# [WSL2]
from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch


class GraphSentinelTopology:
    def __init__(self):
        self.net = Mininet(controller=Controller, switch=OVSSwitch, autoSetMacs=True)
        self.hosts = {}
        self._build()

    def _build(self):
        self.net.addController("c0")
        switch = self.net.addSwitch("s1")
        for index in range(1, 11):
            ip = f"10.0.0.{index}"
            host = self.net.addHost(f"h{index}", ip=f"{ip}/24")
            self.net.addLink(host, switch)
            self.hosts[ip] = host

    def start(self):
        self.net.start()
        info("*** GraphSentinel network READY: 10 hosts on 10.0.0.0/24\n")
        info("*** Keep this CLI open while the backend monitor is running.\n")

    def stop(self):
        self.net.stop()


def main():
    setLogLevel("info")
    topology = GraphSentinelTopology()
    topology.start()
    try:
        CLI(topology.net)
    finally:
        topology.stop()


if __name__ == "__main__":
    main()

