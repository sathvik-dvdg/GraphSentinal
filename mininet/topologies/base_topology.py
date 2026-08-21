# [WSL2]
from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSController, OVSSwitch


class GraphSentinelTopology:
    def __init__(self):
        self.net = Mininet(controller=OVSController, switch=OVSSwitch, autoSetMacs=True)
        self.hosts = {}
        self._build()

    def _build(self):
        # OVSController wraps ovs-testcontroller as a real L2-learning-switch
        # controller: it installs an explicit per-conversation OpenFlow rule
        # (nw_src=/nw_dst=/tp_src=/tp_dst=) for each new flow, which is what
        # flow_parser.py's dump-flows regex needs for real per-IP telemetry.
        # Mininet's plain default Controller never pushes flows at all (100%
        # packet loss in 'secure' fail-mode), and a no-controller/standalone
        # switch collapses everything into one wildcard 'actions=NORMAL' rule
        # with an aggregate counter -- no per-host breakdown either way.
        self.net.addController("c0")
        switch = self.net.addSwitch("s1", failMode="secure")
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

