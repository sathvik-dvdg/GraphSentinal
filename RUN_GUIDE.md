# GraphSentinel — Run Guide

**Start here.** Two ways to start the system: **Docker Compose** (§4, use this for
the demo) and **manually, service by service** (§5, use this when you need to see
a traceback). §6 is the same verification either way — one command, nine checks.
Run it every time, and run it in front of the examiners. Before a demo, read §12.

Every command in §4–§6 was executed on 2026-10-04 on the development machine
(Windows 10, PowerShell, Docker Desktop 29.6.1) and its output is pasted where it
matters. What was **not** executed here is listed in §11 rather than presented as
working.

This guide does not replace the older documents; it is the short path through
them. For what it leaves out:

| for | read |
|---|---|
| the v2 path against demo flows (the gate refusing), and real OVS flows end to end | `RUNNING.md`, Tier 2 and Tier 3 |
| installing WSL2, Mininet and Open vSwitch | `INSTALLATION_GUIDE.md` |
| what needs a rebuild and what hot-reloads; `.env.docker.local`; the daemon token | `TEAM_SETUP.md` |
| starting Ganache and deploying the contract by hand | `HOW_TO_RUN.md` (predates the Compose stack) |
| the attack scenarios | `MININET_ATTACK_SCRIPTS.md` |

---

## 1. What you are starting

| part | what it does | Compose service | host port |
|---|---|---|---|
| blockchain | Ganache and the `IncidentLogger` contract; the audit trail | `blockchain` | 8546 |
| inference service | loads `ML/weights.pt`, scores 60 s flow windows, applies the mitigation policy it is sent | `inference` | 8081 |
| backend | owns the mitigation policy, consumes verdicts and rules, drives the v1 pipeline | `backend` | 8001 |
| frontend | React dashboard | `frontend` | 5174 (Compose), 5173 (manual) |
| traffic source | Mininet + OVS (`mininet/topologies/`), or the committed sample | — | — |

`dry_run = True` everywhere. Rules are generated, gated, logged and counted;
**nothing is installed on a switch.** See §9.

**The v2 path is on by default under Compose** (`GS2_ENABLED: "true"` in
`docker-compose.yml`, since 2026-10-04), so a fresh clone starts the path §6
verifies. The manual path (§5) sets it per terminal. With it off, nothing in §6
beyond checks 1, 2, 4, 5 and 6 can pass. To run the v1 path alone:
`docker compose -f docker-compose.yml -f docker-compose.v1.yml up -d`.

**One file a fresh clone still lacks: `ML/weights.pt`.** It is gitignored (72.7
MiB) and cannot be committed; `INTEGRATION.md` §1 says how to fetch it. Without it
the inference service never becomes healthy and checks 1, 2, 4–6, 8 and 9 fail.

---

## 2. Prerequisites

| | what this was run on |
|---|---|
| Docker Desktop | 29.6.1, with tens of GB free on `C:`. The four images total about 6.2 GB |
| Python (manual path, test suites) | **3.10.10**, with `ML/graphsentinel_v2/requirements.txt` and `backend/requirements.txt` installed (torch 2.13.0+cpu, torch-geometric 2.8.0, pandas 2.3.3, numpy 2.2.6). The containers run Python 3.12 with torch 2.4.0 |
| Node (frontend, manual path) | v22.19.0, npm 11.16.0. The frontend and blockchain images use `node:22-alpine` |
| Mininet / Open vSwitch | Linux or WSL2 only; **not installed on this machine** and not needed for §4–§6 |

**Memory.** This machine has 3.8 GB of RAM. Building four images at once crashed
npm; starting the stack while another start was still running made Ganache miss
its own 30-second start limit. Build one image at a time and start the stack once.

Storage Sense on this machine is limited to the Recycle Bin — see
`docs/machine/storage_sense_2026-10-04.md`. Do not turn it back on while a build
is running.

---

## 3. Environment files — read this before either path

`backend/.env` is **untracked**. Create it from the template:

```bash
cp backend/.env.example backend/.env
```

**One value needs your attention.** Every tracked source in the repository
declares the detection threshold as **0.75**. The `backend/.env` currently on this
machine sets **0.40**. That difference is why one backend test failed here and
nowhere else. Decide which is correct and make the tracked default and your local
file agree — do not leave them disagreeing, and do not change the tracked default
just to silence a test.

```powershell
# check what you are actually running with
Select-String -Path backend\.env, backend\.env.example -Pattern THRESHOLD
```

Compose does not read `backend/.env`; it uses the tracked `.env.docker`. The
manual path (§5) does read `backend/.env`. On this machine that file also sets
`ENFORCEMENT_MODE=ovs` and `DEMO_FALLBACK_FLOWS=false`, so a manually started
backend polls a Mininet daemon that is not there and reports each poll as failed.
That is expected and does not affect §6.

The model path, class order and mitigation policy come from `ML/model_card.json`
and the backend's own policy definition, not from the environment.

---

## 4. Path A — Docker Compose

From the repository root, in PowerShell.

```powershell
# 1. build, one image at a time (first time, or after a Dockerfile or dependency change)
docker compose build inference
docker compose build blockchain
docker compose build backend
docker compose build frontend

# 2. start everything from a clean state (the v2 path is on by default)
docker compose down -v
docker compose up -d

# 3. watch it come up
docker compose ps
```

On a quiet machine all four services were healthy **125 seconds** after
`docker compose up -d`:

```
SERVICE      STATUS                        PORTS
backend      Up About a minute (healthy)   0.0.0.0:8001->8000/tcp
blockchain   Up 2 minutes (healthy)        0.0.0.0:8546->8545/tcp
frontend     Up 25 seconds (healthy)       0.0.0.0:5174->5173/tcp
inference    Up 2 minutes (healthy)        0.0.0.0:8081->8080/tcp
```

**Start order.** The backend waits for `blockchain` to be *healthy* (the contract
address must exist) but only for `inference` to have *started*. That is deliberate:
without the gitignored `ML/weights.pt` the inference service never becomes healthy,
and the backend must still boot. So "backend healthy" does **not** mean the model
is loaded; §6 checks that directly. The frontend waits for a healthy backend.

```powershell
docker logs graphsentinel-backend        # the provenance gate and v2 lines
docker logs graphsentinel-inference

# stop, keeping volumes (the chain data and the backend's database)
docker compose down
# stop and wipe volumes — a clean slate
docker compose down -v
```

The run recorded in §6 used a local `docker-compose.override.yml` to set
`GS2_ENABLED: "true"`. That value is now the tracked default, so the resolved
configuration is the same and no override file is needed.

With the v2 path on and no Mininet, the backend log shows the provenance gate
refusing the demo flows, once and then at most once a minute. That is a pass, not
a fault (`RUNNING.md` Tier 2):

```
WARNI [graphsentinel.monitor] v2 provenance gate: REFUSING poll -- input not from OVS (sources {'demo': 1}, 1 flows). Nothing from this poll reaches the inference service. This is not a quiet network.
```

---

## 5. Path B — manually

Three terminals, PowerShell, from the repository root. Uses the **same ports as
Compose** (8081 and 8001), so §6 is identical. Stop the Compose stack first.

**Do not use port 8080 for the inference service on this machine.** Another
program (a Java process) already listens there and answers `/health` with 200, so
a bare "is it up?" check passes against the wrong service; uvicorn then fails to
bind with `[Errno 13]`.

### Terminal 1 — inference service

```powershell
cd ML\graphsentinel_v2
$env:GRAPHSENTINEL_MODEL_DIR = "C:\dev\GraphSentinal\ML"      # the folder holding weights.pt
python -m uvicorn graphsentinel.inference.service:app --host 127.0.0.1 --port 8081
```

Answers `/health` about 12 seconds after start.

### Terminal 2 — backend

```powershell
cd backend
$env:GS2_ENABLED     = "true"
$env:GS2_SERVICE_URL = "http://127.0.0.1:8081"
$env:GS2_MODEL_DIR   = "../ML"
python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8001
```

Answers `/health` about 16 seconds after start. Without Ganache running it reports
`blockchain.connected: false`; the v2 checks do not depend on the chain. To start
Ganache and deploy the contract by hand see `HOW_TO_RUN.md` — note that its deploy
step **rewrites `backend/.env`**.

The backend writes its SQLite database to `SQLITE_PATH` (default
`./graphsentinel.db` in `backend/`). Set `$env:SQLITE_PATH` to another file first
if you do not want this run in your local database.

### Terminal 3 — frontend

```powershell
cd frontend
npm run dev
```

Serves `http://localhost:5173` (HTTP 200 about 16 seconds after start).
`frontend/node_modules` must exist; `npm ci` creates it.

### Traffic

There is no replay script that feeds the backend: its monitor accepts flows from
OVS only, and refuses anything else. The committed sample is sent to the inference
service, with the backend's own policy, by §6's last two checks.

---

## 6. Verification — run this every time

One command, the same on both paths:

```powershell
python ML\verify_stack.py
```

It needs the Python environment of §2. Checks 1–7 take seconds
(`--skip-sample` stops there); checks 8 and 9 send the committed sample,
`ML/testdata/cicids2017_sample.csv` (18,264 flows, 58 windows), through the
inference service with the backend's policy and take about a minute.

| # | check | how it is checked | expected |
|---|---|---|---|
| 1 | inference `/health` | 200 **and** the payload has our `model_dir` and `memory` fields | pass |
| 2 | inference `/contract` | `contract_version` | `2.0.0` |
| 3 | backend `/health` lists the policy | `ml_v2.policy` has `enforceable`, `alert_only`, `floors` | pass |
| 4 | weights identity | sha256 in the served card = `ML/MANIFEST.json` = the file `ML/weights.pt` | all three equal |
| 5 | parameter count | `parameters` in the served card | **654,851** |
| 6 | class order | served card and backend contract | `BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet` |
| 7 | `dry_run` | backend `ml_v2.policy.dry_run` | **true** |
| 8 | **policy digest echo** | every scored window echoes the digest the backend publishes at `ml_v2.policy.sha256` | 58 of 58 |
| 9 | rules admitted / withheld | rules by class, each joined to its true label; withheld flows by class and reason | no rule on a wrong or benign flow |

Checks 8 and 9 are the ones worth showing someone. They are the proof that the
loop is closed: the backend's policy — not a table inside the model package —
decides every action, and anything below its floor is refused with a stated
reason.

**Output on Path A** (Compose, torch 2.4.0 in the container), 2026-10-04:

```
inference http://localhost:8081 | backend http://localhost:8001
  [PASS] 1 inference /health: HTTP 200, model_dir '/app/ML'
  [PASS] 2 inference /contract: contract_version 2.0.0
  [PASS] 3 backend /health lists the policy: HTTP 200, enforceable ['Volumetric_Flood', 'PortScan', 'BruteForce'], alert_only ['Botnet'], floors {'Volumetric_Flood': 0.9, 'PortScan': 0.85, 'BruteForce': 0.85, 'Botnet': 1.01}
  [PASS] 4 weights identity: served card 3db34022bcbab050, MANIFEST 3db34022bcbab050, ML/weights.pt 3db34022bcbab050
  [PASS] 5 parameter count: 654,851
  [PASS] 6 class order: BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet
  [PASS] 7 dry_run: backend policy.dry_run = True
  [PASS] 8 policy digest echo: 58 of 58 windows echoed d030e547ae90aafe, backend publishes d030e547ae90aafe
  [PASS] 9 rules admitted / withheld: admitted {'BruteForce:drop_port': 8, 'Volumetric_Flood:meter': 4}, on a wrong or benign flow: 0; withheld {'BruteForce': {'below_floor': 131}, 'Volumetric_Flood': {'below_floor': 102}, 'Botnet': {'class_suppressed': 1}, 'PortScan': {'below_floor': 68}}

9 of 9 checks passed
```

**Output on Path B** (manual, torch 2.13.0): identical line for line, except
check 1 reports `model_dir 'C:\\dev\\GraphSentinal\\ML'`. Same digest, same 12
rules, same withholdings.

**Reference result**, from the committed `ML/live_rule_check.json` over all 18,264
sample flows:

- all 58 windows echoed the policy digest;
- **12 rules admitted**, every one on a correctly classified flow;
- **0 rules on benign traffic, 0 on a wrong-class prediction**;
- PortScan's 0.85 floor was **never reached** — 0 of 68 correct PortScan
  predictions. Reported, not adjusted.

If your run differs from those numbers on the same sample, something is wrong with
your setup — start with checks 4 and 8.

**What check 9 is not — the unverified link.** The counts come from the inference
service's response to the sample, sent to it directly with the backend's policy.
"The loop is closed" is therefore verified **from the inference service outward**.
The backend's own ingestion path — OVS flow → monitor → provenance gate → v2
client → rules accepted and logged by the backend — **has never been exercised end
to end** with the installed model. The backend logs the same counts (`rules
admitted`, `withheld ... : reason`) only for flows that arrive through its monitor,
and the monitor accepts OVS flows only. Closing this needs one Mininet run
(`RUNNING.md` Tier 3) on Linux or WSL2, which this machine does not have. See §11.

### The test suites

```powershell
cd ML\graphsentinel_v2
python -m pytest tests -q -p no:cacheprovider      # 165 passed

cd ..\..\backend
python -m pytest -q -p no:cacheprovider            # 233 passed, 3 skipped
```

---

## 7. Traffic from Mininet

Linux or WSL2 only. **Not run for this guide**: Mininet and Open vSwitch are not
installed in this machine's WSL. The tested procedure is `RUNNING.md` Tier 3;
installation is `INSTALLATION_GUIDE.md`; the topology is
`mininet/topologies/base_topology.py` and the scenarios are in
`MININET_ATTACK_SCRIPTS.md`.

The flow source is gated: the provenance allowlist admits `data_source == "ovs"`
only, it fails closed, and it refuses a whole batch rather than part of one. A
demo-substituted batch is rejected by design — if your flows are not being scored,
check the provenance gate's log line before you check anything else.

---

## 8. Resetting

```powershell
docker compose down -v                  # containers and volumes
```

On the manual path the local app database is `backend/graphsentinel.db`
(gitignored); delete it for a clean slate.

Do **not** delete anything under `ML/`. `ML/prefix_epoch31/`,
`ML/phase2b_runs/`, `ML/retrain_logs/` and the audit JSONs are the evidence the
project's results rest on.

---

## 9. What this demo shows, and what it does not

**Shows:**

- flow-level attack/benign discrimination at **binary F1 0.9961**;
- a closed rule-generation loop: the backend's policy gates every rule, digests are
  echoed, withheld flows are counted with reasons;
- on the committed sample, 12 rules admitted and none wrong.

**Does not show, and must not be claimed:**

- **live mitigation.** `dry_run = True`; no rule has ever reached a switch.
- **real-time performance.** Latency has not been measured for the installed model.
- **zero-day detection.** Nothing here tests unseen attack families.
- **reliable class-conditional action.** The model cannot separate PortScan from
  BruteForce; on the test split, Volumetric_Flood is the only class with a correct
  end-to-end path, and PortScan's floor is never reached.

Every number above comes from `MODEL_BEHAVIOUR.md`. If a figure here disagrees
with that file, that file is right and this one needs fixing.

---

## 10. Troubleshooting

| symptom | cause |
|---|---|
| `docker compose build` fails in `npm ci` for `blockchain` with "package.json and package-lock.json are not in sync" | an out-of-sync lock file; fixed in commit `e7d6517`. Pull, or run `npm install --package-lock-only` in `blockchain/` |
| a build dies with `npm error Exit handler never called!` | memory. Build one image at a time (§4) |
| `blockchain` exits with "Ganache did not start within 30s" | the machine was too busy at start-up. Wait, then `docker compose up -d` again |
| `cannot stop container ... is zombie and can not be killed` | a Docker Desktop fault seen three times on this machine. `docker compose up -d --force-recreate <service>` |
| check 3 or 7 fails, `ml_v2 = {'enabled': False, ...}` | the v2 path is off: the stack was started with `docker-compose.v1.yml` or a local override sets `GS2_ENABLED` to false (§1), or `GS2_ENABLED` is not set (§5). `docker compose config` shows the resolved value |
| check 1 passes but nothing else does, on the manual path | something else is answering on that port (8080 on this machine). Use 8081 |
| inference never becomes healthy | `ML/weights.pt` is missing (it is gitignored); see `INTEGRATION.md` §1 |
| service healthy but no verdicts through the backend | the provenance gate is refusing the batch — check `data_source` in `docker logs graphsentinel-backend` |
| no PortScan rule ever appears | expected. Its floor is never reached on the sample. Check the withheld counts before suspecting a bug |
| a test passes elsewhere and fails here | `backend/.env` — see §3 |
| check 4 fails | `ML/weights.pt` and `ML/MANIFEST.json` are out of step; re-unzip the result at the repository root |

---

## 11. Not executed for this guide

- **Mininet and real OVS flows** (§7): not installed on this machine.
- **Ganache and the contract deploy by hand**: the deploy script rewrites the
  untracked `backend/.env`, so it was not run. Under Compose the `blockchain`
  service does this itself and was healthy.
- **A fresh virtual environment** built from the two requirements files: the
  manual path and the suites ran in the existing Python 3.10.10 environment.
  `ML/graphsentinel_v2/requirements.txt` is unpinned (`torch>=2.1`), so a fresh
  install may resolve different versions from the ones listed in §2.
- **`docker compose build` with no service name** (all four at once): it failed
  here, first on the lock file and then on memory. The four per-service builds in
  §4 are what succeeded.
- **UNVERIFIED LINK — the backend's ingestion path, end to end.** Checks 8 and 9
  exercise the inference service with the backend's policy; they do not pass a
  single flow through the backend's monitor. OVS flow → monitor → provenance gate
  → v2 client → rules accepted by the backend has not been run with the installed
  model, so the backend's own admitted/withheld log lines have never been observed
  on real traffic (§6, "What check 9 is not"). It is the one link between this
  project and a loop demonstrated end to end. It needs a Mininet run (`RUNNING.md`
  Tier 3) on Linux or WSL2; it is scheduled for when WSL2 with Mininet and Open
  vSwitch is available, and until then must be stated wherever the loop is claimed.

---

## 12. Before a demo

This machine has 3.8 GB of RAM. Preparing this guide on it produced **two flaky
failures** — npm crashing mid-build (`Exit handler never called!`) and Ganache
missing its 30-second start limit — and **two session restarts mid-build**. Docker,
Node, Python, Ganache and a browser do not fit comfortably in 3.8 GB. So, in order
of value:

1. **Record a successful run.** Screen-capture `docker compose up -d` through all
   nine checks of `python ML\verify_stack.py`, with the output legible. If the
   live run dies on memory, show the recording and carry on. No recording is
   committed yet.
2. **Build ahead, never during.** Run the four `docker compose build <service>`
   commands of §4 the night before. On the day, `docker compose up -d` only:
   nothing on the critical path should compile or download.
3. **Close everything else.** The browser above all; the frontend needs one tab.

**Build clean at least once before the day, on purpose.** `blockchain/package-lock.json`
was out of sync from 2026-09-06 (commit `d135fce`) until it was fixed in `e7d6517`
on 2026-10-04, and for that month `docker compose build` kept passing because
Docker reused a cached `npm ci` layer. The break only showed when the cache was
lost. A cached build proves the cache, not the repository:
`docker compose build --no-cache <service>` is the check that a fresh clone builds.
