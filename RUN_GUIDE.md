# GraphSentinel — Run Guide

**Start here.** Two ways to start the system: **Docker Compose** (§4, use this for
the demo) and **manually, service by service** (§5, use this when you need to see
a traceback). §6 is the same verification either way — one command, ten checks.
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

**Two detection paths run in the backend** (`MODEL_BEHAVIOUR.md` §1.1). The
inference service above is **v2**: `dry_run = True`, its rules are generated,
gated, logged and counted, and none is installed. **v1** is an older two-class
model inside the backend process; it runs on every poll whether or not v2 is on,
and it is the one that creates incidents, blocks hosts and writes to the chain.
v1 is **not** dry-run: Compose sets `ENFORCEMENT_MODE=simulated`, so here it logs
its blocks and applies nothing, but with `ENFORCEMENT_MODE=ovs` and the
enforcement daemon it installs real drop rules. See §9.

**The v2 path is on by default under Compose** (`GS2_ENABLED: "true"` in
`docker-compose.yml`, since 2026-10-04), so a fresh clone starts the path §6
verifies. The manual path (§5) sets it per terminal. With it off, nothing in §6
beyond checks 1, 2, 4, 5 and 6 can pass. To run the v1 path alone:
`docker compose -f docker-compose.yml -f docker-compose.v1.yml up -d`.

**One file a fresh clone still lacks: `ML/weights.pt`.** It is gitignored (72.7
MiB) and cannot be committed; `INTEGRATION.md` §1 says how to fetch it. What
happens without it was run, not reasoned — see "A fresh clone" in §6.

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

Two files the manual path needs are **untracked**. Create both from their
templates:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

`frontend/.env` was tracked until 2026-10-04 and carried the backend's API key in
a `VITE_` variable, which the dev server delivers to the browser. The variable was
unused and is gone, but the value is still in every earlier commit; it is the demo
default, so change it for anything that is not a demo. Compose reads neither file.

**One value needs your attention.** Every tracked source in the repository
declares the detection threshold as **0.75**. The `backend/.env` currently on this
machine sets **0.40**. That difference is why one backend test failed here and
nowhere else, it is why §6's check 10 fails on the manual path, and it is not
neutral: the threshold is v1's, the path that blocks, and `MODEL_BEHAVIOUR.md`
§1.2 measures 0.40 as strictly worse for wrong blocks. Recommended: 0.75
everywhere. Decide which is correct and make the tracked default and your local
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

All four services were healthy **127 seconds** after `docker compose up -d` on the
last run (125 on an earlier one); the command itself returned after 119:

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

The backend's health check allows it **180 seconds** to start. That figure was
chosen on an idle machine, the same condition the 75 it replaced was chosen
under, and has not been checked under load: if the machine is busy (a build, a
browser, a screen recorder) treat a slow start as expected, not as a fault. It allowed 75 until
2026-10-04; on this machine the backend needed longer three times that day, was
marked unhealthy, and `docker compose up -d` exited with `dependency failed to
start` **without starting the frontend** — on a fresh clone too. If you see that
on an older checkout, wait for the backend to turn healthy and run
`docker compose up -d` again.

This was `service_healthy` when the service was first wired in and was changed on
purpose (commit `4071505`, 2026-09-14); it was reviewed again on 2026-10-04 and
kept. It is not a race that can produce a wrong result: until the model is in
memory the backend reports `ml_v2` unreachable, scores nothing, and tries again on
the next poll. **Wait for `inference` to show `(healthy)` in `docker compose ps`
before running §6** — about 45 seconds after start, longer on a busy machine.

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
cd ML/graphsentinel_v2
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
python ML/verify_stack.py
```

It needs the Python environment of §2. Checks 1–7 and 10 take seconds
(`--skip-sample` runs only those); checks 8 and 9 send the committed sample,
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
| 10 | **v1's threshold and enforcement mode** | backend `/health` → `v1`, against `backend/.env.example` | **0.75**, `simulated` |

**Checks 1–9 are all about v2**, the audited model, which blocks nothing. Not one
of them exercises v1, the path that creates incidents, blocks hosts and writes the
chain (§1). Two stacks can pass them line for line while running v1 differently,
and on this machine the two paths did: Compose reads `.env.docker` (0.75,
`simulated`) and the manual path reads the untracked `backend/.env` (0.40, `ovs`).
(That file was brought back to the tracked values on 2026-10-04; it is untracked,
so nothing stops it drifting again, which is what check 10 is for.)
Check 10 scores nothing; it reads back what v1 is configured to do and fails when
that is not the tracked configuration. It does not test whether v1's detections
are right — `MODEL_BEHAVIOUR.md` §1.2 is the only measurement of that.

Checks 8 and 9 are the ones worth showing someone. They are the proof that the
loop is closed: the backend's policy — not a table inside the model package —
decides every action, and anything below its floor is refused with a stated
reason.

**A check has three outcomes: `PASS`, `FAIL` and `UNVERIFIABLE`.** The last means
what the check reads was not there to be read. Checks 5 and 6 describe the loaded
model but read the model card, which the service serves whether or not a model is
in memory; without `ML/weights.pt` they used to pass on a model that was not
there, and now report `UNVERIFIABLE` whenever check 1 fails. Checks 7 and 10 do
the same when the backend publishes no policy or does not answer, and 9 when 8
could not score the sample. `UNVERIFIABLE` counts against the exit code. A
service that refuses the connection, hangs, or answers with something that is not
JSON is reported on its check's line, never as a traceback.

**Output on Path A** (Compose, torch 2.4.0 in the container), 2026-10-04:

```
inference http://localhost:8081 | backend http://localhost:8001
  [PASS] 1 inference /health: HTTP 200, model_dir '/app/ML'
  [PASS] 2 inference /contract: contract_version 2.0.0
  [PASS] 3 backend /health lists the policy: HTTP 200, enforceable ['Volumetric_Flood', 'BruteForce'], alert_only ['PortScan', 'Botnet'], floors {'Volumetric_Flood': 0.9, 'PortScan': 0.85, 'BruteForce': 0.85, 'Botnet': 1.01}
  [PASS] 4 weights identity: served card 3db34022bcbab050, MANIFEST 3db34022bcbab050, ML/weights.pt 3db34022bcbab050
  [PASS] 5 parameter count: 654,851
  [PASS] 6 class order: BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet
  [PASS] 7 dry_run: backend policy.dry_run = True
  [PASS] 8 policy digest echo: 58 of 58 windows echoed e99290226e2d4ad9, backend publishes e99290226e2d4ad9
  [PASS] 9 rules admitted / withheld: admitted {'BruteForce:drop_port': 8, 'Volumetric_Flood:meter': 4}, on a wrong or benign flow: 0; withheld {'BruteForce': {'below_floor': 131}, 'Volumetric_Flood': {'below_floor': 102}, 'Botnet': {'class_suppressed': 1}, 'PortScan': {'below_floor': 68}}
  [PASS] 10 v1 threshold and enforcement mode: running threshold 0.75, mode 'simulated'; tracked default 0.75, 'simulated'

10 of 10 checks passed
```

**Output on Path B** (manual, torch 2.13.0): checks 1–9 identical line for line,
except check 1 reports `model_dir 'C:/dev/GraphSentinal/ML'`. Same digest, same 12
rules, same withholdings. **Check 10 fails on this machine**, and should:

```
  [FAIL] 10 v1 threshold and enforcement mode: running threshold 0.4, mode 'ovs'; tracked default 0.75, 'simulated' -- v1 is not running the tracked configuration (RUN_GUIDE.md section 3)

9 of 10 checks passed; FAILED: ['10 v1 threshold and enforcement mode']
```

That is §3's disagreement, now reported by the verification instead of hidden by
it. It stays failing until `backend/.env` and the tracked default agree.

**A fresh clone**, run on 2026-10-04: the pushed branch cloned to a scratch
folder — no `ML/weights.pt`, no `backend/.env`, no override file — and started
with `docker compose up -d`, reusing the images already built (so this did not
test a fresh *build*).

- the inference service starts and answers `/health` with **503**,
  `model not loaded: [Errno 2] No such file or directory: '/app/ML/weights.pt'`,
  and stays `unhealthy`;
- the backend starts, reports `status: degraded` and the service as unreachable;
  v1 runs at 0.75, `simulated`; the frontend serves;
- **checks 1, 4, 8 and 9 fail; 2, 3, 5, 6, 7 and 10 pass.** `/contract` is served
  from the tracked `model_card.json`, which is why 2, 5 and 6 pass with no weights
  — only check 4 compares the card against the file.

It also found two defects, both fixed: `docker compose up -d` failed outright (§4,
the 75-second window), and `verify_stack.py` crashed with a traceback on the 503
instead of reporting failed checks.

**Reference result**, from the committed `ML/live_rule_check.json` over all 18,264
sample flows:

- all 58 windows echoed the policy digest;
- **12 rules admitted**, every one on a correctly classified flow;
- **0 rules on benign traffic, 0 on a wrong-class prediction**;
- PortScan's 0.85 floor was **never reached** — 0 of 68 correct PortScan
  predictions. PortScan has been `alert_only` since 2026-10-05, so those 68 are
  withheld as `class_suppressed`; the floor itself is unchanged.

If your run differs from those numbers on the same sample, something is wrong with
your setup — start with checks 4 and 8.

**What check 9 is not.** The counts come from the inference service's response
to the committed sample, sent to it directly with the backend's policy. They
verify the loop **from the inference service outward, on that sample**. The
backend's own ingestion path — OVS flow → monitor → provenance gate → v2 client →
rules accepted and logged by the backend — was run once on live flows on
2026-10-05, and there the admitted rules were on benign traffic
(`MODEL_BEHAVIOUR.md` §1.3). Check 9 passing does not mean the rules are right on
a live network. See §7 and §11.

### The test suites

```powershell
cd ML/graphsentinel_v2
python -m pytest tests -q -p no:cacheprovider      # 167 passed

cd ..\..\backend
python -m pytest -q -p no:cacheprovider            # 244 passed, 3 skipped

cd ..\blockchain
npm ci
npx hardhat test                                   # 25 passing
```

The backend suite takes about four minutes here. `backend/requirements.txt` pins
`web3==7.4.0`; check `pip show web3` agrees before quoting the count.

---

## 7. Traffic from Mininet

Linux or WSL2 only. **Run once, on 2026-10-05** (`MODEL_BEHAVIOUR.md` §1.3,
`ML/retrain_logs/live_loop_run.txt`). The longer procedure is `RUNNING.md` Tier 3;
installation is `INSTALLATION_GUIDE.md`; the scenarios are in
`MININET_ATTACK_SCRIPTS.md`.

**What puts per-flow entries in the table.** `ovs-ofctl dump-flows` returns the
flow table, not a list of traffic. The topology starts Mininet's `OVSController`,
which is `ovs-testcontroller`: a reactive learning switch that installs one
exact-match entry per conversation (`nw_src`, `nw_dst`, `tp_src`, `tp_dst`,
`idle_timeout=60`) with the switch in `fail_mode: secure`. Without that controller
the table holds one `NORMAL` rule and the backend sees no flows. The backend never
runs `ovs-ofctl` itself: it asks `backend/scripts/enforcement_daemon.py` over TCP
(`DAEMON_HOST`, `DAEMON_PORT`, `DAEMON_TOKEN`), and the daemon runs
`sudo ovs-ofctl dump-flows <switch>`. The switch must be one of `s1`, `s2`, `s3`
(the daemon's allowlist) and equal `ENFORCEMENT_SWITCH`. The 10.0.0.0/24 range is
required only for v1's block and unblock, not for polling or for v2.

**As run** (WSL2 Ubuntu, as root; the backend and inference service on Windows as
in §5, plus a logging config, below):

```bash
apt-get install -y openvswitch-switch openvswitch-testcontroller mininet hping3 nmap
systemctl stop openvswitch-testcontroller      # Mininet starts its own on 6653
systemctl start openvswitch-switch
python3 mininet/topologies/base_topology_headless.py          # terminal 1
DAEMON_TOKEN=<the backend's> python3 backend/scripts/enforcement_daemon.py   # terminal 2
```

The daemon's `DAEMON_TOKEN` must be the backend's, or every poll fails with
`Unauthorized`. WSL2 forwards `127.0.0.1:50051` to Windows, so the backend needs
no change. To put traffic on the switch, run commands inside a host:
`mnexec -a $(pgrep -f 'mininet:h2$') <command>`.

**The backend prints its own v2 lines by default** since 2026-10-05
(`backend/app/logging_setup.py`): the provenance gate `ADMITTING` a poll and then
`still admitting` once a minute, each window `scored`, each `rule` with the flow
it was made on, and each `withheld … : reason`. Before that they were INFO with no
handler and needed `--log-config`.

**To keep the bytes the parser was given**, start the daemon with
`DAEMON_DUMP_LOG=<file>`: it appends every `dump_flows` answer exactly as it
returns it. That file, not a second `ovs-ofctl` beside the daemon, is the
provenance evidence for a run. It grows without bound; leave it unset otherwise.

**Installed in this machine's Ubuntu WSL distribution** (26.04, kernel
6.18 WSL2): Open vSwitch 3.7.1 with the kernel datapath, Mininet 2.3.0, hping3,
nmap. The run needs about 2 GB of free memory: as root in WSL,
`sync; echo 3 > /proc/sys/vm/drop_caches` first, or the inference service may not
start. Colab was considered as an alternative and not needed.

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
- a closed v2 rule-generation loop, in dry-run: the backend's policy gates every
  rule, digests are echoed, withheld flows are counted with reasons;
- on the committed sample, 12 rules admitted and none wrong.

**Say this out loud.** The dashboard's header carries `BLOCKS: v1 MODEL · v2:
DRY-RUN`, and that is the only place the screen makes the distinction. Hosts
turning red and chain records appearing are v1's work; the audited model's output
is the admitted and withheld counts in §6. Say so when presenting, and in any
figure caption that shows the dashboard.

**Does not show, and must not be claimed:**

- **live mitigation by the audited model.** v2 is `dry_run = True`; no v2 rule
  has reached a switch. That guarantee is v2's alone. The incidents, blocks and
  chain records on the dashboard come from **v1**, which is not dry-run, was never
  measured, and blocks for real when `ENFORCEMENT_MODE=ovs` (§1). §6 verifies v2;
  nothing in this guide verifies v1's detections.
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
| check 10 fails | v1 is not running the tracked threshold or enforcement mode: your `backend/.env` differs from `backend/.env.example` (§3) |
| check 3 or 7 fails, `ml_v2 = {'enabled': False, ...}` | the v2 path is off: the stack was started with `docker-compose.v1.yml` or a local override sets `GS2_ENABLED` to false (§1), or `GS2_ENABLED` is not set (§5). `docker compose config` shows the resolved value |
| check 1 passes but nothing else does, on the manual path | something else is answering on that port (8080 on this machine). Use 8081 |
| inference never becomes healthy | `ML/weights.pt` is missing (it is gitignored); see `INTEGRATION.md` §1 |
| service healthy but no verdicts through the backend | the provenance gate is refusing the batch — check `data_source` in `docker logs graphsentinel-backend` |
| no PortScan rule ever appears | expected. PortScan is `alert_only`: recognised and reported, never turned into a rule (`MODEL_BEHAVIOUR.md` §6). Check the withheld counts before suspecting a bug |
| a test passes elsewhere and fails here | `backend/.env` — see §3 |
| check 4 fails | `ML/weights.pt` and `ML/MANIFEST.json` are out of step; re-unzip the result at the repository root |

---

## 11. Not executed for this guide

- **Mininet and real OVS flows** (§7): run once on 2026-10-05, in WSL2. Not part
  of the ten checks, and not repeated for each revision of this guide.
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
- **The backend's ingestion path, end to end: run once, live, and the result is
  not the one the sample gives.** On 2026-10-05 real OVS flows went through the
  monitor, the provenance gate and the v2 client, and the backend logged its own
  admitted and withheld lines (§7 for how; `MODEL_BEHAVIOUR.md` §1.3 for what).
  The mechanism ran: no poll failed, no batch was refused, no window was unscored.
  The rules it admitted were on benign web fetches, and half the flows of a
  benign-only window were predicted as attacks. So checks 8 and 9, which pass on
  the committed sample, say nothing about live traffic. Three runs of one traffic
  script, on one machine short of memory; the live path has not been measured as
  a rate.

---

## 12. Before a demo

This machine has 3.8 GB of RAM. Preparing this guide on it produced **two flaky
failures** — npm crashing mid-build (`Exit handler never called!`) and Ganache
missing its 30-second start limit — and **two session restarts mid-build**. Docker,
Node, Python, Ganache and a browser do not fit comfortably in 3.8 GB. So, in order
of value:

1. **The recording is the plan; the live run is the bonus.** With Docker up this
   machine had **76 MB** of RAM free, and the working session died under load again on
   2026-10-04. Screen-capture `docker compose up -d` through all ten checks of
   `python ML/verify_stack.py`, with the output legible, on a quiet machine. Save
   it as **`docs/demo/verify_stack_run.mp4`** so it is findable under pressure.
   **That file does not exist yet**; until it does, there is no fallback.
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
