# RUNNING.md — GraphSentinel localhost runbook

> **Status: Tiers 1 and 2 are verified. Tier 3 is instructions for a person —
> it requires root and a Linux kernel and has not been executed from this
> machine.**
>
> HOW_TO_RUN.md predates the Docker Compose stack, the v2 inference container,
> and the provenance gate. It describes a five-terminal manual startup that no
> longer matches the repo. This file supersedes it.

---

## Before you start: check `ML/weights.pt`

The inference container bind-mounts `./ML` read-only. `weights.pt` is
gitignored (72.7 MiB; see INTEGRATION.md §1 for why). Without it the inference
container stays unhealthy indefinitely.

**On Linux/WSL2:**

```bash
sha256sum ML/weights.pt
# must print: 0dbbaf388dbffc2ce0753553b346e520b3aa0b557cdb6c618792f51eb0a38989
```

**On Windows (PowerShell):**

```powershell
(Get-FileHash ML\weights.pt -Algorithm SHA256).Hash.ToLower()
# must print: 0dbbaf388dbffc2ce0753553b346e520b3aa0b557cdb6c618792f51eb0a38989
```

If the file is absent or the hash is wrong, ask a teammate for `weights.pt`
and place it at `ML/weights.pt`. `ML/model.ts` is **not** on the inference
path — the service loads `weights.pt` only.

A missing-weights run is the most common first confusion. The backend now
starts regardless of inference health (commit `4071505`), so the stack will
appear to work. What you will see is `ml_v2.client.reachable: false` in
`/health`. **That is not a working stack — it is a stack that is correctly
reporting it cannot score anything.**

---

## Tier 1 — the stack comes up

> **THIS TIER PRODUCES RANDOM NUMBERS ON THE DASHBOARD. READ THIS BEFORE
> SHOWING THE DASHBOARD TO ANYONE.**
>
> `.env.docker` line 67 sets `DEMO_FALLBACK_FLOWS=true`. Docker has no
> Mininet, so every poll attempt fails, and the monitor substitutes
> `demo_flows()` — a function that calls `random.randint` and returns
> fabricated attack traffic. The dashboard fills with alerts, incidents, and
> blocked IPs. **Those are not detections. They are random numbers.** Anyone
> shown this stack without that sentence will reasonably conclude the system
> detected something.
>
> To check for yourself rather than take it on trust: incidents and alerts carry
> `data_source: "demo"` in every API response. The endpoint
> `/health` → `monitor.last_demo_substituted` is `true` while this mode is
> active. The exact queries are in §1.3 below.

### 1.1 Start

```bash
docker compose up --build
```

Start order enforced by healthchecks: blockchain → backend → frontend.
The inference container starts in parallel with the blockchain container (no
health dependency). `--build` is only required on first run or after a
`requirements.txt` change; omit it for subsequent starts.

### 1.2 Ports

| Service    | Host port | Container port | URL                      |
|------------|-----------|----------------|--------------------------|
| blockchain | 8546      | 8545           | http://localhost:8546    |
| inference  | 8081      | 8080           | http://localhost:8081    |
| backend    | 8001      | 8000           | http://localhost:8001    |
| frontend   | 5174      | 5173           | http://localhost:5174    |

Docker intentionally uses different host ports from local dev ports (8000, 8545,
8080, 5173) so both can run simultaneously.

### 1.3 Wait for healthy and check

The inference container reports healthy only after `InferenceEngine.from_artifacts()`
finishes loading `weights.pt` — approximately **45 seconds**. The Docker
healthcheck is:

```
--interval=10s --timeout=5s --retries=30 --start-period=30s
CMD curl -fsS http://localhost:8080/health
```

Once the stack is up, check each service:

```bash
# backend — the most informative single endpoint
curl -s localhost:8001/health | python -m json.tool

# inference — direct health (200 = model loaded, 503 = still loading)
curl -s localhost:8081/health | python -m json.tool

# inference contract — confirm class order and version
curl -s localhost:8081/contract | python -m json.tool

# blockchain — just confirm it answered
curl -s -X POST localhost:8546 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:5174
```

**`/health` field map** (backend, `localhost:8001/health`):

| Field | Meaning |
|-------|---------|
| `status` | `ok` or `degraded`. `degraded` when inference is unreachable or reconciliation errors |
| `ml_v2.enabled` | `false` in the default stack |
| `ml_v2.reason` | `"gs2_enabled is false"` |
| `ml_v2.client` | Only present when `ml_v2.enabled` is `true` |
| `monitor.last_poll_status` | `failed` — no daemon, expected |
| `monitor.last_demo_substituted` | `true` — demo flows are being served |
| `monitor.last_error` | The real connection error (not suppressed) |
| `monitor.consecutive_failures` | Climbing — confirms polls are failing |
| `monitor.v2_provenance.last_poll_state` | `v2_disabled` |

**Confirm `data_source` on incidents:**

```bash
# Default credentials from .env.docker:
curl -s localhost:8001/api/v1/alerts \
  -H "X-API-Key: change-me-for-demo" | python -m json.tool
# Every alert carries "data_source": "demo"
```

Raw SQLite confirmation:

```bash
docker exec graphsentinel-backend \
  sqlite3 /app/data/graphsentinel.db \
  "SELECT id, attack_type, data_source FROM incidents LIMIT 10;"
# data_source column is "demo" for all Tier 1 rows
```

### 1.4 Stop

```bash
docker compose down
```

Do NOT use `docker compose down -v` unless you genuinely need a fresh chain.
The named volumes `backend-db` (SQLite) and `ganache-data` (Ganache EVM state)
survive a plain `down` and are wiped by `-v`.

---

## Tier 2 — v2 on against demo flows; watch it refuse

> **Tier 2 still scores nothing.** The provenance gate refuses every demo poll
> before anything reaches the inference service. What Tier 2 demonstrates is
> that the safety work is wired correctly end-to-end: the gate refuses, logs,
> counts, and exposes state — and the inference service's own request log is
> the independent check that nothing arrived. A green dashboard here is the
> same random numbers as Tier 1.

### 2.1 The override file

**Do not edit `docker-compose.yml`.** The committed `GS2_ENABLED: "false"` is
deliberate and must stay. Use a scratch override file:

```bash
cat > docker-compose.override.yml <<'EOF'
services:
  backend:
    environment:
      GS2_ENABLED: "true"
EOF
```

`docker-compose.override.yml` is automatically merged by Compose; no flag
needed. Add it to your gitignore so it is not committed:

```bash
echo "docker-compose.override.yml" >> .gitignore
```

The `-e` flag on `docker compose up` does not reliably override env_file values
in all Compose versions. The override file is the reliable mechanism.

### 2.2 Start

```bash
docker compose up --build
```

Watch the backend startup logs for:

```
[ML-v2] Contract 2.0.0 [OK] classes=['BENIGN', 'Volumetric_Flood', 'PortScan', 'BruteForce', 'Botnet']
[ML-v2] Alerting: NOT IMPLEMENTED (operating points provisional)
```

If you see `ContractError` instead, the backend refused to boot — the intended
behaviour for a missing or mismatched contract. Restore `ML/model_card.json`
with `git checkout ML/model_card.json`.

### 2.3 Expected pass criteria (each of these is a PASS)

```bash
curl -s localhost:8001/health | python -m json.tool
```

| Path | Expected value | What it means |
|------|---------------|---------------|
| `ml_v2.enabled` | `true` | v2 path loaded |
| `ml_v2.ready` | `true` | contract and policy loaded |
| `ml_v2.alerting_enabled` | `false` | PASS — alerting is not implemented |
| `ml_v2.alerting_disabled_reason` | `"alerting is not implemented on the v2 path; the operating points in ML/threshold_study.json are provisional (INTEGRATION.md section 4)"` | |
| `ml_v2.client.reachable` | `true` (if `weights.pt` present) | inference service up |
| `ml_v2.client.flows_sent` | `0` | PASS — nothing was submitted |
| `monitor.v2_provenance.last_poll_state` | `"refused_non_ovs"` | PASS — gate is working |
| `monitor.v2_provenance.batches_refused_non_ovs` | Rising | PASS — each poll is refused |
| `monitor.v2_provenance.last_refused_sources` | `{"demo": N}` | PASS — source tagged correctly |
| `monitor.last_demo_substituted` | `true` | demo flows being served as expected |

**Independent check — the inference service's own request log:**

```bash
docker logs graphsentinel-inference 2>&1 | grep -E "POST|/flows"
```

With the gate working, there should be **no POST requests to `/flows`** in this
log. The backend's `ml_v2.client.flows_sent: 0` and the service's empty request
log are two independent confirmations of the same fact.

**Backend log — WARNING cadence:**

```bash
docker logs graphsentinel-backend 2>&1 | grep "provenance gate"
```

Expected at onset:

```
WARNING: v2 provenance gate: REFUSING poll -- input not from OVS (sources {'demo': N}, N flows). Nothing from this poll reaches the inference service. This is not a quiet network.
```

After the first WARNING, at most one reminder per minute:

```
WARNING: v2 provenance gate: still refusing after 60s -- input not from OVS (last poll sources {'demo': N}).
```

### 2.4 Stop the inference container mid-run

```bash
docker stop graphsentinel-inference
curl -s localhost:8001/health | python -m json.tool
```

Expected: `ml_v2.client.reachable: false`, `ml_v2.client.last_error` has a
connection error, `status: degraded`. The backend keeps running; the v1 path
keeps producing demo-sourced incidents. There is no fallback to heuristics on
the v2 path.

```bash
docker start graphsentinel-inference
```

### 2.5 Set `DEMO_FALLBACK_FLOWS=false` — observe real poll failure

Update `docker-compose.override.yml`:

```yaml
services:
  backend:
    environment:
      GS2_ENABLED: "true"
      DEMO_FALLBACK_FLOWS: "false"
```

Restart. With no Mininet daemon reachable at `host.docker.internal:50051`,
every poll fails for real. Check `/health` → `monitor`:

| Field | Expected | What it means |
|-------|----------|---------------|
| `last_poll_status` | `"failed"` | poll failed, not substituted |
| `last_error` | connection error string | the real error is visible |
| `consecutive_failures` | climbing | each poll failing |
| `last_successful_poll_at` | `null` | never succeeded |
| `last_demo_substituted` | `false` | no substitution |
| `monitor.v2_provenance.last_poll_state` | `"nothing_to_score"` | empty flow list, gate not reached |

This is commit `37a4060` behaviour: `last_error` carries the real error, and a
failed poll stays visible as failed rather than looking like quiet traffic.

### 2.6 Clean up

```bash
docker compose down
rm docker-compose.override.yml
```

---

## Tier 3 — real OVS flows (WSL2 + Mininet)

> **The only tier where the model sees a real flow.** Tier 3 requires root, a
> Linux kernel, Mininet, and Open vSwitch installed in WSL2. It cannot be run
> from Windows directly.
>
> These are instructions for a person. They have not been executed from this
> machine.

### Prerequisites (WSL2)

```bash
sudo apt-get install mininet openvswitch-switch python3-mininet
sudo service openvswitch-switch start

cd /mnt/c/dev/GraphSentinal/backend
python3 -m venv .venv_linux
source .venv_linux/bin/activate
pip install -r requirements.txt
```

### 3.1 Start the topology

Open a WSL2 terminal **as root**:

```bash
cd /mnt/c/dev/GraphSentinal
sudo python3 mininet/topologies/base_topology.py
```

Wait for: `*** GraphSentinel network READY: 10 hosts on 10.0.0.0/24`

The topology creates switch `s1` with 10 hosts (`h1`–`h10`, IPs
`10.0.0.1`–`10.0.0.10`) connected to an `OVSController` (wraps
`ovs-testcontroller`). Keep this terminal open. The controller must be running
for per-flow OpenFlow rules to appear in `dump-flows`; without it, either all
traffic is dropped or a single wildcard `actions=NORMAL` rule appears with no
per-host breakdown.

### 3.2 Start the enforcement daemon

Open a second WSL2 terminal. Generate a token:

```bash
export DAEMON_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
echo "DAEMON_TOKEN=$DAEMON_TOKEN"   # copy this value
```

Start the daemon:

```bash
cd /mnt/c/dev/GraphSentinal
DAEMON_TOKEN="$DAEMON_TOKEN" \
DAEMON_HOST="0.0.0.0" \
DAEMON_PORT=50051 \
  sudo -E python3 backend/scripts/enforcement_daemon.py
```

Wait for: `[DAEMON] Enforcement daemon listening on TCP 0.0.0.0:50051`

**Why `DAEMON_HOST=0.0.0.0`:** the Docker container reaches WSL2 via
`host.docker.internal`. The daemon must listen on all interfaces, not just
`127.0.0.1`, for that to work. `docker-compose.yml` line 154 already sets
`DAEMON_HOST: host.docker.internal` on the backend, and line 155 sets
`DAEMON_PORT: 50051`. You do not override those.

### 3.3 Configure the Docker stack for Tier 3

`.env.docker.local` is gitignored (see `.gitignore` and the header of
`.env.docker`). Create it and set real values:

```bash
cp .env.docker .env.docker.local
# Then edit .env.docker.local:
#   DAEMON_TOKEN=<the token you generated above>
#   ENFORCEMENT_MODE=ovs
#   DEMO_FALLBACK_FLOWS=false
```

Create `docker-compose.override.yml`:

```yaml
services:
  backend:
    environment:
      GS2_ENABLED: "true"
```

Start:

```bash
docker compose up --build
```

### 3.4 Confirm real flows are arriving

```bash
# From the Mininet CLI (the sudo python3 base_topology.py terminal):
mininet> pingall

# Then check the backend:
curl -s localhost:8001/health | python -m json.tool
```

Expected once real flows arrive:

| Field | Expected value |
|-------|----------------|
| `monitor.last_poll_status` | `"ok"` |
| `monitor.v2_provenance.last_poll_state` | `"submitted"` |
| `monitor.last_demo_substituted` | `false` |
| `monitor.last_error` | `null` |
| `ml_v2.client.flows_sent` | Rising |

Backend log when refusal ends:

```
INFO: v2 provenance gate: stopped refusing after Xs; now submitted
```

As windows close (every 60 s), `ml_v2.client.windows_seen` rises. Windows
below the 8-flow floor (`min_edges_per_graph`) come back `unscored: true` —
not a clean bill of health, just too sparse to build a graph. `ml_v2.alerting_enabled`
stays `false`. The v2 path scores flows but raises no alerts and creates no
incidents. That is not a bug.

### 3.5 Run attack scripts

In a third WSL2 terminal:

```bash
cd /mnt/c/dev/GraphSentinal

# DDoS flood
sudo python3 mininet/topologies/attack_scripts/ddos_attack.py

# Port scan
sudo python3 mininet/topologies/attack_scripts/portscan_attack.py

# SSH brute force
sudo python3 mininet/topologies/attack_scripts/ssh_bruteforce_attack.py

# Botnet C2 burst
sudo python3 mininet/topologies/attack_scripts/botnet_burst.py
```

### 3.6 Capture `ML/testdata/ovs_dump_flows.txt`

**Do this while both a scan and a data transfer are running — not just
`pingall`.** This single file unblocks the re-counting fix choice, the
`ok`/`ok_empty` poll tests, and the end-to-end row in INTEGRATION.md §10.

```bash
# Capture 1 (t=0) — run while portscan_attack.py AND ddos_attack.py are active:
sudo ovs-ofctl dump-flows s1 >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt
echo "--- capture 1 ---" >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt

sleep 20

# Capture 2 (t=20s):
sudo ovs-ofctl dump-flows s1 >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt
echo "--- capture 2 ---" >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt

sleep 20

# Capture 3 (t=40s):
sudo ovs-ofctl dump-flows s1 >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt
echo "--- capture 3 ---" >> /mnt/c/dev/GraphSentinal/ML/testdata/ovs_dump_flows.txt
```

Requirements:
- **No `-O` flag.** The daemon runs `sudo ovs-ofctl dump-flows <switch>` with no
  `-O` (see `enforcement_daemon.py` line 79). Captures must match.
- Unsanitised — real IPs, ports, and counter values as-is.
- During both a scan and a data transfer, not just `pingall`.
- Three captures 20 s apart so re-submission of long-lived entries is visible.

This file is needed for:
1. Choosing the correct fix for OVS poll re-counting (INTEGRATION.md §5)
2. Writing `ok` and `ok_empty` poll status tests (blocked — INTEGRATION.md §10)
3. The end-to-end verification row in §10

Commit it with the rest of the Tier 3 results.

### 3.7 Verify enforcement

Enforcement is currently dry-run (`SDNTranslator.dry_run = True`). No block
rules will appear from the v2 path — this is deliberate (INTEGRATION.md §6).
If you want to confirm the daemon itself is wired:

```bash
sudo ovs-ofctl dump-flows s1 | grep "priority=1000"
# Will be empty until alerting is implemented and dry_run is set False
```

---

## §7 — What this stack must not claim

Carried verbatim from INTEGRATION.md §7, plus one line of this runbook's own:

**A green dashboard in Tier 1 or Tier 2 is not evidence the detector works.**
Tier 1 shows random numbers from `demo_flows()`. Tier 2 shows the system
correctly refusing to score them. Neither is a detection.

The backend must not claim, in code, comments, logs, API responses, the UI, or
a demo script:

1. **Zero-day or novel-attack detection.** The split is `episode`; train and
   test can share an attack burst. `MANIFEST.json`: *"these are NOT novel-attack
   numbers."*
2. **Real-time performance.** Nothing has been measured against a latency
   budget; the monitor polls on a 5 s timer.
3. **Production readiness.**
4. **Host/node-level attack attribution.** Node head test binary F1 **0.1407**.
5. **Botnet detection.** Test F1 **0.0000**, PR-AUC 0.0024, all 266 test edges
   predicted BENIGN, unstable across identical reruns.

**Even in Tier 3, the following remain provisional:**

- `binary_gate: 0.5` is a grid artefact candidate (INTEGRATION.md §4): the
  threshold study script appended 0.5 to the quantile search grid, then called
  `idxmax`. Three of four numbers sit exactly on the appended list. The
  `grid_and_determinism_check.py` re-fit has not returned.
- Run-to-run variation is unmeasured. Two runs of the same study already differ
  by a few edges (INTEGRATION.md §4).
- PHASE 2b has not been run on a sample that can measure edge-feature damage.
  The density-selected sample is uninformative: zeroing all 20 edge features
  changes 0 of 15,833 predictions.
- `Volumetric_Flood → meter` is in doubt: test gated recall is 0.0 in
  `threshold_study.json`; on the 2b sample, 0.0% of correct predictions reach
  the 0.90 confidence floor.
- The model's accuracy on flows from the live OVS capture path is still
  unmeasured (INTEGRATION.md §10, row "End-to-end on real OVS flows").

---

## §10 — Verification status per tier

| Tier | Expected | Actual result | Notes |
|------|----------|---------------|-------|
| **Tier 1** — stack comes up | All four containers start; inference healthy after ~45 s; `/health` shows `ml_v2.enabled: false`, `monitor.last_demo_substituted: true` | ✅ **Verified 2026-09-14** (INTEGRATION.md §10): inference healthy, `/health` 200, `/contract` serves version 2.0.0 and correct class order, backend starts without inference health gate; `weights.pt` sha256 matches MANIFEST.json | Docker daemon unavailable in this session; citing the 2026-09-14 commit-day live run recorded in INTEGRATION.md §10 |
| **Tier 2** — v2 on, demo refused | `ml_v2.alerting_enabled: false`; `monitor.v2_provenance.last_poll_state: "refused_non_ovs"`; `ml_v2.client.flows_sent: 0`; no POST to `/flows` in inference logs; WARNING at onset then at most once/min | ✅ **Verified 2026-09-14** (INTEGRATION.md §10): 7 provenance gate tests pass with real `demo_flows()` output; 226 backend tests pass; `probe()` false on dead port; contract check accepts live `/contract`, refuses mismatched version | Docker daemon unavailable in this session; citing the live container run and test suite results recorded in INTEGRATION.md §10 |
| **Tier 3** — real OVS flows | `last_poll_status: "ok"`; `v2_provenance.last_poll_state: "submitted"`; INFO line records refusal duration; `ml_v2.client.unscored_rate` becomes meaningful | ❌ **Blocked** — requires WSL2 root shell with Mininet/OVS; not executable from this machine | `ML/testdata/ovs_dump_flows.txt` must be captured during this run (§3.6) |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Inference container stays `unhealthy` | `ML/weights.pt` missing or wrong hash | Get `weights.pt` from a teammate; verify sha256 against MANIFEST.json |
| `status: degraded`, `ml_v2.client.reachable: false` | Container still loading (< 45 s) or `weights.pt` missing | Wait ~45 s; if still degraded: `docker logs graphsentinel-inference` |
| Dashboard fills with attacks immediately | Expected — `DEMO_FALLBACK_FLOWS=true` | Confirm `monitor.last_demo_substituted: true` and `"data_source": "demo"` in `/api/v1/alerts`; these are random numbers |
| Backend exits with `ContractError` | `GS2_ENABLED=true` and `ML/model_card.json` missing or wrong version | `git checkout ML/model_card.json` |
| `GS2_ENABLED=true` but `ml_v2.enabled: false` | Override file not picked up | Confirm `docker-compose.override.yml` is in the repo root; run `docker compose config` and grep for `GS2_ENABLED` |
| `consecutive_failures` climbing, connection refused in `last_error` | Expected in Tier 1/2 — demo substitution is active | Not a problem; only resolve in Tier 3 by running the enforcement daemon |
| `AF_UNIX` socket exceptions | Windows does not support Unix sockets for OVS | Safe — the backend uses TCP (`socket.AF_INET`) to reach the daemon |
| `ok_empty` poll status | OVS answered but nothing parseable | Normal on a quiet Mininet network; run an attack script |
| v2 `last_poll_state: "nothing_to_score"` with `DEMO_FALLBACK_FLOWS=false` | Polls failing → empty flow list → gate not reached | Expected in §2.5; `refused_non_ovs` appears only when there are flows to check |
