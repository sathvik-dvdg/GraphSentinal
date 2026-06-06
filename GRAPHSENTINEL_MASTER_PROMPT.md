# 🛡️ GRAPHSENTINEL — GOD-TIER MASTER IMPLEMENTATION PROMPT
> **Project:** GraphSentinel: A Self-Healing Cyber Defense System using Graph Deep Learning and Immutable Audit Trails  
> **Team:** Sairaj (Backend) · Susheep (Frontend) · Skanda (Blockchain) · Sathvik (ML)  
> **Demo:** 60-minute working dynamic demo | **OS:** Windows 11 + WSL2 Ubuntu 22.04 | **Scope:** Local machine only

---

## ⚙️ SECTION 0 — AI IDE MASTER INSTRUCTIONS
### Paste this block verbatim when starting any session in AntGravity / Claude Code / Codex:

```
SYSTEM CONTEXT: You are the implementation advisor for GraphSentinel.
This document is the single source of truth for a 4-person team building
a Self-Healing Cyber Defense System using Graph Deep Learning and Blockchain.

YOUR TASKS:
1. Read this entire document before generating anything.
2. When asked to scaffold, generate the complete folder tree under the
   project root (Windows path: C:\Projects\graphsentinel\).
3. Generate per-member plans as separate markdown files:
   - docs/SAIRAJ_BACKEND_PLAN.md
   - docs/SUSHEEP_FRONTEND_PLAN.md
   - docs/SKANDA_BLOCKCHAIN_PLAN.md
   - docs/SATHVIK_ML_PLAN.md
4. NEVER assign overlapping responsibilities between team members.
5. Use EXACT library versions from the Dependency Matrix in Section 2.
6. All frontend dummy data must have: // TODO: REPLACE WITH API CALL comments.
7. NEVER suggest paid/cloud blockchain — local Ganache ONLY (no Infura, no Alchemy).
8. ML training lives exclusively on Google Colab. Export goes to ml/models/.
9. Backend/Blockchain code is WSL2-compatible. Frontend runs on Windows native.
10. Every code block must state which OS it runs on: [WSL2] or [Windows].
11. Follow frozen API contracts — no member changes endpoints unilaterally.
12. For any 3D visualization, both react-force-graph-3d AND @react-three/fiber
    are available; frontend dev decides per component.

DO NOT: generate Docker configs, cloud deploy scripts, or paid tool references.
DO NOT: use Python 3.11+ or 3.9-. Strictly 3.10.11 via pyenv.
```

---

## 📋 SECTION 1 — PROJECT METADATA (FROZEN — DO NOT CHANGE)

| Field | Value |
|-------|-------|
| Project Name | GraphSentinel |
| Architecture | Modular Monolith (FastAPI) |
| Backend Member | **Sairaj** |
| Frontend Member | **Susheep** |
| Blockchain Member | **Skanda** |
| ML Member | **Sathvik** |
| Demo Duration | 60 minutes (live, dynamic, working system) |
| Primary OS | Windows 11 (host) |
| Secondary OS | WSL2 Ubuntu 22.04 (for backend, blockchain, mininet) |
| Repo Structure | Plain Monorepo (no Turborepo/Nx) |
| Python Package Mgr | pip (pyenv-managed, version 3.10.11) |
| Frontend Package Mgr | npm |
| Blockchain Package Mgr | npm (Hardhat) |
| Database | SQLite (built-in, no server) |
| Blockchain | Ganache local + Hardhat + Solidity 0.8.19 + Web3.py 7.x |
| ML Training | Google Colab (T4/A100 GPU) |
| ML Dataset | CICIDS2017 — Tuesday + Wednesday + Friday CSVs only |
| 5 Attack Classes | DDoS, PortScan, Botnet, SSH-Patator, DoS Hulk |
| AI IDEs | AntGravity, Claude Code, Codex |
| Deployment | LOCAL ONLY — no cloud, no Docker for demo |

---

## 🔢 SECTION 2 — FROZEN DEPENDENCY VERSION MATRIX

### Backend / ML (Python — WSL2)
| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.10.11 | Via pyenv STRICTLY |
| FastAPI | 0.115.x | Core API framework |
| Uvicorn | 0.35.x | ASGI server |
| PyTorch | 2.4.x | CPU build for inference |
| PyTorch Geometric | 2.5.x | Must match torch 2.4.x |
| torch-scatter | Matching PyG | Install from PyG wheel |
| torch-sparse | Matching PyG | Install from PyG wheel |
| NetworkX | 3.3.x | Graph manipulation |
| Scikit-learn | 1.5.x | Preprocessing, scaler |
| Pandas | 2.2.x | Data wrangling |
| NumPy | 1.26.x | Array ops |
| Web3.py | 7.x | Blockchain adapter |
| SQLite | built-in | No install needed |
| python-socketio | 5.x | WebSocket events |
| Scapy | 2.5.x | Packet capture |
| Stable-Baselines3 | 2.3.x | RL agent (optional Phase 2) |

### Frontend (JavaScript — Windows)
| Package | Version | Notes |
|---------|---------|-------|
| React | 18.x | UI framework |
| React DOM | 18.x | DOM rendering |
| Vite | 5.x | Build tool (use over CRA) |
| Cytoscape.js | 3.28.x | 2D network graph |
| react-cytoscapejs | 2.x | React wrapper |
| react-force-graph-3d | 1.x | 3D graph — THREE.js backed |
| @react-three/fiber | 8.x | Custom 3D components |
| @react-three/drei | 9.x | R3F helpers/controls |
| three | 0.167.x | THREE.js core |
| socket.io-client | 4.x | Real-time WebSocket |
| axios | 1.7.x | REST API calls |
| recharts | 2.x | Line/bar charts |
| lucide-react | 0.383.x | Icons |
| tailwindcss | 3.x | Styling |
| framer-motion | 11.x | Animations |

### Blockchain (Hardhat — Windows or WSL2)
| Package | Version | Notes |
|---------|---------|-------|
| hardhat | 2.22.x | Smart contract tooling |
| @nomicfoundation/hardhat-toolbox | 5.x | All-in-one toolbox |
| ganache | 7.9.x | Local EVM blockchain |
| solidity | 0.8.19 | Smart contract language |
| Web3.py | 7.x | Python integration |
| ethers | 6.x | Frontend blockchain calls |

---

## 🏗️ SECTION 3 — FROZEN SYSTEM ARCHITECTURE

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    GRAPHSENTINEL — FULL SYSTEM FLOW                    ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  [WSL2 — Ubuntu 22.04]              [Windows 11 — Native]              ║
║  ┌─────────────────────┐            ┌─────────────────────────────┐    ║
║  │  Mininet Topology   │            │   Susheep — React Dashboard │    ║
║  │  (10 virtual hosts) │            │   Port: 5173 (Vite)         │    ║
║  │  Attack simulation  │            │                             │    ║
║  └────────┬────────────┘            │  ┌──────────────────────┐  │    ║
║           │ flow data (JSON)        │  │  3D Network Graph    │  │    ║
║  ┌────────▼────────────┐            │  │  (react-force-3d/R3F)│  │    ║
║  │  Sairaj — FastAPI   │◄──────────►│  └──────────────────────┘  │    ║
║  │  Port: 8000         │  REST API  │  ┌──────────────────────┐  │    ║
║  │                     │  WebSocket │  │  Alerts + Forensics  │  │    ║
║  │  Modules:           │            │  │  Panel               │  │    ║
║  │  • Mininet monitor  │            │  └──────────────────────┘  │    ║
║  │  • Graph builder    │            │  ┌──────────────────────┐  │    ║
║  │  • GNN inference    │            │  │  Blockchain Ledger   │  │    ║
║  │  • Threat analyzer  │            │  │  Visualization       │  │    ║
║  │  • Self-heal engine │            │  └──────────────────────┘  │    ║
║  │  • Blockchain adptr │            └─────────────────────────────┘    ║
║  │  • SQLite logger    │                                               ║
║  └────────┬────────────┘                                               ║
║           │ Web3.py (HTTP)          [Windows or WSL2]                  ║
║  ┌────────▼────────────┐            ┌─────────────────────────────┐    ║
║  │  Skanda — Ganache   │            │  Skanda — Hardhat Compile   │    ║
║  │  Port: 8545         │            │  IncidentLogger.sol          │    ║
║  │  Local EVM chain    │            │  deployed → Ganache          │    ║
║  └─────────────────────┘            └─────────────────────────────┘    ║
║                                                                          ║
║  [Google Colab — Remote]                                                ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │  Sathvik — CICIDS2017 → GraphSAGE Training → weights.pt export  │  ║
║  │  Exports: ml/models/graphsage_weights.pt + ml/models/scaler.pkl │  ║
║  │  Backend loads these files at startup via WEIGHTS_PATH env var  │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════╝

DATA FLOW:
Mininet (WSL2) → Traffic JSON → Graph Builder → GNN Inference → 
Threat Score → [SQLite log] + [Self-Healing] + [Blockchain hash] → 
WebSocket push → React Dashboard (Windows)
```

---

## 📁 SECTION 4 — MONOREPO STRUCTURE + CONNECTION GUIDE

### 4.1 Full Folder Tree

```
C:\Projects\graphsentinel\            ← Git repo root (Windows host)
│
├── backend/                          ← SAIRAJ owns this
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   ← FastAPI entry point
│   │   ├── config.py                 ← Settings + env vars
│   │   ├── database.py               ← SQLite setup
│   │   ├── models/
│   │   │   ├── incident.py           ← SQLite ORM models
│   │   │   └── schemas.py            ← Pydantic request/response schemas
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── analyze.py        ← POST /api/v1/analyze
│   │   │   │   ├── alerts.py         ← GET /api/v1/alerts
│   │   │   │   ├── blocked.py        ← GET/POST /api/v1/blocked
│   │   │   │   ├── forensics.py      ← GET /api/v1/forensics
│   │   │   │   └── blockchain.py     ← POST /api/v1/blockchain/store
│   │   ├── services/
│   │   │   ├── inference_service.py  ← Loads weights.pt + scaler.pkl
│   │   │   ├── graph_builder.py      ← NetworkX → PyG Data object
│   │   │   ├── threat_analyzer.py    ← Threshold + confidence scoring
│   │   │   ├── self_healing.py       ← Block/unblock IP via Mininet
│   │   │   ├── blockchain_adapter.py ← Web3.py → Ganache calls
│   │   │   └── forensics_service.py  ← Report generation
│   │   ├── mininet_monitor/
│   │   │   ├── monitor.py            ← Polls Mininet every 5s
│   │   │   └── flow_parser.py        ← Converts raw flows to JSON
│   │   └── websocket/
│   │       └── events.py             ← Socket.IO event handlers
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/                         ← SUSHEEP owns this
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── NetworkGraph3D/       ← react-force-graph-3d component
│   │   │   │   ├── NetworkGraph3D.jsx
│   │   │   │   ├── NodeObject.jsx    ← Custom 3D node renderer (R3F)
│   │   │   │   └── LinkParticle.jsx  ← Traffic flow particles
│   │   │   ├── NetworkGraph2D/       ← Cytoscape.js fallback
│   │   │   │   └── NetworkGraph2D.jsx
│   │   │   ├── AlertPanel/
│   │   │   │   ├── AlertPanel.jsx
│   │   │   │   └── AlertCard.jsx
│   │   │   ├── BlockchainLedger/
│   │   │   │   ├── BlockchainPanel.jsx
│   │   │   │   └── TxHashCard.jsx
│   │   │   ├── SelfHealingStatus/
│   │   │   │   └── SelfHealStatus.jsx
│   │   │   ├── ThreatTimeline/
│   │   │   │   └── ThreatTimeline.jsx
│   │   │   ├── StatsBar/
│   │   │   │   └── StatsBar.jsx
│   │   │   └── ForensicsReport/
│   │   │       └── ForensicsModal.jsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js       ← Socket.IO real-time hook
│   │   │   ├── useGraphData.js       ← Graph state management
│   │   │   └── useAlerts.js          ← Alerts + incidents
│   │   ├── services/
│   │   │   ├── api.js                ← Axios REST calls to backend
│   │   │   └── mockData.js           ← ALL DUMMY DATA LIVES HERE
│   │   ├── store/
│   │   │   └── graphStore.js         ← Zustand/Context state
│   │   ├── constants/
│   │   │   └── nodeColors.js         ← Color scheme for node status
│   │   └── styles/
│   │       └── globals.css
│   ├── public/
│   ├── package.json
│   ├── vite.config.js                ← Proxy: /api → localhost:8000
│   ├── tailwind.config.js
│   └── .env
│
├── ml/                               ← SATHVIK owns this
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_preprocessing.ipynb
│   │   ├── 03_graph_construction.ipynb
│   │   ├── 04_graphsage_training.ipynb
│   │   └── 05_evaluation_export.ipynb
│   ├── src/
│   │   ├── preprocess.py             ← Reusable preprocessing functions
│   │   ├── graph_utils.py            ← Flow → PyG graph converter
│   │   ├── model.py                  ← GraphSAGE class definition
│   │   └── evaluate.py               ← Metrics + confusion matrix
│   ├── models/                       ← GITIGNORED — large files
│   │   ├── graphsage_weights.pt      ← Exported by Sathvik
│   │   └── scaler.pkl                ← StandardScaler export
│   ├── requirements_colab.txt
│   └── README.md
│
├── blockchain/                       ← SKANDA owns this
│   ├── contracts/
│   │   └── IncidentLogger.sol        ← Main smart contract
│   ├── scripts/
│   │   ├── deploy.js                 ← Hardhat deploy to Ganache
│   │   └── verify.js                 ← Contract verification
│   ├── test/
│   │   └── IncidentLogger.test.js
│   ├── artifacts/                    ← Compiled ABI (auto-generated)
│   ├── web3_bridge/
│   │   ├── web3_client.py            ← Python Web3.py class (used by backend)
│   │   └── contract_abi.json         ← Copied from artifacts after compile
│   ├── hardhat.config.js
│   ├── package.json
│   └── .env                          ← GANACHE_URL, CONTRACT_ADDRESS
│
├── mininet/                          ← SAIRAJ owns this
│   ├── topologies/
│   │   ├── base_topology.py          ← 10-node star topology
│   │   └── attack_scripts/
│   │       ├── ddos_attack.py
│   │       ├── portscan_attack.py
│   │       ├── botnet_sim.py
│   │       ├── ssh_brute.py
│   │       └── dos_hulk.py
│   └── README.md
│
├── docs/                             ← SHARED docs
│   ├── API_CONTRACTS.md              ← FROZEN — all members read this
│   ├── DATA_SCHEMAS.md               ← JSON schema for all shared data
│   ├── INTEGRATION_GUIDE.md
│   ├── SAIRAJ_BACKEND_PLAN.md
│   ├── SUSHEEP_FRONTEND_PLAN.md
│   ├── SKANDA_BLOCKCHAIN_PLAN.md
│   └── SATHVIK_ML_PLAN.md
│
├── datasets/                         ← GITIGNORED (local only)
│   ├── .gitkeep
│   └── cicids2017/                   ← CSV files go here
│
├── .gitignore
├── .env.shared.example               ← Shared env var template
└── README.md
```

### 4.2 How the Monorepo Connects (Critical Integration Points)

```
CONNECTION MATRIX:

Sathvik (ML) ──exports──► ml/models/graphsage_weights.pt
                           ml/models/scaler.pkl
                                │
                                ▼
Sairaj (Backend) ──loads──► backend/app/services/inference_service.py
         │
         ├─── REST API ────────────────────────► Susheep (Frontend)
         │    http://localhost:8000              http://localhost:5173
         │
         ├─── WebSocket ──────────────────────► Susheep (Frontend)
         │    ws://localhost:8000/ws
         │
         └─── Web3.py HTTP ──────────────────► Skanda (Ganache)
              http://127.0.0.1:8545

Skanda (Blockchain) ──copies──► blockchain/web3_bridge/contract_abi.json
                                 blockchain/web3_bridge/web3_client.py
                                         │
                                         ▼
                    Sairaj (Backend) imports blockchain_adapter.py
                    which wraps Skanda's web3_client.py

SHARED ENVIRONMENT VARIABLES (in .env.shared.example):
  BACKEND_URL=http://localhost:8000
  GANACHE_URL=http://127.0.0.1:8545
  CONTRACT_ADDRESS=<deployed by Skanda>
  WEIGHTS_PATH=../ml/models/graphsage_weights.pt
  SCALER_PATH=../ml/models/scaler.pkl
  SQLITE_PATH=./graphsentinel.db
  THREAT_THRESHOLD=0.75
  POLL_INTERVAL_SECONDS=5
```

### 4.3 File Sharing Between Windows and WSL2

```bash
# Strategy: Clone repo on WINDOWS, access from WSL2 via mount
# Windows path:    C:\Projects\graphsentinel\
# WSL2 path:       /mnt/c/Projects/graphsentinel/

# Recommended: ALL members clone to same Windows path:
git clone https://github.com/team/graphsentinel.git C:\Projects\graphsentinel

# Sairaj (Backend) — always work from WSL2:
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Susheep (Frontend) — work from Windows PowerShell:
cd C:\Projects\graphsentinel\frontend
npm run dev

# Skanda (Blockchain) — Hardhat from Windows, Ganache from Windows:
cd C:\Projects\graphsentinel\blockchain
npx ganache --port 8545    # Terminal 1
npx hardhat run scripts/deploy.js --network localhost    # Terminal 2

# Sathvik (ML) — Google Colab, then copy outputs:
# After training: download graphsage_weights.pt + scaler.pkl
# Place in: C:\Projects\graphsentinel\ml\models\
```

---

## 👤 SECTION 5 — SAIRAJ: BACKEND IMPLEMENTATION PLAN

> **Current Sairaj backend contract:** use `SAIRAJ_BACKEND_PLAN.md` as the source of truth for backend implementation. The latest hardening update requires flow-node PyG graphs, no inference-time scaler, explicit ML degraded mode, API-token protection for mutating endpoints, IP validation with `ipaddress`, and OVS drop-flow enforcement through a narrow agent. Do not copy older iptables/root-server patterns.

### 5.1 Environment Setup [WSL2]

```bash
# STEP 1: Enable WSL2 on Windows 11
# Run as Administrator in PowerShell:
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2

# STEP 2: Inside WSL2 Ubuntu 22.04
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y build-essential curl git wget libssl-dev \
  libffi-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  openvswitch-switch openvswitch-testcontroller net-tools

# STEP 3: Install pyenv for Python version management
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# STEP 4: Install Python 3.10.11 STRICTLY
pyenv install 3.10.11
pyenv global 3.10.11
python --version   # Must show 3.10.11

# STEP 5: Install Mininet
git clone https://github.com/mininet/mininet
cd mininet
sudo PYTHON=python3 ./util/install.sh -a   # Full install with OVS
sudo mn --test pingall                      # Verify Mininet works
cd ..

# STEP 6: Create virtual environment for the project
cd /mnt/c/Projects/graphsentinel/backend
python -m venv .venv
source .venv/bin/activate

# STEP 7: Install dependencies
pip install --upgrade pip
pip install fastapi==0.115.* uvicorn==0.35.* python-socketio==5.*
pip install networkx==3.3.* pandas==2.2.* numpy==1.26.* scikit-learn==1.5.*
pip install scapy==2.5.*

# STEP 8: Install PyTorch 2.4.x (CPU — for inference only)
pip install torch==2.4.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# STEP 9: Install PyTorch Geometric
pip install torch-geometric==2.5.*
# If scatter/sparse fail, install from PyG wheels:
# pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.4.0+cpu.html

# STEP 10: Install Web3.py
pip install web3==7.*

# STEP 11: Freeze
pip freeze > requirements.txt
```

### 5.2 Backend Pipeline (Optimized + Realistic)

```
PRODUCTION-GRADE DATA PIPELINE:

Mininet Topology (WSL2)
       │ (every 5 seconds — polling thread)
       ▼
flow_parser.py
  • Reads OVS port stats via: sudo ovs-ofctl dump-flows s1
  • Extracts: src_ip, dst_ip, src_port, dst_port, protocol,
              packet_count, byte_count, duration_sec, tcp_flags
  • Output: List[FlowRecord] (Pydantic model)
       │
       ▼
graph_builder.py
  • Builds a PyG Data object with one node per flow, not one node per IP
  • Adds temporal edges flow[i] -> flow[i+1]
  • Adds same-destination-port edges from prior matching flow -> current flow
  • Computes exactly the 7 features in backend/NODE_FEATURES.md
  • Applies per-window z-score normalization inside graph_builder.py
  • Output: PyG Data with x=(N,7), edge_index, flow_sources, flow_destinations
       │
       ▼
inference_service.py
  • Loads graphsage_weights.pt at startup (singleton)
  • Does NOT apply scaler.pkl to the 7 inference features
  • Missing weights fail startup unless DEMO_ALLOW_MOCK_ML=true
  • Runs model.eval() forward pass — no_grad()
  • Returns flow_scores and IP-aggregated threat scores for frontend graph/healing
  • Output: { flow_scores: [...], ip_scores: { ip: score } }
       │
       ▼
threat_analyzer.py
  • Applies THREAT_THRESHOLD = 0.75 (configurable in .env)
  • Classifies: benign < 0.50 | suspicious 0.50-0.75 | malicious > 0.75
  • Generates IncidentRecord if threshold crossed
  • Output: List[IncidentRecord]
       │
  ┌────┴──────────────────────────────────────────────────┐
  ▼                        ▼                              ▼
self_healing.py        SQLite Logger              blockchain_adapter.py
  • Validates IPs with     • Writes to              • Calls Skanda's
    ipaddress              incidents table           web3_client.py
  • Uses OVS drop flows     via SQLAlchemy           • logIncident()
    through enforcement                              on smart contract
    agent                                            • Stores tx hash
  • Updates                                          • Returns tx_hash
    blocked_ips table
  • Reconciles SQLite
    block state with OVS
       │                                                    │
       └────────────────────────────────────────────────────┘
                                │
                                ▼
                    websocket/events.py
                      • Emits graph_update event
                      • Emits alert event
                      • Emits healing_triggered event
                      • Pushes to ALL connected frontend clients
```

### 5.3 FastAPI Application Structure

```python
# backend/app/main.py — [WSL2] [Python 3.10.11]

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

# ── App init ──────────────────────────────────────────
app = FastAPI(title="GraphSentinel API", version="1.0.0")
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, app)

# ── CORS — CRITICAL: allows React (port 5173) to call backend ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────
from app.api.v1 import analyze, graph, stats, timeline, alerts, blocked, forensics, blockchain
app.include_router(analyze.router,    prefix="/api/v1")
app.include_router(graph.router,      prefix="/api/v1")
app.include_router(stats.router,      prefix="/api/v1")
app.include_router(timeline.router,   prefix="/api/v1")
app.include_router(alerts.router,     prefix="/api/v1")
app.include_router(blocked.router,    prefix="/api/v1")
app.include_router(forensics.router,  prefix="/api/v1")
app.include_router(blockchain.router, prefix="/api/v1")

# ── Background task: Mininet polling ───────────────────
from app.mininet_monitor.monitor import MininetMonitor
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor = MininetMonitor(sio=sio)
    monitor.start()  # Background thread
    yield
    monitor.stop()

# Start with: uvicorn app.main:socket_app --reload --host 0.0.0.0 --port 8000
```

### 5.4 Module Implementation Details

**Module: inference_service.py**
```python
# backend/app/services/inference_service.py — [WSL2]
import torch
import pickle
from app.services.graph_builder import build_pyg_graph
from ml.src.model import GraphSAGEClassifier  # shared import path

class InferenceService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.device = torch.device("cpu")
        self.model = GraphSAGEClassifier(
            in_channels=7,   # Must match Sathvik's node feature count
            hidden_channels=256,
            out_channels=2,
            num_layers=3
        )
        # Load weights — path set by Sathvik's export
        weights_path = os.getenv("WEIGHTS_PATH", "../ml/models/graphsage_weights.pt")
        self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
        self.model.eval()

        scaler_path = os.getenv("SCALER_PATH", "../ml/models/scaler.pkl")
        with open(scaler_path, "rb") as f:
            self.scaler = pickle.load(f)

    def predict(self, flow_records: list) -> dict:
        pyg_data = build_pyg_graph(flow_records, self.scaler)
        with torch.no_grad():
            logits = self.model(pyg_data.x, pyg_data.edge_index)
            probs = torch.softmax(logits, dim=1)[:, 1]  # malicious prob
        # Return: { "ip_address": threat_score (0.0-1.0), ... }
        return dict(zip(pyg_data.node_ips, probs.tolist()))
```

**Module: self_healing.py**
```python
# backend/app/services/self_healing.py — [WSL2]
# Requires Mininet to be running and accessible

import subprocess
from app.database import get_db
from app.models.incident import BlockedIP

class SelfHealingEngine:
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
        self.blocked = set()

    def evaluate_and_act(self, predictions: dict, sio=None) -> list:
        """
        predictions: { "10.0.0.2": 0.94, "10.0.0.1": 0.12 }
        Returns list of newly blocked IPs
        """
        newly_blocked = []
        for ip, score in predictions.items():
            if score >= self.threshold and ip not in self.blocked:
                self._block_ip(ip)
                self.blocked.add(ip)
                newly_blocked.append({
                    "ip": ip,
                    "threat_score": score,
                    "action": "BLOCKED"
                })
                # Push to frontend via WebSocket
                if sio:
                    sio.emit("healing_triggered", {
                        "ip": ip,
                        "score": score,
                        "status": "isolated"
                    })
        return newly_blocked

    def _block_ip(self, ip: str):
        """Block via iptables inside WSL2 (simulates network isolation)"""
        subprocess.run(
            ["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"],
            check=True
        )
        # Also write to SQLite
        with get_db() as db:
            db.add(BlockedIP(ip_address=ip, reason="GNN_DETECTED"))
            db.commit()

    def unblock_ip(self, ip: str):
        subprocess.run(
            ["sudo", "iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"]
        )
        self.blocked.discard(ip)
```

### 5.5 Week-by-Week Plan (Sairaj)

| Week | Focus | Deliverable |
|------|-------|-------------|
| **W1** | WSL2 setup + pyenv + Mininet install + repo clone | Mininet `pingall` works, Python 3.10.11 confirmed |
| **W2** | FastAPI skeleton + SQLite schema + CORS config | API server starts on port 8000, mock responses |
| **W3** | graph_builder.py + mock inference (random scores) | `/api/v1/analyze` returns fake predictions |
| **W4** | Load Sathvik's weights.pt → real inference_service.py | Real GNN predictions from static graph |
| **W5** | Mininet topology + monitor.py + flow_parser.py | Live flow data extracted from Mininet every 5s |
| **W6** | self_healing.py + SQLite logging + WebSocket events | Blocking works, frontend receives events |
| **W7** | blockchain_adapter.py → integrates Skanda's web3_client | Full pipeline: attack → detect → block → chain |
| **W8** | Integration testing + fallback mocks + demo hardening | 60-min demo works end-to-end |

### 5.6 Risks and Failure Points (Sairaj)

| Risk | Probability | Impact | Failure Scenario | Mitigation |
|------|------------|--------|-----------------|-----------|
| Mininet won't start on WSL2 | **HIGH** | Critical | OVS kernel module missing, requires `sudo mn` | Install OVS in WSL2 during W1, test daily |
| iptables block fails silently | **MEDIUM** | High | Self-healing fires but doesn't actually block | Test iptables rules manually before demo |
| PyTorch Geometric install fails | **HIGH** | Critical | Wheel incompatibility with Python 3.10 | Use exact pip wheel URLs from PyG docs |
| WebSocket drops under load | **MEDIUM** | Medium | Frontend loses real-time updates | Add reconnect logic in useWebSocket.js |
| Inference >500ms latency | **MEDIUM** | Medium | Demo feels laggy | Pre-batch 5s of flows, batch inference |
| Path mismatch (Windows/WSL2) | **HIGH** | High | weights.pt not found | Use absolute WSL2 paths in .env |
| SQLite file lock during demo | **LOW** | Medium | Multiple writes collide | Use WAL mode: `PRAGMA journal_mode=WAL` |

---

## 👤 SECTION 6 — SUSHEEP: FRONTEND IMPLEMENTATION PLAN

### 6.1 Environment Setup [Windows Native]

```powershell
# STEP 1: Install Node.js LTS (Windows)
# Download from: https://nodejs.org/en/download (LTS 20.x)
node --version   # Should show v20.x.x
npm --version    # Should show 10.x.x

# STEP 2: Navigate to project
cd C:\Projects\graphsentinel\frontend

# STEP 3: Create Vite React project (if not scaffolded)
npm create vite@latest . -- --template react
# Choose: React → JavaScript

# STEP 4: Install all dependencies
npm install

# 3D Visualization Stack
npm install react-force-graph-3d three@0.167.0
npm install @react-three/fiber@8 @react-three/drei@9

# 2D Fallback (Cytoscape)
npm install cytoscape react-cytoscapejs

# Real-time + API
npm install socket.io-client@4 axios@1.7

# UI + Charts
npm install recharts@2 lucide-react tailwindcss framer-motion
npm install -D autoprefixer postcss

# State management (lightweight)
npm install zustand

# STEP 5: Initialize Tailwind
npx tailwindcss init -p

# STEP 6: Configure Vite proxy (critical for backend calls)
# Edit vite.config.js (see Section 6.3)

# STEP 7: Run dev server
npm run dev   # http://localhost:5173
```

### 6.2 Dashboard Architecture + UI/UX Blueprint

```
DASHBOARD LAYOUT (Full-Screen Dark Theme):

┌─────────────────────────────────────────────────────────────────────┐
│  🛡️ GRAPHSENTINEL                    ● LIVE  [System: HEALTHY]     │  ← StatsBar
│  Nodes: 10 | Malicious: 2 | Blocked: 1 | Threats Today: 7          │
├──────────────────────────────────┬──────────────────────────────────┤
│                                  │                                   │
│                                  │  🚨 ALERT FEED                   │  ← AlertPanel
│                                  │  ─────────────────               │
│   3D NETWORK GRAPH               │  [DDoS] 10.0.0.2 → 10.0.0.8     │
│                                  │  Threat: 94% | 14:32:01          │
│   (react-force-graph-3d)         │  ─────────────────               │
│                                  │  [PortScan] 10.0.0.5             │
│   • Green spheres = benign       │  Threat: 81% | 14:31:44          │
│   • Red pulsing = malicious      │  ─────────────────               │
│   • Blue cage = isolated         │                                   │
│   • Yellow = suspicious          │  ⛓️  BLOCKCHAIN LEDGER           │  ← BlockchainPanel
│   • Animated particles = traffic │  ─────────────────               │
│                                  │  TX: 0x4f3a...c21b               │
│   [Toggle 2D/3D]                 │  IP: 10.0.0.2 | DDoS             │
│                                  │  Time: 14:32:01 ✓                │
│                                  │  ─────────────────               │
│                                  │  TX: 0x9e1d...a54f               │
│                                  │  IP: 10.0.0.5 | PortScan         │
├──────────────────────────────────┤  Time: 14:31:44 ✓               │
│  🔒 BLOCKED NODES                │  ─────────────────               │
│  10.0.0.2 | DDoS | 0.94 | 14:32 │                                   │
│  10.0.0.5 | Scan | 0.81 | 14:31 │  🛡️ SELF-HEALING STATUS          │  ← SelfHealStatus
├──────────────────────────────────┤  Node 10.0.0.2 — ISOLATED       │
│  📈 THREAT TIMELINE              │  Edges removed: 6                │
│  (Recharts line graph)           │  Network stability: 94%          │
└──────────────────────────────────┴──────────────────────────────────┘

THEME: Background #0a0e1a (deep navy), Cards #111827, 
       Accent #00ff88 (neon green), Alert #ff4444, 
       Warning #ffaa00, Info #0099ff, Blockchain #9945ff
```

### 6.3 Vite Configuration (API Proxy)

```javascript
// frontend/vite.config.js — [Windows]
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // All /api calls → backend on WSL2 port 8000
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      // WebSocket proxy
      '/socket.io': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      }
    }
  }
})
```

### 6.4 Complete Static Dummy Data (Use Until Backend Ready)

```javascript
// frontend/src/services/mockData.js — [Windows]
// ═══════════════════════════════════════════════════════════════════
// ALL DUMMY DATA — Replace each section with real API calls
// when the backend is integrated. Look for "TODO: REPLACE" comments.
// ═══════════════════════════════════════════════════════════════════

// ─── SECTION A: Network Graph ────────────────────────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/graph')
//   const { nodes, edges } = response.data
// ─────────────────────────────────────────────────────────────────
export const MOCK_GRAPH_DATA = {
  nodes: [
    {
      id: "10.0.0.1",   label: "h1-Router",
      status: "normal", // "normal"|"suspicious"|"malicious"|"blocked"
      threat_score: 0.08, connections: 4, bytes_total: 45200,
      attack_type: null, is_blocked: false,
      pos_x: 0,   pos_y: 0,   pos_z: 0
    },
    {
      id: "10.0.0.2",   label: "h2-Attacker",
      status: "malicious",
      threat_score: 0.94, connections: 487, bytes_total: 5120000,
      attack_type: "DDoS", is_blocked: false,
      pos_x: 2.5, pos_y: 1.2, pos_z: 0.3
    },
    {
      id: "10.0.0.3",   label: "h3-Server",
      status: "normal",
      threat_score: 0.11, connections: 6, bytes_total: 98000,
      attack_type: null, is_blocked: false,
      pos_x: -1.8, pos_y: 2.1, pos_z: -0.5
    },
    {
      id: "10.0.0.4",   label: "h4-DB",
      status: "suspicious",
      threat_score: 0.61, connections: 25, bytes_total: 210000,
      attack_type: "PortScan", is_blocked: false,
      pos_x: 3.2, pos_y: -1.1, pos_z: 1.0
    },
    {
      id: "10.0.0.5",   label: "h5-Victim",
      status: "blocked",
      threat_score: 0.88, connections: 190, bytes_total: 1780000,
      attack_type: "SSHBrute", is_blocked: true,
      pos_x: -2.5, pos_y: -1.5, pos_z: 0.8
    },
    {
      id: "10.0.0.6",   label: "h6-Web",
      status: "normal",
      threat_score: 0.05, connections: 3,  bytes_total: 32000,
      attack_type: null, is_blocked: false,
      pos_x: 0.5, pos_y: 3.0, pos_z: -1.2
    },
    {
      id: "10.0.0.7",   label: "h7-Admin",
      status: "normal",
      threat_score: 0.13, connections: 5,  bytes_total: 67000,
      attack_type: null, is_blocked: false,
      pos_x: -3.0, pos_y: 0.5, pos_z: 0.2
    },
    {
      id: "10.0.0.8",   label: "h8-Client",
      status: "suspicious",
      threat_score: 0.55, connections: 42, bytes_total: 380000,
      attack_type: "Botnet", is_blocked: false,
      pos_x: 1.8, pos_y: -2.8, pos_z: -0.7
    },
    {
      id: "10.0.0.9",   label: "h9-Storage",
      status: "normal",
      threat_score: 0.09, connections: 2,  bytes_total: 15000,
      attack_type: null, is_blocked: false,
      pos_x: -1.2, pos_y: -3.2, pos_z: 1.5
    },
    {
      id: "10.0.0.10",  label: "h10-Monitor",
      status: "normal",
      threat_score: 0.04, connections: 8,  bytes_total: 88000,
      attack_type: null, is_blocked: false,
      pos_x: 4.0, pos_y: 1.8, pos_z: -0.3
    },
  ],
  links: [
    { source: "10.0.0.2", target: "10.0.0.1", value: 0.94, attack_type: "DDoS",     packet_count: 15000 },
    { source: "10.0.0.2", target: "10.0.0.3", value: 0.91, attack_type: "DDoS",     packet_count: 12000 },
    { source: "10.0.0.2", target: "10.0.0.6", value: 0.88, attack_type: "DDoS",     packet_count: 9800  },
    { source: "10.0.0.5", target: "10.0.0.7", value: 0.88, attack_type: "SSHBrute", packet_count: 3400  },
    { source: "10.0.0.4", target: "10.0.0.9", value: 0.61, attack_type: "PortScan", packet_count: 1200  },
    { source: "10.0.0.8", target: "10.0.0.1", value: 0.55, attack_type: "Botnet",   packet_count: 890   },
    { source: "10.0.0.1", target: "10.0.0.3", value: 0.10, attack_type: null,       packet_count: 45    },
    { source: "10.0.0.3", target: "10.0.0.6", value: 0.08, attack_type: null,       packet_count: 30    },
    { source: "10.0.0.7", target: "10.0.0.10",value: 0.12, attack_type: null,       packet_count: 60    },
  ]
}

// ─── SECTION B: Alerts Feed ──────────────────────────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/alerts')
//   const alerts = response.data
// ─────────────────────────────────────────────────────────────────
export const MOCK_ALERTS = [
  {
    id: "alert-001",
    timestamp: "2024-01-15T14:32:01Z",
    source_ip: "10.0.0.2",
    attack_type: "DDoS",
    severity: "critical",  // "info"|"warning"|"critical"
    threat_score: 0.94,
    description: "High-volume DDoS detected — 15,000 packets in 3.5s",
    is_blocked: false,
    blockchain_tx: "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1"
  },
  {
    id: "alert-002",
    timestamp: "2024-01-15T14:31:44Z",
    source_ip: "10.0.0.5",
    attack_type: "SSHBrute",
    severity: "critical",
    threat_score: 0.88,
    description: "SSH brute force — 3,400 login attempts",
    is_blocked: true,
    blockchain_tx: "0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8"
  },
  {
    id: "alert-003",
    timestamp: "2024-01-15T14:31:20Z",
    source_ip: "10.0.0.4",
    attack_type: "PortScan",
    severity: "warning",
    threat_score: 0.61,
    description: "Systematic port scan on 1,200 ports detected",
    is_blocked: false,
    blockchain_tx: null  // Not yet stored on chain
  },
  {
    id: "alert-004",
    timestamp: "2024-01-15T14:30:55Z",
    source_ip: "10.0.0.8",
    attack_type: "Botnet",
    severity: "warning",
    threat_score: 0.55,
    description: "Botnet C2 communication pattern detected",
    is_blocked: false,
    blockchain_tx: null
  }
]

// ─── SECTION C: Blocked Nodes ────────────────────────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/blocked')
//   const blocked = response.data
// ─────────────────────────────────────────────────────────────────
export const MOCK_BLOCKED = [
  {
    ip: "10.0.0.5",
    blocked_at: "2024-01-15T14:31:50Z",
    reason: "GNN_DETECTED",
    attack_type: "SSHBrute",
    threat_score: 0.88,
    edges_removed: 4,
    blockchain_tx: "0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8"
  }
]

// ─── SECTION D: Blockchain Ledger ────────────────────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/forensics')
//   const transactions = response.data.blockchain_records
// ─────────────────────────────────────────────────────────────────
export const MOCK_BLOCKCHAIN_TXS = [
  {
    tx_hash: "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1",
    block_number: 142,
    timestamp: "2024-01-15T14:32:01Z",
    source_ip: "10.0.0.2",
    attack_type: "DDoS",
    severity: 9,
    is_blocked: false,
    incident_hash: "0xb8f2a1c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    gas_used: 68432,
    status: "confirmed"
  },
  {
    tx_hash: "0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8",
    block_number: 141,
    timestamp: "2024-01-15T14:31:50Z",
    source_ip: "10.0.0.5",
    attack_type: "SSHBrute",
    severity: 8,
    is_blocked: true,
    incident_hash: "0xa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    gas_used: 71200,
    status: "confirmed"
  },
]

// ─── SECTION E: System Stats ─────────────────────────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/stats')
//   const stats = response.data
// ─────────────────────────────────────────────────────────────────
export const MOCK_STATS = {
  total_nodes: 10,
  malicious_nodes: 2,
  suspicious_nodes: 2,
  blocked_nodes: 1,
  total_threats_today: 7,
  blockchain_tx_count: 2,
  system_health: 94,     // percentage
  model_confidence: 0.89,
  last_updated: "2024-01-15T14:32:05Z"
}

// ─── SECTION F: Self-Healing Events ──────────────────────────────
// TODO: REPLACE WITH REAL WEBSOCKET:
//   socket.on('healing_triggered', (event) => setHealingEvents(prev => [event, ...prev]))
// ─────────────────────────────────────────────────────────────────
export const MOCK_HEALING_EVENTS = [
  {
    id: "heal-001",
    timestamp: "2024-01-15T14:31:50Z",
    ip: "10.0.0.5",
    action: "ISOLATED",
    edges_severed: 4,
    trigger_score: 0.88,
    attack_type: "SSHBrute",
    duration_ms: 245,   // how fast the healing was
    network_stability_before: 88,
    network_stability_after: 94
  }
]

// ─── SECTION G: Threat Timeline (for Recharts) ───────────────────
// TODO: REPLACE WITH REAL API CALL:
//   const response = await axios.get('/api/v1/timeline?last=60min')
//   const points = response.data.data_points
// ─────────────────────────────────────────────────────────────────
export const MOCK_TIMELINE = [
  { time: "14:25", threats: 0, blocked: 0 },
  { time: "14:26", threats: 1, blocked: 0 },
  { time: "14:27", threats: 2, blocked: 0 },
  { time: "14:28", threats: 3, blocked: 1 },
  { time: "14:29", threats: 5, blocked: 1 },
  { time: "14:30", threats: 6, blocked: 1 },
  { time: "14:31", threats: 7, blocked: 1 },
  { time: "14:32", threats: 7, blocked: 1 },
]
```

### 6.5 3D Network Graph Component

```jsx
// frontend/src/components/NetworkGraph3D/NetworkGraph3D.jsx — [Windows]
import React, { useRef, useCallback, useMemo, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import { MOCK_GRAPH_DATA } from '../../services/mockData'

// ─── Node Color Scheme ─────────────────────────────────────────────
const NODE_COLORS = {
  normal:     '#00ff88',   // Neon green — healthy
  suspicious: '#ffaa00',   // Amber — watch list
  malicious:  '#ff4444',   // Red — confirmed attack
  blocked:    '#0066ff',   // Blue — isolated/quarantined
}

const LINK_COLORS = {
  DDoS:       '#ff4444',
  SSHBrute:   '#ff8800',
  PortScan:   '#ffff00',
  Botnet:     '#aa44ff',
  DoSHulk:    '#ff2266',
  normal:     '#334466',
}

export default function NetworkGraph3D({ 
  graphData = MOCK_GRAPH_DATA,  // TODO: REPLACE WITH real graphData from props/store
  onNodeClick,
  healingNodeId = null,         // IP being isolated (triggers animation)
}) {
  const fgRef = useRef()
  const [selectedNode, setSelectedNode] = useState(null)

  // Custom 3D node object
  const nodeThreeObject = useCallback((node) => {
    const isHealing = node.id === healingNodeId
    const isMalicious = node.status === 'malicious'

    const geometry = new THREE.SphereGeometry(
      node.status === 'malicious' ? 8 : 5, 16, 16
    )

    // Emissive glow for malicious nodes
    const material = new THREE.MeshPhongMaterial({
      color: NODE_COLORS[node.status] || '#ffffff',
      emissive: isMalicious ? NODE_COLORS.malicious : '#000000',
      emissiveIntensity: isMalicious ? 0.6 : 0,
      transparent: node.status === 'blocked',
      opacity: node.status === 'blocked' ? 0.7 : 1.0,
    })

    const mesh = new THREE.Mesh(geometry, material)

    // Cage effect for isolated/blocked nodes
    if (node.status === 'blocked') {
      const cageGeo = new THREE.WireframeGeometry(
        new THREE.SphereGeometry(12, 8, 8)
      )
      const cageMat = new THREE.LineBasicMaterial({ color: '#0066ff', opacity: 0.5, transparent: true })
      const cage = new THREE.LineSegments(cageGeo, cageMat)
      mesh.add(cage)
    }

    // Label
    const canvas = document.createElement('canvas')
    canvas.width = 256; canvas.height = 64
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#ffffff'
    ctx.font = '24px monospace'
    ctx.fillText(node.label || node.id, 10, 40)
    const texture = new THREE.CanvasTexture(canvas)
    const spriteMat = new THREE.SpriteMaterial({ map: texture })
    const sprite = new THREE.Sprite(spriteMat)
    sprite.scale.set(30, 8, 1)
    sprite.position.set(0, 14, 0)
    mesh.add(sprite)

    return mesh
  }, [healingNodeId])

  // Link color + width by attack type
  const getLinkColor = useCallback((link) => {
    return LINK_COLORS[link.attack_type] || LINK_COLORS.normal
  }, [])

  const getLinkWidth = useCallback((link) => {
    return link.value > 0.75 ? 3 : link.value > 0.5 ? 2 : 1
  }, [])

  // Particle speed = threat level (makes traffic VISIBLE)
  const getParticles = useCallback((link) => {
    if (link.value > 0.75) return 6   // Many particles = high threat
    if (link.value > 0.5)  return 3
    return 1
  }, [])

  return (
    <div style={{ width: '100%', height: '100%', background: '#0a0e1a' }}>
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkDirectionalParticles={getParticles}
        linkDirectionalParticleSpeed={0.008}
        linkDirectionalParticleColor={getLinkColor}
        backgroundColor="#0a0e1a"
        onNodeClick={(node) => {
          setSelectedNode(node)
          if (onNodeClick) onNodeClick(node)
          // Focus camera on clicked node
          const { x, y, z } = node
          fgRef.current.cameraPosition(
            { x: x + 50, y: y + 50, z: z + 50 },
            { x, y, z },
            1500
          )
        }}
        enableNodeDrag={true}
        enableNavigationControls={true}
      />
    </div>
  )
}
```

### 6.6 WebSocket Real-Time Hook

```javascript
// frontend/src/hooks/useWebSocket.js — [Windows]
// TODO: THIS HOOK ALREADY CONNECTS TO REAL BACKEND
// It falls back to mock data if connection fails.

import { useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export function useWebSocket({ onGraphUpdate, onAlert, onHealingTriggered }) {
  const socketRef = useRef(null)

  useEffect(() => {
    // Connect to backend Socket.IO
    const socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    })

    socket.on('connect', () => {
      console.log('[WebSocket] Connected to GraphSentinel backend')
    })

    // TODO: This receives real graph from backend every 5 seconds
    // Format: { type: "graph_update", nodes: [...], links: [...] }
    socket.on('graph_update', (data) => {
      if (onGraphUpdate) onGraphUpdate(data)
    })

    // TODO: Fires when threat_score >= threshold
    // Format: see MOCK_ALERTS shape in mockData.js
    socket.on('alert', (data) => {
      if (onAlert) onAlert(data)
    })

    // TODO: Fires when self-healing blocks a node
    // Format: see MOCK_HEALING_EVENTS shape in mockData.js
    socket.on('healing_triggered', (data) => {
      if (onHealingTriggered) onHealingTriggered(data)
    })

    socket.on('disconnect', () => {
      console.warn('[WebSocket] Disconnected — switching to mock data fallback')
      // TODO: When disconnect, UI should show "SIMULATION MODE" badge
    })

    socketRef.current = socket
    return () => socket.disconnect()
  }, [])

  return socketRef.current
}
```

### 6.7 Self-Healing Animation (Framer Motion + Three.js)

```jsx
// frontend/src/components/SelfHealingStatus/SelfHealStatus.jsx — [Windows]
// Visual indicators when a node is being isolated

import { motion, AnimatePresence } from 'framer-motion'

export default function SelfHealStatus({ events = [] }) {
  // events: array from MOCK_HEALING_EVENTS / real WebSocket
  // TODO: REPLACE with: const { healingEvents } = useGraphStore()

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-blue-500/30">
      <h3 className="text-blue-400 font-mono text-sm mb-3">
        🛡️ SELF-HEALING ENGINE
      </h3>
      <AnimatePresence>
        {events.map(event => (
          <motion.div
            key={event.id}
            initial={{ opacity: 0, x: 20, backgroundColor: '#ff4444' }}
            animate={{ opacity: 1, x: 0, backgroundColor: '#0a1628' }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8 }}
            className="mb-2 p-2 rounded border border-blue-500/20 font-mono text-xs"
          >
            {/* Isolation animation: RED → BLUE transition */}
            <div className="flex items-center gap-2">
              <motion.div
                className="w-3 h-3 rounded-full"
                animate={{
                  backgroundColor: ['#ff4444', '#ff8800', '#0066ff'],
                  scale: [1, 1.5, 1],
                }}
                transition={{ duration: 1.5, times: [0, 0.5, 1] }}
              />
              <span className="text-blue-300">{event.ip}</span>
              <span className="text-gray-400">→</span>
              <span className="text-blue-400 font-bold">ISOLATED</span>
            </div>
            <div className="mt-1 text-gray-500">
              Attack: {event.attack_type} | 
              Edges severed: {event.edges_severed} | 
              Healed in: {event.duration_ms}ms
            </div>
            {/* Stability recovery bar */}
            <div className="mt-1 flex items-center gap-2">
              <span className="text-gray-500">Network stability:</span>
              <motion.div
                className="h-1.5 bg-green-500 rounded"
                initial={{ width: `${event.network_stability_before}%` }}
                animate={{ width: `${event.network_stability_after}%` }}
                transition={{ duration: 1.5, delay: 0.5 }}
                style={{ maxWidth: '100px' }}
              />
              <span className="text-green-400">{event.network_stability_after}%</span>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      {events.length === 0 && (
        <div className="text-gray-600 text-xs font-mono">No isolation events yet.</div>
      )}
    </div>
  )
}
```

### 6.8 Blockchain Ledger Visualization

```jsx
// frontend/src/components/BlockchainLedger/BlockchainPanel.jsx — [Windows]
import { motion } from 'framer-motion'
import { MOCK_BLOCKCHAIN_TXS } from '../../services/mockData'

export default function BlockchainPanel({ transactions = MOCK_BLOCKCHAIN_TXS }) {
  // TODO: REPLACE transactions with real data:
  //   const response = await axios.get('/api/v1/forensics')
  //   const transactions = response.data.blockchain_records

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-purple-500/30">
      <h3 className="text-purple-400 font-mono text-sm mb-3 flex items-center gap-2">
        ⛓️ IMMUTABLE BLOCKCHAIN LEDGER
        <span className="text-xs text-purple-600">Ganache Local Chain</span>
      </h3>

      {transactions.map((tx, i) => (
        <motion.div
          key={tx.tx_hash}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
          className="mb-2 p-2 rounded bg-gray-800 border border-purple-500/20"
        >
          {/* TX Hash with copy button */}
          <div className="flex items-center justify-between">
            <span className="text-purple-300 font-mono text-xs">
              {tx.tx_hash.slice(0, 18)}...{tx.tx_hash.slice(-6)}
            </span>
            {/* Green tick = tamper-proof confirmed */}
            <span className="text-green-400 text-xs">
              {tx.status === 'confirmed' ? '✓ Immutable' : '⏳ Pending'}
            </span>
          </div>
          {/* Incident metadata */}
          <div className="mt-1 text-gray-400 text-xs font-mono">
            <span className="text-red-400">{tx.attack_type}</span>
            {' | '}{tx.source_ip}
            {' | Block #{' + tx.block_number + '}'}
            {' | '}{new Date(tx.timestamp).toLocaleTimeString()}
          </div>
          {/* Severity bar */}
          <div className="mt-1 flex items-center gap-1">
            <span className="text-gray-600 text-xs">Severity:</span>
            {[...Array(10)].map((_, j) => (
              <div
                key={j}
                className={`w-2 h-2 rounded-sm ${j < tx.severity ? 'bg-red-500' : 'bg-gray-700'}`}
              />
            ))}
            <span className="text-red-400 text-xs ml-1">{tx.severity}/10</span>
          </div>
        </motion.div>
      ))}

      {/* TODO: Connect ethers.js to read from Ganache contract directly:
          import { ethers } from 'ethers'
          const provider = new ethers.JsonRpcProvider('http://127.0.0.1:8545')
          const contract = new ethers.Contract(CONTRACT_ADDRESS, ABI, provider)
          const count = await contract.getIncidentCount()
          for (let i = 0; i < count; i++) {
            const incident = await contract.getIncident(i)
            // Map to transaction display
          }
      */}
    </div>
  )
}
```

### 6.9 Frontend Data Contracts (What Backend Sends)

```typescript
// docs/DATA_SCHEMAS.md — shape of every API response
// Susheep: build your components expecting EXACTLY these shapes.

// GET /api/v1/graph — returns full network state
interface GraphResponse {
  nodes: Array<{
    id: string           // IP address
    label: string        // hostname
    status: 'normal' | 'suspicious' | 'malicious' | 'blocked'
    threat_score: number // 0.0 – 1.0
    connections: number
    bytes_total: number
    attack_type: string | null
    is_blocked: boolean
  }>
  links: Array<{
    source: string       // source IP
    target: string       // destination IP
    value: number        // threat weight 0.0–1.0
    attack_type: string | null
    packet_count: number
  }>
  metadata: {
    total_nodes: number
    malicious_nodes: number
    last_updated: string  // ISO timestamp
  }
}

// GET /api/v1/alerts
interface AlertsResponse {
  alerts: Array<{
    id: string
    timestamp: string
    source_ip: string
    attack_type: string
    severity: 'info' | 'warning' | 'critical'
    threat_score: number
    description: string
    is_blocked: boolean
    blockchain_tx: string | null
  }>
}

// WebSocket event: 'graph_update' (every 5 seconds)
interface GraphUpdateEvent extends GraphResponse {}

// WebSocket event: 'healing_triggered'
interface HealingEvent {
  ip: string
  attack_type: string
  trigger_score: number
  action: 'ISOLATED'
  edges_severed: number
  duration_ms: number
  network_stability_after: number
  timestamp: string
}

// WebSocket event: 'alert'
interface AlertEvent extends AlertsResponse['alerts'][0] {}
```

### 6.10 Week-by-Week Plan (Susheep)

| Week | Focus | Deliverable |
|------|-------|-------------|
| **W1** | Node.js install, Vite scaffold, Tailwind, folder structure | `npm run dev` renders dark dashboard shell |
| **W2** | Implement all mock data, StatsBar, AlertPanel with dummy data | Full UI visible with static data |
| **W3** | 3D NetworkGraph with react-force-graph-3d + mock graph data | 3D graph renders with colored nodes |
| **W4** | Self-healing animation, BlockchainPanel, SelfHealStatus | All panels wired to mock data |
| **W5** | Replace graph/alerts with real API calls (axios + /api/v1/*) | UI shows real backend data |
| **W6** | WebSocket hook connected — real-time graph updates | Live graph updates every 5s |
| **W7** | Cytoscape 2D toggle, ThreatTimeline (Recharts), ForensicsModal | Polish + both 2D/3D modes |
| **W8** | Demo hardening, smooth animations, loading states | 60-min demo quality |

### 6.11 Risks and Failure Points (Susheep)

| Risk | Probability | Impact | Failure Scenario | Mitigation |
|------|------------|--------|-----------------|-----------|
| 3D graph lag with 10+ nodes | **MEDIUM** | High | Frame drops during demo | Limit particle count, use `nodeRelSize=5` |
| WebSocket CORS block | **HIGH** | High | Real-time stops working | Test Vite proxy config on W5 with Sairaj |
| react-force-graph-3d version conflict | **MEDIUM** | Medium | 3D graph won't render | Pin to exact version in package.json |
| Framer Motion + Three.js conflict | **LOW** | Low | Animation glitches | Keep them in separate DOM layers |
| Cytoscape 2D too slow for large graphs | **LOW** | Low | 2D mode lags | Use headless rendering with lazy layout |
| Mock data not matching real API shape | **HIGH** | High | Components break on integration | Follow DATA_SCHEMAS.md exactly |

---

## 👤 SECTION 7 — SKANDA: BLOCKCHAIN IMPLEMENTATION PLAN

### 7.1 Environment Setup [Windows or WSL2 — Hardhat on Windows]

```powershell
# [Windows PowerShell] — Hardhat runs fine on Windows
cd C:\Projects\graphsentinel\blockchain

# STEP 1: Initialize npm project
npm init -y

# STEP 2: Install Hardhat toolchain
npm install --save-dev hardhat@2.22.0
npm install --save-dev @nomicfoundation/hardhat-toolbox@5

# STEP 3: Initialize Hardhat project
npx hardhat init
# Choose: "Create a JavaScript project"

# STEP 4: Install Ganache (local blockchain)
npm install --save-dev ganache@7.9.0

# STEP 5: Install ethers for scripts
npm install ethers@6

# STEP 6: Install Web3.py in WSL2 (for backend bridge)
# [WSL2 terminal]
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
pip install web3==7.*

# STEP 7: Verify Ganache starts
npx ganache --port 8545 --deterministic --accounts 5
# Should print 5 test accounts with ETH balance
```

### 7.2 Smart Contract Design (IncidentLogger.sol)

```solidity
// blockchain/contracts/IncidentLogger.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IncidentLogger
 * @dev GraphSentinel forensic storage contract
 * @notice Deployed on local Ganache — tamper-proof incident ledger
 */
contract IncidentLogger {

    // ─── Data Structures ─────────────────────────────────────────
    struct Incident {
        uint256 id;
        bytes32 incidentHash;    // keccak256(ip + timestamp + attackType)
        uint256 timestamp;
        string  sourceIP;
        string  attackType;      // "DDoS"|"PortScan"|"Botnet"|"SSHBrute"|"DoSHulk"
        uint8   severity;        // 1–10
        bool    isBlocked;
        string  forensicsURI;    // link to SQLite record: "local://incident/42"
    }

    // ─── Storage ──────────────────────────────────────────────────
    mapping(uint256 => Incident) private incidents;
    mapping(string  => bool)     public  blockedIPs;
    uint256 public incidentCount;

    // ─── Events ───────────────────────────────────────────────────
    event IncidentLogged(
        uint256 indexed id,
        bytes32 indexed incidentHash,
        string sourceIP,
        string attackType,
        uint256 timestamp
    );
    event NodeBlocked(string indexed sourceIP, uint256 timestamp, string reason);
    event NodeUnblocked(string indexed sourceIP, uint256 timestamp);

    // ─── Log an incident ─────────────────────────────────────────
    function logIncident(
        string  memory _sourceIP,
        string  memory _attackType,
        uint8          _severity,
        bool           _isBlocked,
        string  memory _forensicsURI
    ) external returns (uint256) {
        require(_severity >= 1 && _severity <= 10, "Severity must be 1-10");

        uint256 newId = ++incidentCount;

        bytes32 hash = keccak256(abi.encodePacked(
            _sourceIP, block.timestamp, _attackType, newId
        ));

        incidents[newId] = Incident({
            id:           newId,
            incidentHash: hash,
            timestamp:    block.timestamp,
            sourceIP:     _sourceIP,
            attackType:   _attackType,
            severity:     _severity,
            isBlocked:    _isBlocked,
            forensicsURI: _forensicsURI
        });

        if (_isBlocked) {
            blockedIPs[_sourceIP] = true;
            emit NodeBlocked(_sourceIP, block.timestamp, _attackType);
        }

        emit IncidentLogged(newId, hash, _sourceIP, _attackType, block.timestamp);
        return newId;
    }

    // ─── Getters ─────────────────────────────────────────────────
    function getIncident(uint256 _id) external view returns (Incident memory) {
        require(_id > 0 && _id <= incidentCount, "Invalid ID");
        return incidents[_id];
    }

    function getIncidentCount() external view returns (uint256) {
        return incidentCount;
    }

    function isIPBlocked(string memory _ip) external view returns (bool) {
        return blockedIPs[_ip];
    }

    // ─── Unblock (manual override for demo) ──────────────────────
    function unblockIP(string memory _ip) external {
        blockedIPs[_ip] = false;
        emit NodeUnblocked(_ip, block.timestamp);
    }
}
```

### 7.3 Deployment Script

```javascript
// blockchain/scripts/deploy.js — [Windows]
const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying IncidentLogger to local Ganache...");

  const IncidentLogger = await ethers.getContractFactory("IncidentLogger");
  const contract = await IncidentLogger.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`✅ IncidentLogger deployed at: ${address}`);

  // ── IMPORTANT: Save this address to .env ──────────────────────
  // Write to blockchain/.env automatically:
  const fs = require("fs");
  const envContent = `CONTRACT_ADDRESS=${address}\nGANACHE_URL=http://127.0.0.1:8545\n`;
  fs.writeFileSync(".env", envContent);

  // Also write to backend .env for Sairaj:
  const backendEnv = `\n# Blockchain (added by Skanda deploy script)\nCONTRACT_ADDRESS=${address}\nGANACHE_URL=http://127.0.0.1:8545\n`;
  fs.appendFileSync("../backend/.env", backendEnv);

  // Save ABI for backend use:
  const artifact = require("../artifacts/contracts/IncidentLogger.sol/IncidentLogger.json");
  fs.writeFileSync("./web3_bridge/contract_abi.json", JSON.stringify(artifact.abi, null, 2));

  console.log("✅ ABI saved to web3_bridge/contract_abi.json");
  console.log("✅ CONTRACT_ADDRESS written to backend/.env");
}

main().catch((e) => { console.error(e); process.exit(1); });
```

### 7.4 Web3.py Bridge (Used by Sairaj's Backend)

```python
# blockchain/web3_bridge/web3_client.py — [WSL2]
# This file is created by Skanda and imported by Sairaj's blockchain_adapter.py

import json
import hashlib
import os
from web3 import Web3
from datetime import datetime

class BlockchainClient:
    """
    GraphSentinel Forensics Blockchain Client
    Connects to local Ganache instance via HTTP RPC.
    No Infura, no Alchemy — purely local.
    """

    def __init__(self):
        ganache_url = os.getenv("GANACHE_URL", "http://127.0.0.1:8545")
        self.w3 = Web3(Web3.HTTPProvider(ganache_url))

        if not self.w3.is_connected():
            raise ConnectionError(
                f"Cannot connect to Ganache at {ganache_url}. "
                "Run: npx ganache --port 8545 --deterministic"
            )

        # Load ABI
        abi_path = os.path.join(os.path.dirname(__file__), "contract_abi.json")
        with open(abi_path) as f:
            abi = json.load(f)

        contract_address = os.getenv("CONTRACT_ADDRESS")
        if not contract_address:
            raise ValueError("CONTRACT_ADDRESS not set in .env")

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )

        # Use account[0] from Ganache as the sender
        self.account = self.w3.eth.accounts[0]
        print(f"[Blockchain] Connected. Account: {self.account}")

    def log_incident(
        self,
        source_ip: str,
        attack_type: str,
        severity: int,
        is_blocked: bool,
        sqlite_incident_id: int
    ) -> dict:
        """
        Write an incident to the immutable ledger.
        Returns: { tx_hash, block_number, incident_hash }
        """
        forensics_uri = f"local://incident/{sqlite_incident_id}"

        tx = self.contract.functions.logIncident(
            source_ip,
            attack_type,
            severity,
            is_blocked,
            forensics_uri
        ).transact({
            "from": self.account,
            "gas": 200000
        })

        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return {
            "tx_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "status": "confirmed" if receipt.status == 1 else "failed",
            "gas_used": receipt.gasUsed,
        }

    def get_all_incidents(self) -> list:
        """Read all incidents from the chain for forensics display."""
        count = self.contract.functions.getIncidentCount().call()
        incidents = []
        for i in range(1, count + 1):
            raw = self.contract.functions.getIncident(i).call()
            incidents.append({
                "id": raw[0],
                "incident_hash": "0x" + raw[1].hex(),
                "timestamp": datetime.fromtimestamp(raw[2]).isoformat(),
                "source_ip": raw[3],
                "attack_type": raw[4],
                "severity": raw[5],
                "is_blocked": raw[6],
                "forensics_uri": raw[7],
            })
        return incidents
```

### 7.5 Forensics Storage Architecture

```
DUAL-STORAGE FORENSICS DESIGN (No external providers):

┌─────────────────────────────────────────────────────────────────┐
│               HOW FORENSICS WORKS IN GRAPHSENTINEL              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LAYER 1 — SQLite (Fast, Queryable)                            │
│  ┌───────────────────────────────────────────────┐             │
│  │ Table: incidents                              │             │
│  │ - id, source_ip, attack_type, threat_score   │             │
│  │ - timestamp, raw_flow_data (JSON blob)        │             │
│  │ - blockchain_tx_hash (FK to Layer 2)          │             │
│  │ - is_blocked, report_generated                │             │
│  │                                               │             │
│  │ Purpose: Fast queries, full-text search,      │             │
│  │ detailed flow logs that would be expensive    │             │
│  │ to store on-chain.                            │             │
│  └───────────────────────────────────────────────┘             │
│                        ↕ linked via incident ID                │
│  LAYER 2 — Ganache Blockchain (Tamper-Proof Proof)             │
│  ┌───────────────────────────────────────────────┐             │
│  │ IncidentLogger.sol                            │             │
│  │ - incident_hash (keccak256 fingerprint)       │             │
│  │ - source_ip, attack_type, severity            │             │
│  │ - timestamp (immutable block timestamp)       │             │
│  │ - forensics_uri → "local://incident/42"       │             │
│  │                                               │             │
│  │ Purpose: PROOF that the log existed at that  │             │
│  │ exact time and was NOT modified.              │             │
│  │ The keccak256 hash proves integrity.          │             │
│  └───────────────────────────────────────────────┘             │
│                                                                 │
│  VERIFICATION FLOW (viva demo proof):                          │
│  1. Show attack in UI → alert fires                            │
│  2. SQLite record created (id: 42)                             │
│  3. Blockchain tx fires → hash stored on Ganache               │
│  4. Demo: "Can we tamper with log 42?"                         │
│  5. Change SQLite → recompute hash → MISMATCH with chain       │
│  6. This proves tamper-proof integrity ✓                       │
└─────────────────────────────────────────────────────────────────┘

WHY NO INFURA/ALCHEMY?
- Ganache local chain is deterministic, always available
- No internet required during demo (avoids network failures)
- Free — no API key limits
- Instant transactions (no wait time)
- Full control over accounts and state
```

### 7.6 Hardhat Config

```javascript
// blockchain/hardhat.config.js — [Windows]
require("@nomicfoundation/hardhat-toolbox");
require('dotenv').config();

module.exports = {
  solidity: {
    version: "0.8.19",
    settings: {
      optimizer: { enabled: true, runs: 200 }
    }
  },
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,  // Ganache default chain ID
    }
  }
};
```

### 7.7 Week-by-Week Plan (Skanda)

| Week | Focus | Deliverable |
|------|-------|-------------|
| **W1** | Node.js, Hardhat, Ganache install + hardhat.config.js | `npx hardhat compile` works |
| **W2** | Write IncidentLogger.sol + unit tests | All test cases pass |
| **W3** | deploy.js script + Ganache deployment | Contract address obtained, ABI exported |
| **W4** | Write web3_client.py + test `log_incident()` | Python can write to chain |
| **W5** | Test `get_all_incidents()` + verify tamper-proof demo | Full read/write cycle works |
| **W6** | Hand off web3_client.py to Sairaj + backend integration test | blockchain_adapter.py works end-to-end |
| **W7** | Demo script: attack → tx hash appears in 2 seconds | Chain entries visible in frontend |
| **W8** | Demo hardening — restart Ganache cleanly before demo | Reliable startup procedure documented |

### 7.8 Risks and Failure Points (Skanda)

| Risk | Probability | Impact | Failure Scenario | Mitigation |
|------|------------|--------|-----------------|-----------|
| Ganache port 8545 already in use | **MEDIUM** | High | Deploy fails with ECONNREFUSED | Kill existing process: `npx kill-port 8545` |
| Contract not redeployed after Ganache restart | **HIGH** | Critical | Old CONTRACT_ADDRESS invalid | Script re-deploy at every demo start |
| Web3.py version mismatch with Ganache | **MEDIUM** | High | Transaction reverts | Use `web3==7.*` strictly with Ganache 7.x |
| ABI not updated after contract change | **HIGH** | High | Function calls fail silently | Re-run deploy.js after every Solidity edit |
| Gas limit too low | **LOW** | Medium | Transaction out of gas | Set `gas: 200000` (well above actual ~68k) |
| Ganache state lost between sessions | **MEDIUM** | Medium | All tx history gone | Use `--db ./ganache-data` for persistence |

---

## 👤 SECTION 8 — SATHVIK: ML IMPLEMENTATION PLAN

### 8.1 Environment Setup [Google Colab Primary]

```python
# STEP 1: Google Colab Setup — Run these in first cell of each notebook

# Enable GPU: Runtime → Change Runtime Type → T4 GPU
import torch
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU'}")
print(f"PyTorch: {torch.__version__}")

# STEP 2: Install dependencies in Colab
!pip install torch-geometric==2.5.0
!pip install torch-scatter torch-sparse \
  -f https://data.pyg.org/whl/torch-$(python -c "import torch; v=torch.__version__; print(v[:5])")+cu121.html

!pip install pandas==2.2.0 scikit-learn==1.5.0 networkx==3.3.0 \
             matplotlib seaborn imbalanced-learn

# STEP 3: Mount Google Drive (for saving checkpoints)
from google.colab import drive
drive.mount('/content/drive')

MODEL_SAVE_DIR = "/content/drive/MyDrive/GraphSentinel/models/"
import os
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
```

```bash
# WSL2 LOCAL TESTING SETUP (after Colab training)
# [WSL2 Ubuntu 22.04 — for local inference test]
cd /mnt/c/Projects/graphsentinel/ml
python -m venv .venv_ml
source .venv_ml/bin/activate
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
pip install torch-geometric==2.5.0 networkx==3.3.0 scikit-learn==1.5.0 pandas==2.2.0
# Test: python src/model.py  → should print model summary
```

### 8.2 CICIDS2017 Dataset — Specific Files to Download

```
DATASET STRATEGY: Download ONLY these 3 CSV files from:
https://www.unb.ca/cic/datasets/ids-2017.html
OR mirror: https://www.kaggle.com/datasets/cicdataset/cicids2017

FILES TO DOWNLOAD (do NOT download full dataset — only these):
┌─────────────────────────────────────────────────────────┐
│ FILE 1: Tuesday-WorkingHours.pcap_ISCX.csv  (~400MB)   │
│   Contains: FTP-Patator, SSH-Patator, BENIGN            │
│   We need: SSH-Patator rows only (+ sample of BENIGN)   │
│                                                         │
│ FILE 2: Wednesday-workingHours.pcap_ISCX.csv (~550MB)  │
│   Contains: DoS Slowloris, DoS Hulk, Heartbleed, BENIGN│
│   We need: DoS Hulk rows only (+ sample of BENIGN)      │
│                                                         │
│ FILE 3a: Friday-WorkingHours-Morning.pcap_ISCX.csv     │
│   Contains: Botnet ARES, BENIGN                         │
│   We need: BOTNET rows only                             │
│                                                         │
│ FILE 3b: Friday-WorkingHours-Afternoon-DDos.pcap_ISCX  │
│   Contains: DDoS, BENIGN                                │
│   We need: DDoS rows only                               │
│                                                         │
│ FILE 3c: Friday-WorkingHours-Afternoon-PortScan.pcap   │
│   Contains: PortScan, BENIGN                            │
│   We need: PortScan rows only                           │
└─────────────────────────────────────────────────────────┘

AFTER FILTERING (expected rows per class):
  DDoS:        ~128,000 rows
  PortScan:    ~158,000 rows
  Botnet:      ~1,956  rows  ← heavy class imbalance warning!
  SSH-Patator: ~5,897  rows
  DoS Hulk:    ~231,073 rows
  BENIGN:      ~50,000 rows  (random sample from all files)

TOTAL WORKING DATASET: ~575,000 rows
After preprocessing + graph conversion: much smaller graph
```

### 8.3 Multi-Phase Training Pipeline

```
PHASE 1 — DATA EXPLORATION (Notebook 01)
  Goal: Understand the 5 CSV files before touching anything
  Tasks:
    - Load each CSV with pd.read_csv()
    - Check column names (CICIDS2017 has 79 features)
    - Count class distribution: df['Label'].value_counts()
    - Plot class imbalance bar chart
    - Identify top 20 most informative features via correlation
    - Check for NaN/Inf values per column
  Output: EDA report markdown + class distribution chart

PHASE 2 — PREPROCESSING (Notebook 02)
  Goal: Clean data and select features for graph construction
  Tasks:
    - Load only the 5 target attack CSVs
    - Filter by Label: keep only 5 attack types + BENIGN
    - Drop NaN rows: df.dropna()
    - Drop infinite values: df.replace([np.inf, -np.inf], np.nan).dropna()
    - Drop duplicate rows: df.drop_duplicates()
    - Select 15 key features:
        'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
        'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
        'Fwd Packet Length Max', 'Bwd Packet Length Max',
        'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean',
        'Fwd IAT Total', 'Bwd IAT Total', 'SYN Flag Count',
        'RST Flag Count', 'Destination Port'
    - Also keep: 'Source IP', 'Destination IP', 'Label'
    - Binary encode: Label → 0 (BENIGN), 1 (MALICIOUS, all attacks)
    - StandardScaler on numeric features → save scaler.pkl
    - Handle class imbalance with RandomUnderSampler (BENIGN >> attacks)
  Output: cleaned_dataset.csv + scaler.pkl

PHASE 3 — GRAPH CONSTRUCTION (Notebook 03)
  Goal: Convert tabular flow data to PyG graph objects
  Tasks:
    - For each 5-minute time window:
        * Group flows by source/destination IP pairs
        * Build NetworkX DiGraph:
            - node = unique IP address
            - edge = (src_ip, dst_ip) with aggregated flow features
        * Compute 7 NODE FEATURES (aggregated per IP):
            1. out_degree (how many hosts this node connects to)
            2. in_degree  (how many hosts connect to this node)
            3. avg_packet_size = total_bytes / total_packets
            4. connection_rate = total_packets / window_duration
            5. port_entropy = -Σ p(port) * log2(p(port))  — detects port scan
            6. byte_asymmetry = (sent - received) / (sent + received + ε)
            7. syn_ratio = SYN_count / total_packets
        * Assign NODE LABEL: 1 if any edge from this node is malicious
        * Convert to PyG Data object
    - Split: train 70% / val 15% / test 15% (time-based split, not random)
  Output: List of PyG Data objects saved as processed_graphs.pt

PHASE 4 — GNN TRAINING (Notebook 04)
  Goal: Train GraphSAGE classifier on node-level attack detection
  Model: GraphSAGE (3 layers, mean aggregation, inductive)
  Tasks:
    - Define GraphSAGEClassifier (see model.py below)
    - DataLoader with batch_size=32
    - Optimizer: Adam, lr=0.001, weight_decay=5e-4
    - Loss: BCEWithLogitsLoss (with pos_weight for class imbalance)
    - Train for max 100 epochs
    - Early stopping: patience=15 on val_f1
    - Save best checkpoint at each val improvement
    - Plot loss + F1 curves every 10 epochs
  Output: best_model_checkpoint.pt

PHASE 5 — EVALUATION + EXPORT (Notebook 05)
  Goal: Final evaluation, export production files
  Tasks:
    - Load best checkpoint
    - Run on test set
    - Print full classification report (per class)
    - Generate confusion matrix
    - Compute AUC-ROC curve (binary: benign vs malicious)
    - If metrics below target → return to Phase 4 with adjustments
    - Export: torch.save(model.state_dict(), 'graphsage_weights.pt')
    - Export: pickle.dump(scaler, open('scaler.pkl', 'wb'))
    - Copy BOTH files to Google Drive → download to C:\Projects\graphsentinel\ml\models\
  Output: graphsage_weights.pt + scaler.pkl (PRODUCTION FILES)
```

### 8.4 GraphSAGE Model Architecture

```python
# ml/src/model.py — [WSL2 and Colab]
# THIS FILE IS SHARED: backend/app/services/inference_service.py imports it

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

class GraphSAGEClassifier(nn.Module):
    """
    GraphSAGE node classifier for cyber attack detection.
    Architecture: 3-layer GraphSAGE with residual connections
    Input: 7 node features (degree, packet_size, connection_rate, etc.)
    Output: 2 classes (benign=0, malicious=1)
    """

    def __init__(
        self,
        in_channels: int   = 7,    # MUST match preprocessing node feature count
        hidden_channels: int = 256,
        out_channels: int  = 2,    # binary: benign / malicious
        num_layers: int    = 3,
        dropout: float     = 0.3,
        aggr: str          = 'mean'
    ):
        super().__init__()
        self.num_layers = num_layers
        self.dropout = dropout

        self.convs = nn.ModuleList()
        self.bns   = nn.ModuleList()

        # Layer 1: in_channels → hidden
        self.convs.append(SAGEConv(in_channels, hidden_channels, aggr=aggr))
        self.bns.append(nn.BatchNorm1d(hidden_channels))

        # Layers 2..N-1: hidden → hidden
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels, aggr=aggr))
            self.bns.append(nn.BatchNorm1d(hidden_channels))

        # Layer N: hidden → out
        self.convs.append(SAGEConv(hidden_channels, out_channels, aggr=aggr))

    def forward(self, x, edge_index):
        for i, (conv, bn) in enumerate(zip(self.convs[:-1], self.bns)):
            x = conv(x, edge_index)
            x = bn(x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)

        # Final layer — no activation (logits for CrossEntropyLoss)
        x = self.convs[-1](x, edge_index)
        return x

    def predict_proba(self, x, edge_index):
        """Returns malicious probability for each node."""
        logits = self.forward(x, edge_index)
        return torch.softmax(logits, dim=1)[:, 1]  # prob of class 1 (malicious)
```

### 8.5 Optimal Performance Targets

```
═══════════════════════════════════════════════════════════════════
GRAPHSENTINEL — MINIMUM ACCEPTABLE MODEL PERFORMANCE
(For a credible 60-minute major project demo)
═══════════════════════════════════════════════════════════════════

METRIC              TARGET      CRITICAL MINIMUM    WHAT IT MEANS
─────────────────────────────────────────────────────────────────
Overall Accuracy    ≥ 92%       ≥ 88%               Most nodes classified correctly
Weighted F1         ≥ 0.88      ≥ 0.82              Balanced precision + recall
Per-class F1:
  DDoS              ≥ 0.90      ≥ 0.85              Most DDoS nodes caught
  PortScan          ≥ 0.87      ≥ 0.80              Port scan pattern identified
  SSH-Patator       ≥ 0.85      ≥ 0.78              Brute force detected
  DoS Hulk          ≥ 0.89      ≥ 0.83              HTTP flood recognized
  Botnet            ≥ 0.80      ≥ 0.72              C2 pattern detected *
AUC-ROC             ≥ 0.95      ≥ 0.90              Discrimination ability
False Positive Rate ≤ 5%        ≤ 10%               Normal nodes flagged as attack
Inference Latency   ≤ 200ms     ≤ 500ms             Real-time feel in demo
Model Size          ≤ 50MB      ≤ 100MB             Fast load at startup

* Botnet has fewest samples (1,956 rows) — hardest class.
  If Botnet F1 < 0.72, use SMOTE oversampling or weighted loss.

WHAT TO DO IF TARGETS NOT MET:
  Accuracy < 88%     → Retrain with higher dropout; check label noise
  F1 < 0.82          → Check class imbalance; apply RandomUnderSampler
  Botnet F1 < 0.72   → Use SMOTE on Botnet rows before training
  AUC < 0.90         → Check graph construction; port_entropy is key feature
  Latency > 500ms    → Reduce graph to top 20 nodes; batch inference

COLAB TRAINING EXPECTATIONS:
  - Convergence: typically by epoch 40-60
  - Training time on T4: ~15-25 minutes for full pipeline
  - Val F1 plateau: if no improvement for 15 epochs → stop early
  - Best checkpoint: save whenever val_f1 improves
═══════════════════════════════════════════════════════════════════
```

### 8.6 Week-by-Week Plan (Sathvik)

| Week | Focus | Deliverable |
|------|-------|-------------|
| **W1** | Colab setup + CICIDS2017 CSV download to Drive | All 5 CSVs on Google Drive, notebook running |
| **W2** | Phase 1 EDA + Phase 2 preprocessing | `cleaned_dataset.csv` + class distribution charts |
| **W3** | Phase 3 graph construction + node feature engineering | `processed_graphs.pt` — PyG objects ready |
| **W4** | Phase 4 training (epochs 1-100) + early stopping | Loss/F1 curves, best checkpoint saved |
| **W5** | Phase 5 evaluation — hit performance targets | All metrics meet minimum threshold |
| **W6** | Export `graphsage_weights.pt` + `scaler.pkl` → hand to Sairaj | Files in `ml/models/`, Sairaj confirms load |
| **W7** | Integration test: Sairaj loads weights, test inference on mock flows | Real predictions from real model |
| **W8** | Demo prep: pre-run notebook outputs, cache results | Offline fallback notebook ready |

### 8.7 Risks and Failure Points (Sathvik)

| Risk | Probability | Impact | Failure Scenario | Mitigation |
|------|------------|--------|-----------------|-----------|
| CIC website down / slow downloads | **HIGH** | High | Can't get CSVs | Use Kaggle mirror as backup; download early W1 |
| Botnet class imbalance (1,956 rows) | **HIGH** | Medium | Low Botnet F1 | SMOTE with imblearn; weighted loss |
| Colab session timeout during training | **HIGH** | Medium | Model not saved | Use Drive checkpoints + `torch.save` every 10 epochs |
| PyTorch Geometric install conflict | **MEDIUM** | High | Notebook fails | Pre-test exact wheel URL; pin version |
| graph_builder.py mismatches backend | **HIGH** | Critical | Backend inference fails | Share EXACT node feature list with Sairaj in docs/ |
| Feature column names differ in CSVs | **MEDIUM** | Medium | KeyError in preprocessing | Run df.columns in notebook W1 before any transform |
| model.py not importable in backend | **MEDIUM** | High | weights.pt won't load | Test import in WSL2 before handing off |

---

## 📡 SECTION 9 — FROZEN API CONTRACTS
> **These endpoints CANNOT be changed without team consensus. All members design their code around these exact shapes.**

```
BASE URL: http://localhost:8000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 1: POST /api/v1/analyze
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj (backend)
Caller: Internal (mininet monitor calls this)

Request body:
{
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
}

Response 200:
{
  "predictions": {
    "10.0.0.2": 0.94,
    "10.0.0.1": 0.08
  },
  "incidents_created": ["incident-id-42"],
  "healing_triggered": ["10.0.0.2"],
  "graph_snapshot": { /* GraphResponse shape */ }
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 2: GET /api/v1/alerts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj | Caller: Susheep (frontend polling)

Query params: ?limit=50&severity=critical

Response 200:
{
  "alerts": [ /* Array of AlertRecord */ ],
  "total": 7
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 3: GET /api/v1/blocked
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj | Caller: Susheep (frontend)

Response 200:
{
  "blocked_ips": [
    {
      "ip": "10.0.0.5",
      "blocked_at": "2024-01-15T14:31:50Z",
      "reason": "GNN_DETECTED",
      "attack_type": "SSHBrute",
      "threat_score": 0.88
    }
  ]
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 4: POST /api/v1/block
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj | Caller: Susheep (manual block button in UI)

Request body: { "ip": "10.0.0.2", "reason": "MANUAL_OVERRIDE" }
Response 200: { "status": "blocked", "ip": "10.0.0.2" }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 5: GET /api/v1/forensics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj + Skanda | Caller: Susheep (forensics modal)

Response 200:
{
  "incidents": [ /* SQLite records */ ],
  "blockchain_records": [ /* Ganache on-chain records */ ],
  "total_on_chain": 2,
  "chain_id": 1337,
  "contract_address": "0x..."
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 6: POST /api/v1/blockchain/store
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj calls this internally after incident confirmed

Request body:
{
  "source_ip": "10.0.0.2",
  "attack_type": "DDoS",
  "severity": 9,
  "is_blocked": false,
  "sqlite_incident_id": 42
}

Response 200:
{
  "tx_hash": "0x4f3a...",
  "block_number": 142,
  "status": "confirmed",
  "gas_used": 68432
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINT 7: GET /api/v1/graph  [Additional — for initial load]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Owner: Sairaj | Caller: Susheep (initial page load)

Response 200: { GraphResponse shape as defined in Section 6.9 }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEBSOCKET EVENTS (Socket.IO — ws://localhost:8000)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Event: 'graph_update'    → every 5 seconds → GraphResponse
Event: 'alert'           → on new incident  → AlertRecord
Event: 'healing_triggered' → on block action → HealingEvent
```

---

## 🔗 SECTION 10 — INTEGRATION CHECKLIST

### Week-by-Week Integration Milestones

```
INTEGRATION HANDOFF SCHEDULE:

WEEK 3 — Sathvik → ALL:
  ✓ Share exact node_feature_list.txt (7 features, exact names + order)
  ✓ Share model.py (GraphSAGEClassifier class)
  ✓ Document expected input shape: x.shape = (N, 7), edge_index.shape = (2, E)

WEEK 4 — Skanda → Sairaj:
  ✓ Hand off blockchain/web3_bridge/web3_client.py
  ✓ Hand off blockchain/web3_bridge/contract_abi.json
  ✓ Write CONTRACT_ADDRESS + GANACHE_URL to shared .env.local

WEEK 5 — Sairaj → Susheep (CRITICAL):
  ✓ Backend running on localhost:8000
  ✓ GET /api/v1/graph returns real graph (even with mock/random threats)
  ✓ WebSocket 'graph_update' fires every 5 seconds
  → Susheep: replace MOCK_GRAPH_DATA with real API call
  → Susheep: connect useWebSocket hook to real backend

WEEK 6 — Sathvik → Sairaj (CRITICAL):
  ✓ graphsage_weights.pt + scaler.pkl placed in ml/models/
  ✓ Sairaj confirms: inference_service.py loads weights without error
  ✓ Run smoke test: POST /api/v1/analyze with 5 mock flows → real scores

WEEK 7 — FULL INTEGRATION TEST:
  ✓ Start Ganache → Deploy contract → note ADDRESS
  ✓ Start FastAPI backend → confirm blockchain_adapter connects
  ✓ Start Mininet → verify flow data reaches backend
  ✓ Start React frontend → graph appears with real data
  ✓ Trigger DDoS attack → watch all 4 systems respond
  ✓ Verify: blockchain TX hash appears in frontend within 3 seconds

WEEK 8 — DEMO HARDENING:
  ✓ Pre-generate attack logs for fallback
  ✓ Test full restart sequence (all 4 systems from cold start)
  ✓ Prepare demo script (see Section 11)
```

### Integration Debug Checklist

```bash
# Run these in order to verify each integration point:

# 1. Is Ganache up?
curl http://127.0.0.1:8545 -d '{"method":"eth_blockNumber","id":1}' -H "Content-Type: application/json"
# Expected: {"result":"0x..."}

# 2. Is FastAPI up?
curl http://localhost:8000/api/v1/alerts
# Expected: {"alerts":[],"total":0}

# 3. Is CORS working? (From browser console)
fetch('http://localhost:8000/api/v1/alerts').then(r=>r.json()).then(console.log)
# Expected: no CORS error

# 4. Is WebSocket connecting? (Browser console)
const s = io('http://localhost:8000'); s.on('connect', () => console.log('WS OK'))
# Expected: "WS OK"

# 5. Are weights loaded?
# In backend terminal, check for:
# "[Inference] Loaded GraphSAGE weights from ../ml/models/graphsage_weights.pt"

# 6. Is Mininet producing flows?
# In backend terminal, check for:
# "[Monitor] Extracted 23 flows from Mininet at 14:32:01"
```

---

## 🎬 SECTION 11 — 60-MINUTE DEMO EXECUTION SCRIPT

```
PRE-DEMO (15 min before panel arrives):
  [ ] Terminal 1 (Windows): cd C:\Projects\graphsentinel\blockchain
                             npx ganache --port 8545 --deterministic
                             npx hardhat run scripts/deploy.js --network localhost
  [ ] Terminal 2 (WSL2):    cd /mnt/c/Projects/graphsentinel
                             sudo mn --controller=ovs  (pre-start Mininet)
  [ ] Terminal 3 (WSL2):    cd backend && source .venv/bin/activate
                             uvicorn app.main:app --reload
                             (confirm: "Loaded GraphSAGE weights ✓")
                             (confirm: "Blockchain connected ✓")
  [ ] Terminal 4 (Windows): cd C:\Projects\graphsentinel\frontend
                             npm run dev
                             → open http://localhost:5173 (check 3D graph loads)

DEMO FLOW (60 minutes):

[0:00 - 5:00]   INTRODUCTION
  → Explain GraphSentinel: detection + autonomous response + blockchain proof
  → Show dashboard overview: 10 nodes, all green, 0 threats

[5:00 - 15:00]  NORMAL TRAFFIC DEMONSTRATION
  → Show live 3D graph updating every 5s
  → Point to edge particles (traffic flow animation)
  → Show system health: 100%
  → Show empty blockchain ledger: "No incidents yet"

[15:00 - 25:00] ATTACK DEMONSTRATION — DDoS
  → Run: python mininet/topologies/attack_scripts/ddos_attack.py
  → Watch live: node 10.0.0.2 turns YELLOW (suspicious)
  → 5 seconds later: turns RED (malicious, threat: 94%)
  → Alert appears in AlertPanel
  → Self-healing fires: node turns BLUE, edges cut, cage appears
  → Show SelfHealStatus: "Isolated in 245ms, 6 edges severed"
  → Show Blockchain panel: TX hash appears with green ✓
  → System health recovers: 88% → 94%

[25:00 - 35:00] ATTACK DEMONSTRATION — PortScan + SSH Brute
  → Run: python mininet/topologies/attack_scripts/portscan_attack.py
  → Show suspicious amber node for port scan (threshold not hit)
  → Run: python mininet/topologies/attack_scripts/ssh_brute.py
  → Watch detection + isolation

[35:00 - 45:00] BLOCKCHAIN FORENSICS DEEP DIVE
  → Show forensics modal: all incidents with TX hashes
  → TAMPER-PROOF DEMO:
      • Open SQLite: show incident record #42
      • Explain: "What if attacker deletes this log?"
      • Show blockchain: hash still on chain = proof it existed
      • Change SQLite record (demo) → hash mismatch = tampered!
  → This is the core research novelty

[45:00 - 55:00] SELF-HEALING + RECOVERY
  → Show unblock: POST /api/v1/block with unblock action
  → Node transitions: BLUE → GREEN
  → Edges re-appear in graph
  → System health: full recovery
  → Explain: "System heals itself — no admin required"

[55:00 - 60:00] QUESTION TIME
  → Point to GraphSAGE architecture slide
  → Show model metrics: F1=0.89, AUC=0.96
  → Have fallback pre-recorded demo video ready
```

---

## 🛟 SECTION 12 — FALLBACK PLAN (VIVA-SAFE)

```
IF COMPONENT FAILS DURING DEMO:

FALLBACK TIER 1 — Mock data always ready:
  • Frontend can run on MOCK_GRAPH_DATA from mockData.js
  • Enable via: localStorage.setItem('USE_MOCK', 'true')
  • The UI looks IDENTICAL — no one can tell

FALLBACK TIER 2 — Pre-recorded demo:
  • Record full 10-minute attack demo in W8
  • Keep as: docs/fallback_demo.mp4
  • Play on second monitor if live demo fails

FALLBACK TIER 3 — Static slides:
  • System architecture diagram
  • Confusion matrix + AUC-ROC curve from training
  • Blockchain TX screenshot

SPECIFIC COMPONENT FALLBACKS:
  Mininet fails     → Use pre-captured flow CSV fed to backend manually
  Blockchain fails  → Show pre-generated TX hashes from SQLite mock
  ML model fails    → Use hardcoded threat scores (0.94 for attacker node)
  WebSocket fails   → Fall back to polling GET /api/v1/graph every 3s
  Backend fails     → Switch frontend to MOCK mode (localStorage flag)

PRE-DEMO CHECKLIST:
  [ ] All 3 fallback options tested and working
  [ ] graphsage_weights.pt backed up on USB + Google Drive
  [ ] ganache-data/ directory saved (so chain history persists)
  [ ] Mock API file updated with realistic final data
  [ ] Demo video recorded and accessible offline
```

---

## 📊 SECTION 13 — FULL RISK MATRIX (ALL MEMBERS)

| # | Risk | Member | Probability | Impact | Failure Rate | Mitigation |
|---|------|--------|-------------|--------|-------------|-----------|
| 1 | Mininet won't start on WSL2 | Sairaj | **HIGH** | Critical | 40% without prep | Install OVS in W1, test daily |
| 2 | CICIDS2017 CIC server down | Sathvik | **HIGH** | High | 30% on CIC directly | Use Kaggle mirror — download in W1 |
| 3 | API contract mismatch at integration | All | **HIGH** | Critical | 60% without freeze | Freeze API in W2, mock responses first |
| 4 | weights.pt load path wrong | Sairaj+Sathvik | **HIGH** | Critical | 50% first try | Use absolute env paths, test in W6 |
| 5 | 3D graph frame drops during demo | Susheep | **MEDIUM** | High | 35% unoptimized | Cap to 10 nodes, reduce particles |
| 6 | Ganache address changes on restart | Skanda | **HIGH** | High | 70% without persistence | `--db` flag or redeploy script |
| 7 | Botnet class too small → poor F1 | Sathvik | **HIGH** | Medium | 45% without SMOTE | SMOTE oversample in Phase 2 |
| 8 | WebSocket CORS block | Susheep+Sairaj | **MEDIUM** | High | 30% first try | Test Vite proxy in W5 together |
| 9 | Self-healing iptables silently fails | Sairaj | **MEDIUM** | High | 25% without testing | Manual iptables test before demo |
| 10 | PyG install fails | Sairaj+Sathvik | **HIGH** | Critical | 50% first try | Use exact wheel URL from PyG docs |
| 11 | Team integration collapse in W7 | All | **MEDIUM** | Critical | 25% without discipline | Weekly syncs, freeze API W2 |
| 12 | Colab session timeout mid-training | Sathvik | **HIGH** | Medium | 60% long sessions | Save checkpoint every 10 epochs |

---

## 🔖 SECTION 14 — GITHUB WORKFLOW

```bash
# PROTECTED BRANCHES:
# main      → demo-ready only (never push directly)
# develop   → integration branch (PR required)

# FEATURE BRANCHES (one per member):
git checkout -b feature/sairaj-backend
git checkout -b feature/susheep-frontend
git checkout -b feature/skanda-blockchain
git checkout -b feature/sathvik-ml

# WEEKLY INTEGRATION:
git checkout -b integration/week-3
# Each member merges their feature into integration/week-3
# Test together → merge to develop → weekly demo

# COMMIT CONVENTION:
# [BACKEND]  feat: add self-healing engine
# [FRONTEND] feat: implement 3D graph with react-force-3d
# [CHAIN]    feat: deploy IncidentLogger to Ganache
# [ML]       feat: complete phase 2 preprocessing

# NEVER: git push origin main  ← protected
# NEVER: git push origin develop ← PR required

# .gitignore additions (critical):
# ml/models/*.pt
# ml/models/*.pkl
# datasets/
# backend/graphsentinel.db
# blockchain/ganache-data/
# **/.env
# **/node_modules/
# **/__pycache__/
# **/.venv/
```

---

## 🏷️ SECTION 15 — SHARED ENVIRONMENT VARIABLES

```bash
# Copy this to each member's local .env file
# .env.shared.example — COMMIT THIS (no secrets)
# .env              — DO NOT COMMIT

# ── Shared ────────────────────────────────────────────────
BACKEND_URL=http://localhost:8000
GANACHE_URL=http://127.0.0.1:8545
CONTRACT_ADDRESS=        # Filled by Skanda after deploy

# ── Backend (Sairaj) ──────────────────────────────────────
WEIGHTS_PATH=../ml/models/graphsage_weights.pt
SCALER_PATH=../ml/models/scaler.pkl
SQLITE_PATH=./graphsentinel.db
THREAT_THRESHOLD=0.75
POLL_INTERVAL_SECONDS=5
MININET_CONTROLLER_IP=127.0.0.1

# ── Frontend (Susheep) ────────────────────────────────────
VITE_BACKEND_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_USE_MOCK=false        # Set to true for offline dev

# ── Blockchain (Skanda) ───────────────────────────────────
GANACHE_ACCOUNTS=5
GANACHE_DETERMINISTIC=true
GANACHE_CHAIN_ID=1337
GANACHE_DB_PATH=./ganache-data

# ── ML (Sathvik) ──────────────────────────────────────────
COLAB_DRIVE_PATH=/content/drive/MyDrive/GraphSentinel/
NODE_FEATURE_COUNT=7
NUM_ATTACK_CLASSES=5
TRAIN_SPLIT=0.70
VAL_SPLIT=0.15
TEST_SPLIT=0.15
```

---

*GraphSentinel Master Prompt v1.0 — Generated for team: Sairaj, Susheep, Skanda, Sathvik*  
*All constraints, versions, and contracts in this document are FROZEN.*  
*Any changes require team consensus and version bump in this document.*
