# [WSL2] Headless variant of base_topology.py for unattended/background runs.
# Same 10-host star topology, but skips the interactive CLI() so the process
# can run detached (nohup/background) without stdin ever going through it.
# Run: sudo python3 base_topology_headless.py
from mininet.net import Mininet
from mininet.node import OVSController, OVSSwitch
from mininet.log import setLogLevel, info
import signal
import sys
import time


def build_graphsentinel_network():
    setLogLevel('info')

    net = Mininet(
        switch=OVSSwitch,
        controller=OVSController,
        autoSetMacs=True,
        autoStaticArp=True
    )

    info("*** Creating GraphSentinel topology\n")

    # OVSController wraps ovs-testcontroller as a real L2-learning-switch
    # controller: it installs an explicit per-conversation OpenFlow rule
    # (nw_src=/nw_dst=/tp_src=/tp_dst=) for each new flow it sees, which is
    # what flow_parser.py's dump-flows regex expects. A plain no-controller
    # failMode='standalone' switch instead collapses everything into one
    # wildcard 'actions=NORMAL' rule with aggregate counters -- no per-IP
    # breakdown, so the backend can't tell hosts apart.
    net.addController('c0', controller=OVSController)
    s1 = net.addSwitch('s1', failMode='secure')

    host_roles = {
        1: "Router", 2: "Attacker-A", 3: "WebServer",
        4: "Database", 5: "Attacker-B", 6: "AppServer",
        7: "AdminHost", 8: "ClientNode", 9: "StorageNode", 10: "MonitorHost"
    }

    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1, bw=100)
        hosts[i] = h
        info(f"  h{i} -> 10.0.0.{i} [{host_roles[i]}]\n")

    info("*** Starting network\n")
    net.start()

    # A full pingAll() (10x9 simultaneous pings at a 1s timeout) is too
    # aggressive right after namespace startup under WSL2 and reports
    # false failures even though forwarding works fine (verified separately
    # with a 2-host case: 0% loss, real flow counters in dump-flows). Do one
    # light connectivity check between the pair the attack scripts use instead.
    info("*** Testing h2 -> h1 connectivity\n")
    result = hosts[2].cmd('ping -c2 -W3 10.0.0.1')
    info(result + "\n")

    info("\n*** GraphSentinel network READY (headless)\n")
    info("*** Backend should be polling OVS flows via the enforcement daemon\n")

    def _shutdown(signum, frame):
        info("\n*** Signal received, stopping network\n")
        net.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        net.stop()


if __name__ == '__main__':
    build_graphsentinel_network()
