# Demo checklist

For the person who built this, running a ten-minute demo. Mininet and Open
vSwitch run in WSL; the backend, inference service and frontend run where they
normally do.

## Before you start (once per session)

1. Free WSL memory, as root in WSL: `sync; echo 3 > /proc/sys/vm/drop_caches`
2. Start Open vSwitch if it is not running: `sudo service openvswitch-switch start`
   (and `sudo systemctl stop openvswitch-testcontroller`: Mininet starts its own).
   Mininet needs that controller installed: `sudo apt-get install -y openvswitch-testcontroller`.
   Without it the topology stops at "Cannot find required executable ovs-controller"
   and switch `s1` never exists.
   `./run_dev.ps1 -WithMininet` does steps 2 to 5 for you and checks the controller and `s1`.
3. Start the long-lived topology and keep its terminal open:
   `sudo python3 mininet/topologies/base_topology_headless.py`
4. Start the enforcement daemon, as root in WSL, with the backend's token:
   `DAEMON_TOKEN=<the backend's> python3 backend/scripts/enforcement_daemon.py`
5. Start the inference service, then the backend, with `ENFORCEMENT_MODE=simulated`
6. `python ML/verify_stack.py` — all ten checks must pass
7. Start the frontend; sign in as admin; the header badge must say LIVE

## Do NOT do during the demo

- Run benign traffic generators (web fetch loops, hping3 in the background). v1
  flags completed TCP conversations whoever sends them, so background traffic
  fills the dashboard with blocked innocent hosts.
- Run the original scripts in `mininet/topologies/attack_scripts/` while the
  headless topology is up. They try to create the switch `s1` again.
- Set `ENFORCEMENT_MODE=ovs`. That installs real drop rules instead of
  simulated ones.
- Run `pingall` in the Mininet CLI. Replaying its flows (one echo for each of the
  90 host pairs) through v1 scored all ten hosts 0.89 and blocked every one of them
  as "Botnet": many hosts, many peers, one tiny flow each is what v1 reads as a
  threat. A single `h1 ping h7` is fine (h1 0.11, h7 0.03, no incident; a finished
  `ping -c 4` creeps toward 0.6 over a minute as its rule ages, still under 0.75).

## Running the attacks

One command, from the repository root, where the backend is reachable:

```
python mininet/demo/run_demo.py --backend-url http://localhost:8001
```

On Windows it sends the attacks into WSL as root by itself (distribution
`Ubuntu`, or set `GS_WSL_DISTRO`). On Linux or inside WSL run it with `sudo`.
The default backend URL is `http://localhost:8000`, or `GS_BACKEND_URL`; the
manual path in `RUN_GUIDE.md` uses 8001. For the unblock step give the backend's
admin API key with `--api-key` or `GS_ADMIN_API_TOKEN`; without it that step is
skipped and the rest runs.

It refuses to start if the backend is not answering, or if the backend's last
poll of the switch failed: an attack nobody can see is a demo of nothing.

Or by hand, in order:

```
sudo python3 mininet/demo/attacks/flood.py
sudo python3 mininet/demo/attacks/portscan.py
sudo python3 mininet/demo/attacks/bruteforce.py
```

Allow about twenty seconds after each before pointing at the dashboard: v1's
score for a source rises over the first polls after an attack.

| Attack | From | To | What it sends | Label seen in testing |
|---|---|---|---|---|
| flood | h2, 10.0.0.2 | h1, port 80 | 2000 HTTP requests, a new connection each | DDoS |
| port scan | h3, 10.0.0.3 | h1, ports 20 to 30 | a TCP connect to each of 11 ports | PortScan |
| brute-force shape | h4, 10.0.0.4 | h1, port 22 | 300 short TCP connections | SSHBrute |

Each attack **opens the service it needs on h1** for its own duration, then the
listener stops by itself. That is not decoration. Tested with the backend's own
v1 code: against a closed port, or with a ping flood, the attacker scores about
two hundredths, far under the 0.75 threshold, and nothing appears. v1 responds
to completed TCP conversations. To show that live:

```
sudo python3 mininet/demo/attacks/flood.py --mode icmp     # a ping flood: nothing appears
sudo python3 mininet/demo/attacks/portscan.py --closed     # closed ports: nothing appears
sudo python3 mininet/demo/attacks/bruteforce.py --closed   # closed port 22: nothing appears
```

Unblocking the flood's source straight after the flood does not stick: its flows
stay in the switch's table for up to a minute, and v1 blocks it again on the next
poll. The sequence does not depend on it, because every attack uses a different
host.

## From the dashboard

**Simulate Attack** in the header opens the attack console (`/simulation`). It runs
the same scripts as above, through the backend: pick flood, port scan, brute-force
shape or the full sequence, optionally its negative control (`--mode icmp` /
`--closed`), and press Simulate. Admins only.

- It refuses to start, and says why, unless the backend's last poll of the switch
  succeeded, `ENFORCEMENT_MODE=simulated`, and the scripts are where it expects
  them. One run at a time.
- It also refuses an attack whose source host is **already blocked** (h2 for the
  flood, h3 for the scan, h4 for the brute-force shape): v1 skips a blocked host, so
  a second run would score high and record nothing. Unblock the node first. A
  negative control is never held up by this.
- The script's output streams into the page, then it watches for the incident for
  up to `SIMULATION_SCORE_WAIT_SECONDS` (default 45; a control looks for 20) and
  shows what v1 recorded. v1's score for a source keeps rising for a minute after
  the traffic stops, because OVS counts a rule's duration from when it was
  installed. If nothing is recorded it says the latest score and whether it was
  still rising, or that the host never appeared in a scored batch (the switch did
  not show the traffic).
- On Windows the scripts send their commands into WSL as root themselves
  (`GS_WSL_DISTRO`). A backend running on Linux/WSL as a normal user runs them with
  `sudo -n`, so it needs a passwordless sudo rule for its Python, or run it as root.
- `SIMULATION_SCRIPTS_DIR` and `SIMULATION_PYTHON` override where the scripts are
  and which interpreter runs them.

Nothing is posted to `/analyze`: the old synthetic Simulate button is gone.

## What to say about the labels

- The model that acts is binary. **The attack type on the dashboard is a
  port and volume heuristic, not a model output.** Say this before the first
  label appears.
- "DDoS": the heuristic's name for a source with more than five thousand packets.
  It is one host flooding another, not a distributed attack.
- "SSHBrute": port 22 and more than 250 packets. Anything the heuristic does not
  match is called "Botnet"; if that label appears, it is the fall-through.
- The `v2: DRY-RUN` header badge: v2 runs beside v1 and only advises. Its rules
  are logged, not enforced, and not shown in the incident list.
- Accuracy figures on the landing page are offline results on the 2017 CICIDS
  dataset. They are not a property of this live demo; do not quote them as one.
- If asked whether v1 detects attacks: it flags completed TCP conversations. It
  flagged ordinary web fetches in testing, and it does not see a ping flood or a
  scan of closed ports. What the demo shows is the mechanism: threshold crossed,
  host blocked (simulated), incident recorded, dashboard updated.

## What was NOT fixed and why

- **DoS Hulk**: no separate class in either model; not demonstrated. The flood
  here is an HTTP flood, and the heuristic calls it DDoS.
- **Botnet**: neither model detects it; not demonstrated.
- **v1's false positives on benign traffic**: real. That is why no background
  traffic runs during the demo.
- **The original attack scripts**: left as they were. They build and destroy
  their own topology and cannot be used with the long-lived one.

## Tested

The full sequence was run once on 2026-10-05 against the backend with v1 only
(v2 off, to save memory), Mininet in WSL, simulated enforcement, and no
background traffic: three attacks, three incidents, with the labels in the table
above. It has not been run with v2 on, with Ganache, or in front of the
dashboard in a browser.
