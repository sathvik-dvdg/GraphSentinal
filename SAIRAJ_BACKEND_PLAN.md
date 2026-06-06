# SAIRAJ - BACKEND IMPLEMENTATION PLAN
## GraphSentinel | Role: Backend Engineer
### Scope: FastAPI backend, Mininet monitor, SQLite persistence, self-healing, and integration glue

---

## Current Source Of Truth

This file is Sairaj's complete backend plan. It is aligned with:

- `API_CONTRACTS.md` for REST and Socket.IO payload shapes.
- `backend/NODE_FEATURES.md` for the latest ML graph contract.
- `INTEGRATION_GUIDE.md` for team handoff timing.
- `SUSHEEP_FRONTEND_PLAN.md` for frontend calls that require backend support.
- `SKANDA_BLOCKCHAIN_PLAN.md` for the Web3.py bridge contract.
- `SATHVIK_ML_PLAN.md` for the GraphSAGE model class and exported weights.

Important correction: the latest ML contract uses flow nodes, not IP nodes, inside the PyG graph. The frontend still displays IP nodes, so the backend must aggregate flow-level predictions back to source IPs for `/api/v1/graph`, alerts, stats, timeline, and self-healing.

---

## Paste This Block When Starting An AI IDE Session

```text
You are the backend implementation assistant for GraphSentinel, a
Self-Healing Cyber Defense System using Graph Deep Learning and
Immutable Audit Trails.

YOUR ROLE:
Assist Sairaj, who owns the FastAPI backend, Mininet monitor,
SQLite persistence layer, self-healing engine, Socket.IO events,
and backend integration with Sathvik's ML model and Skanda's
blockchain bridge.

FROZEN CONSTRAINTS:
- Python: 3.10.11 via pyenv in WSL2 Ubuntu 22.04
- FastAPI: 0.115.x
- Uvicorn: 0.35.x
- PyTorch: 2.4.x CPU
- PyTorch Geometric: 2.5.x
- Web3.py: 7.x
- NetworkX: 3.3.x
- Database: SQLite only
- Backend OS: WSL2 only
- Backend port: 0.0.0.0:8000
- Frontend origin: http://localhost:5173
- Blockchain RPC: http://127.0.0.1:8545
- No unvalidated subprocess calls
- No shell=True
- No direct root web server
- Mutating endpoints require an API token, even for local demo mode

SCOPE:
Generate or edit only:
- backend/app/*
- backend/README.md
- backend/requirements.txt
- mininet/topologies/*
- mininet/topologies/attack_scripts/*
- docs or root markdown files only when they describe Sairaj-owned backend contracts

Do not edit:
- frontend implementation files
- blockchain implementation files
- ML training implementation files

BACKEND MUST IMPLEMENT:
- GET  /health
- GET  /api/v1/graph
- GET  /api/v1/stats
- GET  /api/v1/timeline
- GET  /api/v1/alerts
- GET  /api/v1/blocked
- POST /api/v1/block
- GET  /api/v1/forensics
- POST /api/v1/blockchain/store
- POST /api/v1/analyze

SOCKET.IO EVENTS TO EMIT:
- graph_update: every poll cycle, same shape as GET /api/v1/graph
- alert: one AlertRecord whenever a new incident is created
- healing_triggered: one HealingEvent whenever an IP is isolated

ML CONTRACT:
- Import GraphSAGEClassifier from ml/src/model.py.
- Load ml/models/graphsage_weights.pt.
- Build PyG graph with one node per network flow.
- Edge type 1: temporal chain flow[i] -> flow[i+1].
- Edge type 2: same destination-port link from the previous flow with the same dst_port.
- Use exactly 7 node features from backend/NODE_FEATURES.md.
- Apply per-window z-score normalization in graph_builder.py.
- Do not apply scaler.pkl to the 7 node features at inference time.

SECURITY CONTRACT:
- Validate every IP with ipaddress.ip_address before enforcement.
- Enforce Mininet blocks through OVS drop flows, not host INPUT iptables.
- Put privileged OVS operations behind a narrow Enforcement Agent interface.
- The FastAPI process must not run as root.
- Missing ML weights must put the service in degraded mode or fail startup.
- Never report "healthy" while ML is unavailable.
- Add request size checks and rate limiting for /api/v1/analyze.

Always add "# [WSL2]" at the top of each backend Python file.
When asked to scaffold, generate file-by-file with complete code.
When asked to fix a bug, make the smallest correct backend change.
```

---

## Backend Ownership Map

| Area | Sairaj deliverable | Completion criteria |
|------|--------------------|---------------------|
| FastAPI app | `backend/app/main.py` with routers, CORS, lifespan startup, Socket.IO wrapper | `uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload` starts cleanly |
| SQLite | Incident, blocked IP, and raw/current flow persistence | WAL mode enabled, API reads do not lock writes |
| ML inference | Load GraphSAGE weights and run flow-node predictions | `POST /api/v1/analyze` returns real or deterministic fallback scores |
| Graph aggregation | Convert flow predictions into frontend IP graph | `GET /api/v1/graph` matches contract exactly |
| Self-healing | Block/unblock IPs and store state | Manual and automatic blocks update SQLite and emit events |
| Enforcement boundary | OVS blocking through a narrow agent | FastAPI never needs root and every IP is validated |
| Blockchain adapter | Wrap Skanda's `web3_client.py` | `POST /api/v1/blockchain/store` returns confirmed or safe degraded response |
| Mininet monitor | Poll OVS flows every 5 seconds | `graph_update` emits while topology is running |
| Frontend support | Stats and timeline endpoints | Susheep can remove stats/timeline TODOs without adding backend fields |
| Demo reliability | Fallbacks for Mininet, ML, blockchain | Backend still serves mock graph/alerts if one dependency is down |

---

## Repository Layout Sairaj Should Create

```text
backend/
  app/
    __init__.py
    main.py
    config.py
    database.py
    api/
      __init__.py
      v1/
        __init__.py
        analyze.py
        graph.py
        stats.py
        timeline.py
        alerts.py
        blocked.py
        forensics.py
        blockchain.py
    models/
      __init__.py
      incident.py
      schemas.py
    services/
      __init__.py
      graph_builder.py
      inference_service.py
      threat_analyzer.py
      self_healing.py
      enforcement_agent.py
      blockchain_adapter.py
      forensics_service.py
      graph_state.py
      timeline_service.py
    mininet_monitor/
      __init__.py
      flow_parser.py
      monitor.py
    websocket/
      __init__.py
      events.py
  requirements.txt
  .env.example

mininet/
  topologies/
    base_topology.py
    attack_scripts/
      ddos_attack.py
      portscan_attack.py
      ssh_bruteforce_attack.py
      botnet_burst.py
```

---

## API Completion Checklist

| Endpoint | Owner | Required behavior |
|----------|-------|-------------------|
| `GET /health` | Sairaj | Return service, status, dependency summary, timestamp |
| `GET /api/v1/graph` | Sairaj | Return current IP-level graph; if no live flows, return 10-node safe demo graph |
| `GET /api/v1/stats` | Sairaj | Return counts and health metrics for the top stats bar |
| `GET /api/v1/timeline?last=60min` | Sairaj | Return Recharts-ready threat and block counts by time bucket |
| `GET /api/v1/alerts?limit=50&severity=critical` | Sairaj | Return newest incidents first, with optional severity filter |
| `GET /api/v1/blocked` | Sairaj | Return currently blocked IPs from SQLite |
| `POST /api/v1/block` | Sairaj | Manual block/unblock; emit `healing_triggered` for block |
| `GET /api/v1/forensics` | Sairaj + Skanda | Return SQLite incidents plus blockchain records |
| `POST /api/v1/blockchain/store` | Sairaj + Skanda | Store incident on Ganache through Skanda's bridge |
| `POST /api/v1/analyze` | Sairaj | Run inference, persist incidents, trigger healing, return predictions and graph snapshot |

No frontend component should need a backend field outside these contracts.

---

## Environment Setup

```bash
# Windows PowerShell as Admin
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

```bash
# WSL2 Ubuntu 22.04
sudo apt-get update
sudo apt-get install -y \
  build-essential curl git wget \
  libssl-dev libffi-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev \
  openvswitch-switch openvswitch-testcontroller \
  net-tools iproute2 iptables

sudo service openvswitch-switch start
sudo ovs-vsctl show
```

```bash
# pyenv and Python
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

pyenv install 3.10.11
pyenv global 3.10.11
python --version
```

```bash
# Mininet
cd ~
git clone https://github.com/mininet/mininet
cd mininet
git checkout 2.3.1b4
sudo PYTHON=python3 ./util/install.sh -a
sudo mn --test pingall
```

```bash
# Backend virtualenv
cd /mnt/c/Projects/graphsentinel/backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

```bash
# Backend dependencies
pip install fastapi==0.115.6 "uvicorn[standard]==0.35.0"
pip install python-socketio==5.11.0 python-dotenv==1.0.0
pip install sqlalchemy==2.0.* pydantic==2.* pydantic-settings==2.*
pip install networkx==3.3 pandas==2.2.0 numpy==1.26.0 scikit-learn==1.5.0
pip install scapy==2.5.0 web3==7.4.0
pip install torch==2.4.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install torch-geometric==2.5.0
pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.4.0+cpu.html
pip freeze > requirements.txt
```

---

## Backend Environment Variables

```bash
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
SQLITE_PATH=./graphsentinel.db
THREAT_THRESHOLD=0.75
POLL_INTERVAL_SECONDS=5
MAX_ANALYZE_FLOWS=5000
ANALYZE_RATE_LIMIT_PER_MINUTE=30
BACKEND_API_TOKEN=change-me-for-demo

WEIGHTS_PATH=../ml/models/graphsage_weights.pt
MODEL_SOURCE_PATH=../ml/src
NODE_FEATURE_COUNT=7

# Kept only because Sathvik may export it. Do not use for 7-feature inference.
SCALER_PATH=../ml/models/scaler.pkl
USE_SCALER_FOR_INFERENCE=false
REQUIRE_ML_MODEL=true
DEMO_ALLOW_MOCK_ML=false

GANACHE_URL=http://127.0.0.1:8545
CONTRACT_ADDRESS=
BLOCKCHAIN_TX_TIMEOUT_SECONDS=5
ENFORCEMENT_MODE=ovs
ENFORCEMENT_SWITCH=s1
ENFORCEMENT_AGENT_SOCKET=/tmp/graphsentinel-enforcer.sock
```

---

## Data Models

Use these Python shapes in `backend/app/models/schemas.py`.

```python
# [WSL2]
from pydantic import BaseModel, Field
from typing import Literal, Optional

NodeStatus = Literal["normal", "suspicious", "malicious", "blocked"]
AttackType = Literal["DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk"]
Severity = Literal["info", "warning", "critical"]
BlockAction = Literal["block", "unblock"]
BlockReason = Literal["GNN_DETECTED", "MANUAL_OVERRIDE"]

class FlowRecord(BaseModel):
    src_ip: str
    dst_ip: str
    src_port: int = 0
    dst_port: int
    protocol: str = "TCP"
    packet_count: int = 0
    byte_count: int = 0
    duration_sec: float = 1.0
    tcp_flags: int = 0
    fwd_packets: Optional[int] = None
    bwd_packets: Optional[int] = None
    fwd_bytes: Optional[int] = None
    bwd_bytes: Optional[int] = None
    syn_flag_count: Optional[int] = None
    flow_bytes_per_s: Optional[float] = None

class AnalyzeRequest(BaseModel):
    flows: list[FlowRecord]

class NodeData(BaseModel):
    id: str
    label: str
    status: NodeStatus
    threat_score: float = Field(ge=0.0, le=1.0)
    connections: int
    bytes_total: int
    attack_type: Optional[AttackType] = None
    is_blocked: bool

class LinkData(BaseModel):
    source: str
    target: str
    value: float = Field(ge=0.0, le=1.0)
    attack_type: Optional[AttackType] = None
    packet_count: int

class GraphResponse(BaseModel):
    nodes: list[NodeData]
    links: list[LinkData]
    metadata: dict

class AlertRecord(BaseModel):
    id: str
    timestamp: str
    source_ip: str
    attack_type: AttackType
    severity: Severity
    threat_score: float
    description: str
    is_blocked: bool
    blockchain_tx: Optional[str] = None

class StatsResponse(BaseModel):
    total_nodes: int
    active_threats: int
    blocked_ips: int
    system_health: int
    total_packets: int
    total_bytes: int
    last_updated: str

class TimelinePoint(BaseModel):
    time: str
    threats: int
    blocked: int

class TimelineResponse(BaseModel):
    window: str
    bucket_minutes: int
    data_points: list[TimelinePoint]

class BlockRequest(BaseModel):
    ip: str
    reason: BlockReason = "MANUAL_OVERRIDE"
    action: BlockAction = "block"

class BlockResponse(BaseModel):
    status: Literal["blocked", "unblocked"]
    ip: str
    blockchain_tx: Optional[str] = None
```

---

## SQLite Schema

Create SQLAlchemy models in `backend/app/models/incident.py` and initialize them from `backend/app/database.py`.

| Table | Purpose | Required fields |
|-------|---------|-----------------|
| `incidents` | One row per detected threat | id, source_ip, attack_type, threat_score, severity, is_blocked, raw_flow_json, blockchain_tx, created_at |
| `blocked_ips` | Current block state | id, ip_address, reason, attack_type, threat_score, blockchain_tx, blocked_at |
| `flow_snapshots` | Latest monitor window for `/graph` fallback and timeline | id, src_ip, dst_ip, src_port, dst_port, protocol, packet_count, byte_count, duration_sec, tcp_flags, threat_score, captured_at |

Rules:

- Enable WAL mode on startup.
- Store timestamps in UTC.
- Never return SQLAlchemy `_sa_instance_state` fields from endpoints.
- Convert all ORM rows into Pydantic or plain dicts before returning.
- Deleting a block on manual unblock should remove the `blocked_ips` row but keep the historical incident.

---

## ML Graph Builder Contract

Implement `backend/app/services/graph_builder.py` against `backend/NODE_FEATURES.md`.

```python
# [WSL2]
# Flow-node graph, not IP-node graph.

FEATURES = [
    "fwd_ratio",
    "avg_packet_size",
    "connection_rate",
    "port_norm",
    "byte_asymmetry",
    "syn_ratio",
    "bytes_rate_norm",
]
```

Feature formulas:

| Index | Name | Formula |
|-------|------|---------|
| 0 | `fwd_ratio` | `fwd_packets / (fwd_packets + bwd_packets + 1e-6)` |
| 1 | `avg_packet_size` | `(fwd_bytes + bwd_bytes) / (total_packets + 1e-6)` |
| 2 | `connection_rate` | `log1p(total_packets / flow_duration_sec)` |
| 3 | `port_norm` | `dst_port / 65535.0` |
| 4 | `byte_asymmetry` | `(fwd_bytes - bwd_bytes) / (total_bytes + 1e-6)` |
| 5 | `syn_ratio` | `syn_flag_count / (total_packets + 1e-6)`, capped at `1.0` |
| 6 | `bytes_rate_norm` | `log1p(min(flow_bytes_per_s, 3e8)) / log1p(3e8)` |

Edge rules:

- Add temporal edge `i -> i + 1` for consecutive flows.
- Add same-port edge `j -> i` where `j` is the most recent previous flow with the same `dst_port`.
- If there are zero edges, return an empty `edge_index` with shape `(2, 0)`.

Normalization:

```python
mean = x.mean(dim=0, keepdim=True)
std = x.std(dim=0, keepdim=True)
std = torch.where(std < 1e-6, torch.ones_like(std), std)
x = (x - mean) / std
```

Fallback mapping from OVS stats:

```python
fwd_packets = flow.fwd_packets or flow.packet_count
bwd_packets = flow.bwd_packets or 0
fwd_bytes = flow.fwd_bytes or flow.byte_count
bwd_bytes = flow.bwd_bytes or 0
syn_flag_count = flow.syn_flag_count if flow.syn_flag_count is not None else int(bool(flow.tcp_flags & 2))
flow_bytes_per_s = flow.flow_bytes_per_s or (flow.byte_count / max(flow.duration_sec, 0.001))
```

Attach these helper arrays to the returned PyG `Data` object:

```python
data.flow_sources = [flow.src_ip for flow in flows]
data.flow_destinations = [flow.dst_ip for flow in flows]
data.flow_records = [flow.model_dump() for flow in flows]
```

---

## Inference Service

Implement `backend/app/services/inference_service.py` as a singleton.

Required behavior:

- Add `MODEL_SOURCE_PATH` to `sys.path`.
- Import `GraphSAGEClassifier` from `model.py`.
- Construct it as `GraphSAGEClassifier(in_channels=7, hidden_channels=256, out_channels=2, num_layers=3)`.
- Load `WEIGHTS_PATH` if it exists.
- If weights are missing and `REQUIRE_ML_MODEL=true`, fail startup with a clear error.
- If weights are missing and `DEMO_ALLOW_MOCK_ML=true`, enter degraded mode with deterministic heuristic scores and expose that state through `/health`.
- Do not apply `scaler.pkl` to the seven inference features.
- Prefer `model.predict_proba(x, edge_index)` if Sathvik's class exposes it.
- Otherwise use `softmax(model(x, edge_index), dim=1)[:, 1]`.
- Set an explicit CPU threading policy, for example `torch.set_num_threads(min(4, os.cpu_count() or 1))`, so inference does not starve Mininet.

Return both prediction levels:

```python
{
  "flow_scores": [
    {"flow_index": 0, "src_ip": "10.0.0.2", "dst_ip": "10.0.0.1", "score": 0.94}
  ],
  "ip_scores": {
    "10.0.0.2": 0.94,
    "10.0.0.1": 0.08
  }
}
```

Aggregation rule for `ip_scores`:

- Source IP score is the max score of outbound flows from that IP.
- Destination IP score is included with the max inbound score, but never let passive victim traffic create an automatic block unless the source score is also high.
- For demo stability, known attacker scripts can boost expected attack source IPs only when `DEMO_ALLOW_MOCK_ML=true`; the health response must still say `degraded`.

Health state rules:

| ML state | `/health.status` | Frontend meaning |
|----------|------------------|------------------|
| weights loaded | `ok` | Real detection active |
| mock ML explicitly allowed | `degraded` | Demo fallback active, not production detection |
| weights missing and required | startup fails | Fix weights before running |

---

## Threat Analyzer, Idempotency, And Self-Healing

Implement `backend/app/services/threat_analyzer.py`.

Responsibilities:

- Convert `ip_scores` into status labels:
  - `< 0.50`: `normal`
  - `0.50 - 0.749`: `suspicious`
  - `>= THREAT_THRESHOLD`: `malicious`
  - blocked IP in SQLite: `blocked`
- Create one incident per source IP crossing threshold.
- Deduplicate repeated incidents from the same IP within a short cooldown window, for example 15 seconds.
- Derive attack type using flow evidence first:
  - many packets to one target: `DDoS`
  - many destination ports: `PortScan`
  - repeated destination port 22: `SSHBrute`
  - repeated low-volume bursts from multiple sources: `Botnet`
  - HTTP-heavy burst: `DoSHulk`
- Trigger self-healing for malicious source IPs only.
- Call blockchain storage after SQLite commit.
- Update the incident row with the returned `tx_hash`.
- Generate an idempotency key for each incident using source IP, attack type, rounded score bucket, and time bucket.
- Never create duplicate blocks for the same IP if a block already exists.
- Keep the canonical current block state in SQLite, the immutable audit history on blockchain, and the physical enforcement state in OVS.

Implement `backend/app/services/self_healing.py`.

Rules:

- `block_ip(ip, reason, attack_type, threat_score)` inserts or updates `blocked_ips`.
- Validate `ip` with `ipaddress.ip_address(ip)` before doing anything else.
- Reject loopback, multicast, broadcast, unspecified, and non-Mininet IPs unless explicitly allowed for tests.
- Do not build shell strings.
- Do not use `shell=True`.
- Do not run FastAPI as root.
- For Mininet, enforce with OVS drop flows, not host INPUT iptables:
  - `sudo ovs-ofctl add-flow s1 priority=1000,ip,nw_src=<ip>,actions=drop`
  - `sudo ovs-ofctl del-flows s1 ip,nw_src=<ip>`
- Prefer a dedicated enforcement agent with the narrow privilege to call `ovs-ofctl`.
- If the agent is down, record the requested block as `pending_enforcement` and make `/health` return `degraded`.
- `unblock_ip(ip)` removes OVS drop flows and deletes the `blocked_ips` row.
- All block actions emit `healing_triggered` with the frozen payload shape.

Implement `backend/app/services/enforcement_agent.py`.

Agent contract:

```python
# [WSL2]
from ipaddress import ip_address, ip_network
import subprocess

MININET_NET = ip_network("10.0.0.0/24")

def validate_mininet_ip(value: str) -> str:
    parsed = ip_address(value)
    if parsed not in MININET_NET:
        raise ValueError("IP is outside Mininet demo subnet")
    if parsed.is_multicast or parsed.is_loopback or parsed.is_unspecified:
        raise ValueError("IP is not enforceable")
    return str(parsed)

def ovs_block(ip: str, switch: str = "s1") -> None:
    clean_ip = validate_mininet_ip(ip)
    subprocess.run(
        ["sudo", "ovs-ofctl", "add-flow", switch, f"priority=1000,ip,nw_src={clean_ip},actions=drop"],
        check=True,
        timeout=3,
    )

def ovs_unblock(ip: str, switch: str = "s1") -> None:
    clean_ip = validate_mininet_ip(ip)
    subprocess.run(
        ["sudo", "ovs-ofctl", "del-flows", switch, f"ip,nw_src={clean_ip}"],
        check=True,
        timeout=3,
    )
```

Production boundary:

- FastAPI should call a Unix socket or local pipe exposed by the agent.
- The agent can be granted limited sudo rights for only `ovs-ofctl add-flow` and `ovs-ofctl del-flows`.
- For the project demo, direct subprocess calls are acceptable only inside this agent module and only with validated IPs and list arguments.

Reconciliation:

- Every 10 seconds, compare `blocked_ips` rows with `ovs-ofctl dump-flows s1`.
- If SQLite says blocked but OVS rule is missing, reapply the rule and log `reconciled`.
- If OVS has a GraphSentinel drop rule with no SQLite row, remove it.
- Expose reconciliation failures in `/health`.

---

## Current Graph, Stats, And Timeline

Implement `backend/app/services/graph_state.py`.

Responsibilities:

- Keep the latest flow window in memory.
- Persist flow snapshots to SQLite for fallback and timeline.
- Build frontend IP graph from flows and `ip_scores`.
- Include all 10 Mininet hosts, even if a host has no current edges.
- Aggregate links by `(src_ip, dst_ip)`.
- Calculate `connections`, `bytes_total`, `packet_count`, and `metadata.last_updated`.

Implement `backend/app/services/timeline_service.py`.

Stats response:

```json
{
  "total_nodes": 10,
  "active_threats": 2,
  "blocked_ips": 1,
  "system_health": 86,
  "total_packets": 15230,
  "total_bytes": 5129000,
  "last_updated": "2026-06-06T16:30:00Z"
}
```

Timeline response:

```json
{
  "window": "60min",
  "bucket_minutes": 5,
  "data_points": [
    { "time": "14:25", "threats": 0, "blocked": 0 },
    { "time": "14:30", "threats": 2, "blocked": 1 }
  ]
}
```

System health formula for demo:

```text
system_health = max(0, 100 - active_threats * 12 - blocked_ips * 4)
```

---

## Router File Requirements

### `app/api/v1/analyze.py`

- Accept `AnalyzeRequest`.
- Reject requests with more than `MAX_ANALYZE_FLOWS`.
- Reject NaN, negative packet counts, negative byte counts, and zero/negative durations before graph construction.
- Apply a per-client rate limit using middleware or a lightweight in-memory limiter.
- Call `InferenceService.predict(flows)`.
- Call `ThreatAnalyzer.evaluate(...)`.
- Store latest graph state.
- Return:
  - `predictions`
  - `flow_scores`
  - `incidents_created`
  - `healing_triggered`
  - `graph_snapshot`

### `app/api/v1/graph.py`

- Return current `GraphResponse`.
- If no flow state exists, return a safe 10-host graph with all nodes normal.
- Must not trigger inference by itself; it is a read endpoint.

### `app/api/v1/stats.py`

- Return `StatsResponse` derived from current graph, incidents, and blocked IPs.
- This completes Susheep's `StatsBar` backend TODO.

### `app/api/v1/timeline.py`

- Accept `last`, default `60min`.
- Return 5-minute buckets for a 60-minute window.
- This completes Susheep's `ThreatTimeline` backend TODO.

### `app/api/v1/alerts.py`

- Accept `limit` and optional `severity`.
- Convert integer DB severity to `info`, `warning`, or `critical`.
- Sort newest first.

### `app/api/v1/blocked.py`

- Return `{ "blocked_ips": [...], "count": N }`.

### `app/api/v1/block.py`

- Accept `BlockRequest`.
- Require `BACKEND_API_TOKEN`.
- Validate the IP before calling the self-healing service.
- For `action=block`, call `SelfHealingEngine.block_ip`.
- For `action=unblock`, call `SelfHealingEngine.unblock_ip`.
- Return `BlockResponse`.

### `app/api/v1/forensics.py`

- Return SQLite incidents plus blockchain records.
- If blockchain is down, return SQLite records and an empty `blockchain_records` list.
- Include `chain_id` and `contract_address` when available.

### `app/api/v1/blockchain.py`

- Wrap `BlockchainAdapter.store_incident`.
- Use a timeout so Ganache cannot block the Mininet monitor thread indefinitely.
- Record failed or timed-out blockchain writes in SQLite for retry.
- Do not expose private keys or raw Web3 internals.
- Return safe error JSON if Ganache is offline.

---

## Main App Requirements

`backend/app/main.py` must:

- Create `socketio.AsyncServer(async_mode="asgi")`.
- Allow origins `http://localhost:5173` and `http://localhost:3000`.
- Initialize SQLite in lifespan startup.
- Load inference service in startup.
- Crash if weights are missing and `REQUIRE_ML_MODEL=true`.
- Enter explicit degraded mode if `DEMO_ALLOW_MOCK_ML=true`.
- Connect blockchain adapter in startup, but do not crash if Ganache is offline.
- Start `MininetMonitor` in a background thread.
- Install API-token auth for mutating endpoints.
- Install request-size and rate-limit middleware for `/api/v1/analyze`.
- Register routers:
  - `analyze`
  - `graph`
  - `stats`
  - `timeline`
  - `alerts`
  - `blocked`
  - `forensics`
  - `blockchain`
- Expose `socket_app = socketio.ASGIApp(sio, app)`.

Run command:

```bash
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

---

## Mininet Monitor Requirements

`backend/app/mininet_monitor/monitor.py`:

- Poll `parse_ovs_flows("s1")` every `POLL_INTERVAL_SECONDS`.
- If flows exist, call the same service path used by `POST /api/v1/analyze`.
- Emit `graph_update`.
- Emit `alert` for each new incident.
- Emit `healing_triggered` for each block event.
- Log failures without killing the thread.
- Never wait indefinitely for blockchain or enforcement calls.

`backend/app/mininet_monitor/flow_parser.py`:

- Run `sudo ovs-ofctl dump-flows s1`.
- Parse IPv4 TCP and UDP flows.
- Fill `FlowRecord` fields.
- Avoid crashing on unsupported OVS lines.
- If OVS parsing returns no flows, optionally return a safe demo flow window only when `DEMO_FALLBACK_FLOWS=true`.

---

## Week-By-Week Backend Breakdown

| Week | Focus | Done when |
|------|-------|-----------|
| W1 | WSL2, Python, Mininet, virtualenv | `sudo mn --test pingall` passes and FastAPI can start |
| W2 | FastAPI skeleton, SQLite, routers | All endpoints return mock contract-shaped JSON |
| W3 | Flow parser, graph state, `/graph`, `/stats`, `/timeline` | Frontend can replace all initial mock API reads |
| W4 | Flow-node `graph_builder.py` and fallback inference | `/analyze` returns flow_scores and ip_scores |
| W5 | Self-healing and WebSocket events | Attack creates alert, block, graph update, healing event |
| W6 | Skanda Web3 bridge integration and reconciliation | Blockchain store returns tx hash or degraded safe response; OVS state reconciles with SQLite |
| W7 | Sathvik weights integration | Real weights load and inference smoke test passes |
| W8 | Demo hardening | Full startup script works twice in a row without manual fixes |

---

## Handoff Checks

### Skanda To Sairaj

Required files:

```text
blockchain/web3_bridge/web3_client.py
blockchain/web3_bridge/contract_abi.json
backend/.env with CONTRACT_ADDRESS and GANACHE_URL
```

Sairaj verification:

```bash
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
python - << 'PY'
from app.services.blockchain_adapter import BlockchainAdapter
adapter = BlockchainAdapter.get_instance()
result = adapter.store_incident("10.0.0.9", "PortScan", 7, False, 99)
print(result)
assert result["status"] in {"confirmed", "mock", "error"}
PY
```

### Sathvik To Sairaj

Required files:

```text
ml/models/graphsage_weights.pt
ml/src/model.py
backend/NODE_FEATURES.md
ml/models/scaler.pkl optional, preprocessing-only
```

Sairaj verification:

```bash
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
python - << 'PY'
from app.services.graph_builder import build_pyg_graph
from app.services.inference_service import InferenceService

flows = [
    {
        "src_ip": "10.0.0.2", "dst_ip": "10.0.0.1",
        "src_port": 54321, "dst_port": 80, "protocol": "TCP",
        "packet_count": 15000, "byte_count": 5120000,
        "duration_sec": 3.5, "tcp_flags": 2
    },
    {
        "src_ip": "10.0.0.2", "dst_ip": "10.0.0.3",
        "src_port": 54322, "dst_port": 22, "protocol": "TCP",
        "packet_count": 600, "byte_count": 120000,
        "duration_sec": 2.0, "tcp_flags": 2
    }
]
data = build_pyg_graph(flows)
assert data.x.shape[1] == 7
result = InferenceService.get_instance().predict(flows)
assert "ip_scores" in result
print(result)
PY
```

### Sairaj To Susheep

Sairaj must verify:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/graph
curl -s http://localhost:8000/api/v1/stats
curl -s "http://localhost:8000/api/v1/timeline?last=60min"
curl -s http://localhost:8000/api/v1/alerts
curl -s http://localhost:8000/api/v1/blocked
```

Then tell Susheep:

```text
Backend is ready at http://localhost:8000.
GET /api/v1/graph, /stats, /timeline, /alerts, /blocked, and /forensics are live.
Socket.IO emits graph_update, alert, and healing_triggered.
Set VITE_USE_MOCK=false and start the frontend.
```

---

## Full Startup Sequence

```bash
# Step 1 - Windows Terminal: Ganache
cd C:\Projects\graphsentinel\blockchain
npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data
```

```bash
# Step 2 - Windows Terminal: deploy contract
cd C:\Projects\graphsentinel\blockchain
npx hardhat run scripts/deploy.js --network localhost
```

```bash
# Step 3 - WSL2 Terminal: backend
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Step 4 - WSL2 Terminal: Mininet
cd /mnt/c/Projects/graphsentinel
sudo python3 mininet/topologies/base_topology.py
```

```bash
# Step 5 - Windows Terminal: frontend
cd C:\Projects\graphsentinel\frontend
npm run dev
```

```bash
# Step 6 - WSL2 Terminal: attack script
cd /mnt/c/Projects/graphsentinel
sudo python3 mininet/topologies/attack_scripts/ddos_attack.py
```

---

## Backend Smoke Test Script

```bash
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate

curl -s http://localhost:8000/health | python -m json.tool
curl -s http://localhost:8000/api/v1/graph | python -m json.tool
curl -s http://localhost:8000/api/v1/stats | python -m json.tool
curl -s "http://localhost:8000/api/v1/timeline?last=60min" | python -m json.tool
curl -s http://localhost:8000/api/v1/alerts | python -m json.tool
curl -s http://localhost:8000/api/v1/blocked | python -m json.tool

curl -s -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BACKEND_API_TOKEN" \
  -d '{
    "flows": [
      {
        "src_ip": "10.0.0.2",
        "dst_ip": "10.0.0.1",
        "src_port": 54321,
        "dst_port": 80,
        "protocol": "TCP",
        "packet_count": 15000,
        "byte_count": 5120000,
        "duration_sec": 3.5,
        "tcp_flags": 2
      }
    ]
  }' | python -m json.tool
```

---

## Failure Triage

| Symptom | Check | Fix |
|---------|-------|-----|
| `uvicorn` starts but Socket.IO fails | command uses `app.main:socket_app` | Restart with `socket_app`, not `app` |
| Frontend CORS error | `allow_origins` includes `http://localhost:5173` | Update CORS and restart backend |
| `/graph` empty | Mininet not running or no OVS flows | Return safe 10-node fallback, then debug `sudo ovs-ofctl dump-flows s1` |
| `/stats` missing | Router not included | Add `stats.router` in `main.py` |
| `/timeline` missing | Router not included | Add `timeline.router` in `main.py` |
| ML weights missing | `WEIGHTS_PATH` wrong or file absent | Fail startup unless `DEMO_ALLOW_MOCK_ML=true`; never report healthy |
| Model shape error | graph_builder features not `(N, 7)` | Re-check `backend/NODE_FEATURES.md` exactly |
| Blockchain offline | Ganache not running or contract address stale | Start Ganache, redeploy, restart backend |
| OVS block fails | Agent down, sudo denied, or switch missing | Mark pending enforcement, return degraded health, reconcile later |

---

## Security And Resilience Tests

Sairaj must add these before demo week:

| Test | Why it matters |
|------|----------------|
| Manual block rejects `10.0.0.1; rm -rf /` | Proves command injection is blocked before subprocess |
| Manual block rejects IP outside `10.0.0.0/24` | Prevents accidental host/network blocking |
| `/api/v1/analyze` rejects more than `MAX_ANALYZE_FLOWS` | Prevents CPU denial of service |
| Graph builder rejects NaN and negative flow values | Prevents NaN threat scores |
| ML weights missing with `REQUIRE_ML_MODEL=true` fails startup | Prevents silent fake security |
| ML weights missing with `DEMO_ALLOW_MOCK_ML=true` returns health `degraded` | Makes fallback honest |
| Ganache timeout does not block monitor loop | Keeps graph updates alive |
| SQLite blocked rows reconcile with OVS drop flows | Fixes crash-between-steps inconsistency |
| On-chain `sqlite_incident_id` maps to an existing SQLite row | Preserves forensic integrity |

---

## Final Definition Of Done For Sairaj

- Backend starts from WSL2 with one command.
- All Sairaj-owned endpoints return contract-shaped JSON.
- `/api/v1/graph`, `/api/v1/stats`, and `/api/v1/timeline` are ready for Susheep.
- `graph_builder.py` follows the flow-node feature contract in `backend/NODE_FEATURES.md`.
- Real GraphSAGE weights load when required; deterministic fallback is allowed only in explicit degraded demo mode.
- Alerts are persisted in SQLite.
- Blocked IPs persist in SQLite and can be manually unblocked.
- OVS enforcement validates IPs and does not require the FastAPI process to run as root.
- Reconciliation keeps SQLite block state and OVS drop flows aligned.
- `graph_update`, `alert`, and `healing_triggered` events emit correctly.
- Blockchain writes use Skanda's bridge and degrade safely when Ganache is offline.
- Demo can run with Mininet live, and can still present using fallback graph data if Mininet fails.
