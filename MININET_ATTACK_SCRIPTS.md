# ⚔️ GRAPHSENTINEL — MININET ATTACK SIMULATION SCRIPTS
## Owner: Sairaj (Backend) | OS: WSL2 Ubuntu 22.04 ONLY
## All scripts run with: sudo python3 <script_name>.py

---

## HOW MININET ATTACK SIMULATION WORKS

```
TOPOLOGY (base_topology.py):
  10 hosts: h1(10.0.0.1) through h10(10.0.0.10)
  1 switch: s1 (OVS — Open vSwitch)
  All hosts connect through s1 (star topology)

ATTACK SIMULATION STRATEGY:
  We don't use real exploit code.
  We generate HIGH-VOLUME TRAFFIC that MIMICS attack signatures.
  The GNN detects the BEHAVIORAL PATTERN (packet rate, port entropy, etc.)
  NOT the actual exploit payload.

  This is academically correct: real IDS/ML systems detect
  behavioral patterns, not payload signatures.

HOW TO TRIGGER ATTACKS DURING DEMO:
  Method 1: Run individual attack scripts below (recommended)
  Method 2: Use Mininet CLI: sudo mn → h2 ping -f h1 (basic flood)
  Method 3: Use the demo controller script (runs all attacks in sequence)
```

---

## MININET BASE TOPOLOGY

```python
# mininet/topologies/base_topology.py  [WSL2 — requires sudo]
# Run: sudo python3 base_topology.py
# This starts Mininet with 10 hosts. Leave this running for attacks.

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import sys

def build_graphsentinel_network():
    """
    Star topology: 10 hosts connected through OVS switch s1.
    IP range: 10.0.0.1/24 through 10.0.0.10/24
    """
    setLogLevel('info')

    net = Mininet(
        switch=OVSSwitch,
        controller=Controller,
        autoSetMacs=True,
        autoStaticArp=True
    )

    info("*** Creating GraphSentinel topology\n")

    # Controller
    c0 = net.addController('c0')

    # Switch
    s1 = net.addSwitch('s1', protocols='OpenFlow13')

    # 10 hosts
    hosts = {}
    host_roles = {
        1: "Router", 2: "Attacker-A", 3: "WebServer",
        4: "Database", 5: "Attacker-B", 6: "AppServer",
        7: "AdminHost", 8: "ClientNode", 9: "StorageNode", 10: "MonitorHost"
    }

    for i in range(1, 11):
        h = net.addHost(
            f'h{i}',
            ip=f'10.0.0.{i}/24',
            mac=f'00:00:00:00:00:0{i:02x}'
        )
        net.addLink(h, s1, bw=100)   # 100 Mbps links
        hosts[i] = h
        info(f"  h{i} → 10.0.0.{i} [{host_roles[i]}]\n")

    info("*** Starting network\n")
    net.start()

    # Verify connectivity
    info("*** Testing connectivity\n")
    net.pingAll(timeout=1)

    info("\n*** GraphSentinel network READY\n")
    info("*** Hosts: h1(10.0.0.1) through h10(10.0.0.10)\n")
    info("*** Backend should be polling OVS flows via: sudo ovs-ofctl dump-flows s1\n")
    info("*** Type 'exit' or Ctrl-D to stop the network\n\n")

    # Open CLI so network stays alive
    CLI(net)
    net.stop()

if __name__ == '__main__':
    build_graphsentinel_network()
```

---

## ATTACK SCRIPT 1 — DDoS (High Volume Flood)

```python
# mininet/topologies/attack_scripts/ddos_attack.py  [WSL2]
# SIMULATE: Distributed Denial of Service
# BEHAVIOR: h2 sends massive flood of packets to multiple targets
# GNN SIGNALS: out_degree↑↑, connection_rate↑↑↑, byte_asymmetry↑
# Run: sudo python3 ddos_attack.py

"""
DDoS Attack Simulation for GraphSentinel Demo

What this does:
  - h2 (10.0.0.2) floods h1, h3, h6, h9 simultaneously
  - Sends 50,000+ packets in 10 seconds
  - Mimics volumetric DDoS flood traffic
  - GNN sees: extreme connection_rate + high out_degree → malicious
"""

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
import subprocess
import threading
import time

ATTACKER_IP  = "10.0.0.2"
TARGET_IPS   = ["10.0.0.1", "10.0.0.3", "10.0.0.6", "10.0.0.9"]
DURATION_SEC = 15   # Run for 15 seconds (backend polls every 5s → 3 reads)
FLOOD_RATE   = 9999  # packets per second per target

def run_flood(attacker_host, target_ip, duration):
    """Use hping3 to generate high-rate SYN flood."""
    print(f"[DDoS] {ATTACKER_IP} → {target_ip} | {FLOOD_RATE} pps")
    # hping3: SYN flood, as fast as possible
    attacker_host.cmd(
        f"timeout {duration} hping3 -S --flood -p 80 {target_ip} &"
    )

def simulate_ddos():
    # Attach to running Mininet (must be started via base_topology.py)
    # Alternative: start fresh network just for this attack
    from mininet.net import Mininet
    from mininet.cli import CLI

    net = Mininet(switch=OVSSwitch, controller=Controller)
    c0  = net.addController('c0')
    s1  = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()

    # Install hping3 on attacker
    hosts[2].cmd("apt-get install -y hping3 -q 2>/dev/null || true")

    print("\n" + "="*50)
    print("  GRAPHSENTINEL — DDoS ATTACK INITIATED")
    print(f"  Attacker: {ATTACKER_IP}")
    print(f"  Targets:  {TARGET_IPS}")
    print(f"  Duration: {DURATION_SEC}s")
    print("="*50 + "\n")

    # Launch flood threads against all targets simultaneously
    threads = []
    for target in TARGET_IPS:
        t = threading.Thread(
            target=run_flood,
            args=(hosts[2], target, DURATION_SEC)
        )
        t.start()
        threads.append(t)
        time.sleep(0.2)

    print(f"[DDoS] Attack running for {DURATION_SEC}s — watch the dashboard!")
    print(f"[DDoS] Backend polls OVS every 5s — expect detection in 5-10s")

    time.sleep(DURATION_SEC + 2)
    for t in threads: t.join(timeout=2)

    print("\n[DDoS] Attack complete. Node 10.0.0.2 should be RED/BLOCKED in dashboard.")
    net.stop()

if __name__ == '__main__':
    simulate_ddos()
```

**Simpler DDoS using Mininet built-in (no hping3 needed):**
```python
# mininet/topologies/attack_scripts/ddos_simple.py  [WSL2]
# REQUIRES: Mininet running (base_topology.py in another terminal)
# Run this FROM the Mininet CLI: py exec(open('/path/ddos_simple.py').read())

import subprocess, threading, time

def ddos_simple(net, attacker_num=2, targets=[1,3,6,9], duration=15):
    """
    Generates high-rate ICMP flood using built-in ping.
    Less realistic but works without hping3.
    """
    attacker = net.get(f'h{attacker_num}')
    print(f"\n[DDoS-SIMPLE] h{attacker_num} flooding {len(targets)} targets for {duration}s")

    for t in targets:
        host = net.get(f'h{t}')
        # -f = flood mode, -c = count
        attacker.cmd(f"ping -f -c 50000 {host.IP()} &")
        time.sleep(0.1)

    time.sleep(duration)
    attacker.cmd("killall ping 2>/dev/null")
    print(f"[DDoS-SIMPLE] Complete.")

# Run from Mininet CLI: py ddos_simple(net)
```

---

## ATTACK SCRIPT 2 — Port Scan

```python
# mininet/topologies/attack_scripts/portscan_attack.py  [WSL2]
# SIMULATE: Systematic Port Scanning
# BEHAVIOR: h4 probes 1000 ports on h3, h6, h7
# GNN SIGNALS: port_entropy↑↑↑ (contacts many unique ports)
# Run: sudo python3 portscan_attack.py

"""
Port Scan Attack Simulation

What this does:
  - h4 (10.0.0.4) systematically contacts ports 1–1024 on multiple hosts
  - Shannon entropy of destination ports → very high (uniform distribution)
  - GNN sees: port_entropy spike → PortScan detected
"""

import subprocess
import threading
import time

SCANNER_IP   = "10.0.0.4"
TARGET_IPS   = ["10.0.0.3", "10.0.0.6", "10.0.0.7"]
PORT_RANGE   = (1, 1024)
DELAY_MS     = 2   # milliseconds between probes (fast scan)

def scan_ports(attacker_host, target_ip, port_start, port_end):
    """Simulate SYN scan using ncat/nc probe on each port."""
    print(f"[PortScan] {SCANNER_IP} scanning {target_ip}:{port_start}-{port_end}")

    # Use nmap if available, otherwise nc loop
    result = attacker_host.cmd("which nmap")
    if "nmap" in result:
        # Nmap SYN scan (fastest, most realistic)
        attacker_host.cmd(
            f"nmap -sS -p {port_start}-{port_end} --min-rate=1000 "
            f"--open {target_ip} -T4 &"
        )
    else:
        # Fallback: nc loop (slower but always available)
        for port in range(port_start, min(port_start + 200, port_end)):
            attacker_host.cmd(
                f"timeout 0.05 nc -zv {target_ip} {port} 2>/dev/null &"
            )
            if port % 50 == 0:
                time.sleep(0.1)

def simulate_portscan():
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch

    net = Mininet(switch=OVSSwitch, controller=Controller)
    c0  = net.addController('c0')
    s1  = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()

    print("\n" + "="*50)
    print("  GRAPHSENTINEL — PORT SCAN ATTACK INITIATED")
    print(f"  Scanner:  {SCANNER_IP}")
    print(f"  Targets:  {TARGET_IPS}")
    print(f"  Ports:    {PORT_RANGE[0]}-{PORT_RANGE[1]}")
    print("="*50 + "\n")

    threads = []
    for target in TARGET_IPS:
        t = threading.Thread(
            target=scan_ports,
            args=(hosts[4], target, PORT_RANGE[0], PORT_RANGE[1])
        )
        t.start()
        threads.append(t)
        time.sleep(1)

    print("[PortScan] Scan running — port_entropy will spike in dashboard")
    time.sleep(20)

    print("\n[PortScan] Complete. Node 10.0.0.4 should be AMBER/SUSPICIOUS.")
    net.stop()

if __name__ == '__main__':
    simulate_portscan()
```

---

## ATTACK SCRIPT 3 — SSH Brute Force

```python
# mininet/topologies/attack_scripts/ssh_brute.py  [WSL2]
# SIMULATE: SSH Brute Force (SSH-Patator pattern)
# BEHAVIOR: h5 makes thousands of TCP connections to port 22 on h7
# GNN SIGNALS: connection_rate↑↑, syn_ratio↑↑, single dst_port (low entropy)
# Run: sudo python3 ssh_brute.py

"""
SSH Brute Force Attack Simulation

What this does:
  - h5 (10.0.0.5) makes rapid repeated TCP connections to port 22
  - Mimics password-spraying / credential brute force
  - GNN sees: very high connection_rate + SYN-heavy traffic + port 22 fixation
"""

import threading
import time

ATTACKER_IP = "10.0.0.5"
TARGET_IP   = "10.0.0.7"  # Admin host
TARGET_PORT = 22           # SSH
NUM_ATTEMPTS = 3000
BATCH_SIZE   = 100
DURATION_SEC = 20

def ssh_brute_batch(attacker_host, target_ip, port, batch_count):
    """Make rapid repeated TCP SYN to port 22."""
    for i in range(batch_count):
        # Rapid fire TCP connect attempts — simulate auth attempt pattern
        attacker_host.cmd(
            f"timeout 0.1 bash -c 'echo x > /dev/tcp/{target_ip}/{port}' "
            f"2>/dev/null; "
        )

def simulate_ssh_brute():
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch

    net = Mininet(switch=OVSSwitch, controller=Controller)
    c0  = net.addController('c0')
    s1  = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()

    print("\n" + "="*50)
    print("  GRAPHSENTINEL — SSH BRUTE FORCE INITIATED")
    print(f"  Attacker: {ATTACKER_IP}")
    print(f"  Target:   {TARGET_IP}:{TARGET_PORT}")
    print(f"  Attempts: {NUM_ATTEMPTS}")
    print("="*50 + "\n")

    # Use hping3 for most realistic SSH brute pattern
    attacker = hosts[5]
    attacker.cmd("apt-get install -y hping3 -q 2>/dev/null || true")

    # SYN flood specifically on port 22
    print(f"[SSHBrute] Flooding port 22 on {TARGET_IP} for {DURATION_SEC}s")
    attacker.cmd(
        f"timeout {DURATION_SEC} hping3 -S -p 22 --fast {TARGET_IP} &"
    )

    print("[SSHBrute] Attack running — watch syn_ratio spike in dashboard")
    time.sleep(DURATION_SEC + 2)

    print(f"\n[SSHBrute] Complete. Node {ATTACKER_IP} should be RED/BLOCKED.")
    net.stop()

if __name__ == '__main__':
    simulate_ssh_brute()
```

---

## ATTACK SCRIPT 4 — Botnet C2 Communication

```python
# mininet/topologies/attack_scripts/botnet_sim.py  [WSL2]
# SIMULATE: Botnet Command-and-Control Communication
# BEHAVIOR: h8 establishes slow, periodic connections to many hosts
# GNN SIGNALS: byte_asymmetry (small sends, no recv), consistent timing,
#              connection to unusual port range (8080, 4444, 1337)
# Run: sudo python3 botnet_sim.py

"""
Botnet C2 Simulation

What this does:
  - h8 (10.0.0.8) sends periodic "beacon" traffic to h1 on unusual ports
  - Mimics botnet C2 check-in pattern (regular intervals, small payload)
  - GNN sees: low entropy ports + regular connection_rate + byte_asymmetry
"""

import threading
import time
import random

BOT_IP     = "10.0.0.8"
C2_IP      = "10.0.0.1"   # "C2 server"
C2_PORTS   = [4444, 8080, 1337, 6667]   # Common C2 ports
BEACON_INTERVAL = 0.5   # seconds between beacons
NUM_BEACONS     = 60    # total beacons to send
DURATION_SEC    = 35    # total simulation time

def send_beacon(bot_host, c2_ip, port):
    """Simulate C2 beacon: small TCP connect + minimal data."""
    # Netcat to send small payload then close
    payload = "BEACON\n"
    bot_host.cmd(
        f"echo '{payload}' | timeout 0.2 nc {c2_ip} {port} 2>/dev/null"
    )

def simulate_botnet():
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch

    net = Mininet(switch=OVSSwitch, controller=Controller)
    c0  = net.addController('c0')
    s1  = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()

    print("\n" + "="*50)
    print("  GRAPHSENTINEL — BOTNET C2 BEACON STARTED")
    print(f"  Bot node: {BOT_IP}")
    print(f"  C2 addr:  {C2_IP}")
    print(f"  Ports:    {C2_PORTS}")
    print(f"  Interval: {BEACON_INTERVAL}s per beacon")
    print("="*50 + "\n")

    bot = hosts[8]
    print(f"[Botnet] Sending {NUM_BEACONS} beacons to {C2_IP}")

    for i in range(NUM_BEACONS):
        port = C2_PORTS[i % len(C2_PORTS)]
        send_beacon(bot, C2_IP, port)
        if i % 10 == 0:
            print(f"[Botnet] Beacon #{i+1}/{NUM_BEACONS} → {C2_IP}:{port}")
        time.sleep(BEACON_INTERVAL)

    print(f"\n[Botnet] Complete. Node {BOT_IP} should be AMBER/SUSPICIOUS.")
    net.stop()

if __name__ == '__main__':
    simulate_botnet()
```

---

## ATTACK SCRIPT 5 — DoS Hulk (HTTP Flood)

```python
# mininet/topologies/attack_scripts/dos_hulk.py  [WSL2]
# SIMULATE: DoS Hulk HTTP flooding pattern
# BEHAVIOR: h2 sends massive HTTP GET requests to h3 (web server)
# GNN SIGNALS: connection_rate↑↑↑, out_degree spikes on port 80/443
# Run: sudo python3 dos_hulk.py

"""
DoS Hulk Simulation

What this does:
  - h2 floods h3 (web server) with rapid HTTP requests
  - Generates unique request patterns to avoid caching
  - GNN sees: extreme packet rate + port 80 concentration + byte asymmetry
"""

import threading
import time
import random
import string

ATTACKER_IP  = "10.0.0.2"
VICTIM_IP    = "10.0.0.3"
TARGET_PORT  = 80
DURATION_SEC = 20
NUM_THREADS  = 10

def generate_random_path():
    """Generate random URL path like DoS Hulk to bypass caches."""
    return ''.join(random.choices(string.ascii_lowercase, k=8))

def hulk_flood(attacker_host, target_ip, port, duration):
    """Simulate DoS Hulk: rapid randomized HTTP GET flood."""
    # Use curl in loop for HTTP requests
    end_time = time.time() + duration
    count = 0
    while time.time() < end_time:
        path = generate_random_path()
        attacker_host.cmd(
            f"timeout 0.1 curl -s -o /dev/null "
            f"http://{target_ip}:{port}/{path}?q={path} 2>/dev/null"
        )
        count += 1
    print(f"[DoSHulk] Thread complete: {count} requests sent")

def simulate_dos_hulk():
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch

    net = Mininet(switch=OVSSwitch, controller=Controller)
    c0  = net.addController('c0')
    s1  = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()

    print("\n" + "="*50)
    print("  GRAPHSENTINEL — DoS HULK INITIATED")
    print(f"  Attacker: {ATTACKER_IP}")
    print(f"  Victim:   {VICTIM_IP}:{TARGET_PORT}")
    print(f"  Threads:  {NUM_THREADS}")
    print(f"  Duration: {DURATION_SEC}s")
    print("="*50 + "\n")

    # Start a simple HTTP server on h3 for realistic traffic
    hosts[3].cmd("python3 -m http.server 80 &")
    time.sleep(1)

    # Launch flood threads
    threads = []
    for _ in range(NUM_THREADS):
        t = threading.Thread(
            target=hulk_flood,
            args=(hosts[2], VICTIM_IP, TARGET_PORT, DURATION_SEC)
        )
        t.start()
        threads.append(t)
        time.sleep(0.1)

    print(f"[DoSHulk] {NUM_THREADS} flood threads running for {DURATION_SEC}s")
    for t in threads: t.join()

    print(f"\n[DoSHulk] Complete. Node {ATTACKER_IP} should be MALICIOUS/BLOCKED.")
    net.stop()

if __name__ == '__main__':
    simulate_dos_hulk()
```

---

## DEMO CONTROLLER — Run All Attacks in Sequence

```python
# mininet/topologies/attack_scripts/demo_controller.py  [WSL2]
# USAGE: Run this during the 60-minute demo for a scripted attack sequence
# Run: sudo python3 demo_controller.py
# This runs all 5 attacks with pauses between them for dashboard observation

"""
GraphSentinel Demo Attack Controller

Sequence:
  T+00s  → DDoS Attack (h2 → h1,h3,h6,h9)          Duration: 15s
  T+25s  → Port Scan (h4 → h3,h6,h7)                Duration: 15s
  T+50s  → SSH Brute Force (h5 → h7)                Duration: 15s
  T+75s  → Botnet C2 Beacons (h8 → h1)              Duration: 30s
  T+115s → DoS Hulk (h2 → h3)                       Duration: 15s

Between attacks: 10s pause (let dashboard update + explain to panel)
"""

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.log import setLogLevel
import threading
import time

def build_net():
    setLogLevel('warning')
    net = Mininet(switch=OVSSwitch, controller=Controller, autoStaticArp=True)
    net.addController('c0')
    s1 = net.addSwitch('s1')
    hosts = {}
    for i in range(1, 11):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
        net.addLink(h, s1)
        hosts[i] = h
    net.start()
    return net, hosts

def wait_with_countdown(seconds, label):
    print(f"\n[DEMO] ⏳ {label} — starting in {seconds}s...")
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end='\r', flush=True)
        time.sleep(1)
    print()

def attack_ddos(hosts, duration=12):
    print("\n[DEMO] 🔴 ATTACK 1: DDoS — h2 flooding 4 targets")
    h2 = hosts[2]
    h2.cmd("apt-get install -y hping3 -q 2>/dev/null || true")
    for target in ["10.0.0.1", "10.0.0.3", "10.0.0.6"]:
        h2.cmd(f"timeout {duration} hping3 -S --flood -p 80 {target} &")
    time.sleep(duration + 1)
    h2.cmd("killall hping3 2>/dev/null")
    print("[DEMO] DDoS complete — check dashboard for RED node h2")

def attack_portscan(hosts, duration=12):
    print("\n[DEMO] 🟡 ATTACK 2: PortScan — h4 scanning h3,h6,h7")
    h4 = hosts[4]
    h4.cmd("apt-get install -y nmap -q 2>/dev/null || true")
    for target in ["10.0.0.3", "10.0.0.6", "10.0.0.7"]:
        h4.cmd(f"nmap -sS -p 1-1024 --min-rate=2000 {target} &")
    time.sleep(duration + 1)
    print("[DEMO] PortScan complete — check h4 → AMBER (suspicious)")

def attack_sshbrute(hosts, duration=12):
    print("\n[DEMO] 🔴 ATTACK 3: SSH Brute Force — h5 → h7:22")
    h5 = hosts[5]
    h5.cmd("apt-get install -y hping3 -q 2>/dev/null || true")
    h5.cmd(f"timeout {duration} hping3 -S -p 22 --fast 10.0.0.7 &")
    time.sleep(duration + 1)
    h5.cmd("killall hping3 2>/dev/null")
    print("[DEMO] SSH Brute complete — h5 → BLOCKED (blue cage)")

def attack_botnet(hosts, duration=20):
    print("\n[DEMO] 🟡 ATTACK 4: Botnet C2 — h8 beaconing to h1")
    h8 = hosts[8]
    for i in range(40):
        port = [4444, 8080, 1337][i % 3]
        h8.cmd(f"echo 'BEACON' | timeout 0.2 nc 10.0.0.1 {port} 2>/dev/null &")
        time.sleep(0.5)
    print("[DEMO] Botnet complete — h8 → AMBER/MALICIOUS")

def attack_doshulk(hosts, duration=12):
    print("\n[DEMO] 🔴 ATTACK 5: DoS Hulk — h2 HTTP flooding h3")
    h3, h2 = hosts[3], hosts[2]
    h3.cmd("python3 -m http.server 80 &")
    time.sleep(1)
    for _ in range(8):
        h2.cmd(f"timeout {duration} ab -n 5000 -c 100 http://10.0.0.3/ &")
    time.sleep(duration + 1)
    print("[DEMO] DoS Hulk complete")

def main():
    print("\n" + "█"*60)
    print("█  GRAPHSENTINEL DEMO ATTACK CONTROLLER              █")
    print("█  Ensure backend (FastAPI) is running on port 8000  █")
    print("█  Ensure frontend (React) is running on port 5173   █")
    print("█"*60)

    wait_with_countdown(5, "Initializing network topology")

    net, hosts = build_net()
    print("[DEMO] ✅ Network ready — 10 hosts on 10.0.0.0/24\n")

    try:
        # ATTACK 1: DDoS
        attack_ddos(hosts)
        wait_with_countdown(10, "PAUSE — explain detection to panel")

        # ATTACK 2: Port Scan
        attack_portscan(hosts)
        wait_with_countdown(10, "PAUSE — show port_entropy spike in dashboard")

        # ATTACK 3: SSH Brute
        attack_sshbrute(hosts)
        wait_with_countdown(10, "PAUSE — show blockchain TX hash in panel")

        # ATTACK 4: Botnet
        attack_botnet(hosts)
        wait_with_countdown(10, "PAUSE — explain C2 communication pattern")

        # ATTACK 5: DoS Hulk
        attack_doshulk(hosts)

        print("\n" + "█"*60)
        print("█  ALL ATTACKS COMPLETE                              █")
        print("█  Dashboard should show 3+ blocked nodes            █")
        print("█  Blockchain panel should show 5+ TX hashes         █")
        print("█  Self-healing events: isolation times displayed     █")
        print("█"*60)

        print("\n[DEMO] Network running — press Ctrl+C to stop\n")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[DEMO] Stopping network...")
        net.stop()

if __name__ == '__main__':
    main()
```

---

## IMPORTANT: MININET COMMANDS FOR DEMO

```bash
# [WSL2] — Run these in Mininet CLI during demo if needed

# Check current flows on switch:
sudo ovs-ofctl dump-flows s1

# Manual traffic generation inside Mininet CLI:
# sudo mn (starts fresh mininet)
# mininet> h2 ping -f h1  (flood ping)
# mininet> h4 nmap 10.0.0.3  (port scan)
# mininet> h5 hping3 -S -p 22 --fast 10.0.0.7 &  (SSH brute)

# Kill all background processes on all hosts:
# mininet> h2 killall hping3 ping nmap 2>/dev/null

# Check network topology:
# mininet> net        (show links)
# mininet> dump       (show all nodes)
# mininet> pingall    (verify connectivity)

# OVS flow statistics (what backend's flow_parser.py reads):
sudo ovs-ofctl dump-ports s1

# Force clear all flows (reset network state):
sudo ovs-ofctl del-flows s1
```

---

## ATTACK DETECTION EXPECTED TIMELINE

```
TIME    EVENT                           DASHBOARD CHANGE
────────────────────────────────────────────────────────────────
T+0s    Attack script starts            (nothing yet)
T+5s    Backend polls OVS               Flows appear
T+5s    graph_builder builds graph      Graph updates
T+5s    GNN inference runs              Threat scores assigned
T+6s    Threat > 0.75 detected          Node turns AMBER
T+10s   Second poll — confirmed         Node turns RED
T+10s   Self-healing fires              Node turns BLUE + cage
T+10s   SQLite incident created         Alert appears in panel
T+11s   blockchain_adapter fires        TX hash starts appearing
T+12s   Ganache mines TX                ✓ confirmed on ledger
T+12s   WebSocket pushes update         Frontend receives all changes

TOTAL: Attack visible in dashboard within 5–12 seconds ✅
```
