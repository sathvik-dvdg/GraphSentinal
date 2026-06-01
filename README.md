# 🛡️ GraphSentinel
### A Self-Healing Cyber Defense System using Graph Deep Learning and Immutable Audit Trails

> **Team:** Sairaj (Backend) · Susheep (Frontend) · Skanda (Blockchain) · Sathvik (ML)  
> **Type:** Major Project Demo (60-minute live demonstration)  
> **Status:** Local machine only — no cloud, no deployment

---

## What is GraphSentinel?

GraphSentinel is an autonomous cyber defense framework that:

1. **Detects** abnormal communication patterns using GraphSAGE (Graph Neural Network)
2. **Responds** by automatically isolating malicious nodes (Self-Healing)
3. **Records** verified attack events on a tamper-proof local blockchain ledger
4. **Visualizes** everything in a real-time 3D React dashboard

```
SYSTEM FLOW:
  Mininet (10-host simulation)
       ↓ network flows every 5s
  FastAPI Backend
       ↓ graph construction
  GraphSAGE GNN (PyTorch)
       ↓ threat scores per node
  Self-Healing Engine
       ↓ isolate malicious node
  Ganache Blockchain
       ↓ tamper-proof TX hash
  React 3D Dashboard ← WebSocket ← all of the above
```

---

## Team Responsibilities

| Member | Role | Primary Tech | Works In |
|--------|------|-------------|---------|
| **Sairaj** | Backend | FastAPI, Mininet, SQLite | WSL2 Ubuntu |
| **Susheep** | Frontend | React, Three.js, Cytoscape | Windows |
| **Skanda** | Blockchain | Solidity, Hardhat, Ganache | Windows |
| **Sathvik** | ML/GNN | PyTorch, PyG, Colab | Google Colab |

---

## Quick Start (Full System)

> Run these in **exactly this order**. Each step in a separate terminal.

### Prerequisites (one-time setup)
```bash
# Windows: Node.js 20 LTS installed
# WSL2: Ubuntu 22.04 with Python 3.10.11 via pyenv
# See each member's plan in docs/ for full setup
```

### Step 1 — Start Blockchain [Windows Terminal 1]
```powershell
cd C:\Projects\graphsentinel\blockchain
npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data
# Wait: "Listening on 127.0.0.1:8545"
```

### Step 2 — Deploy Contract [Windows Terminal 2]
```powershell
# Only needed first time or after full Ganache reset
cd C:\Projects\graphsentinel\blockchain
npx hardhat run scripts/deploy.js --network localhost
# Output: "✅ CONTRACT_ADDRESS written to backend/.env"
```

### Step 3 — Start Backend [WSL2 Terminal 1]
```bash
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
# Wait for:
#   [DB] SQLite initialized ✓
#   [ML] GraphSAGE weights loaded ✓
#   [Blockchain] Ganache connected ✓
```

### Step 4 — Start Mininet [WSL2 Terminal 2]
```bash
sudo python3 /mnt/c/Projects/graphsentinel/mininet/topologies/base_topology.py
# Wait: "GraphSentinel network READY"
```

### Step 5 — Start Frontend [Windows Terminal 3]
```powershell
cd C:\Projects\graphsentinel\frontend
npm run dev
# Open: http://localhost:5173
```

### Step 6 — Trigger Demo Attack [WSL2 Terminal 3]
```bash
sudo python3 /mnt/c/Projects/graphsentinel/mininet/topologies/attack_scripts/ddos_attack.py
# Watch: node 10.0.0.2 turns RED → BLUE in dashboard within 10s
```

---

## Repository Structure

```
graphsentinel/
├── backend/         ← Sairaj: FastAPI, GNN inference, self-healing
├── frontend/        ← Susheep: React dashboard, 3D visualization
├── blockchain/      ← Skanda: Solidity contract, Ganache, Web3.py
├── ml/              ← Sathvik: CICIDS2017, GraphSAGE training
├── mininet/         ← Sairaj: topology + attack scripts
├── docs/            ← Shared: API contracts, schemas, member plans
├── datasets/        ← GITIGNORED: local CSV files only
├── .env.shared.example
├── .gitignore
└── README.md        ← You are here
```

---

## API Reference (Frozen)

| Method | Endpoint | Description | Owner |
|--------|----------|-------------|-------|
| `GET` | `/api/v1/graph` | Current network graph | Sairaj |
| `GET` | `/api/v1/alerts` | Recent threat alerts | Sairaj |
| `GET` | `/api/v1/blocked` | Currently blocked IPs | Sairaj |
| `POST` | `/api/v1/block` | Block/unblock IP manually | Sairaj |
| `GET` | `/api/v1/forensics` | SQLite + blockchain records | Sairaj+Skanda |
| `POST` | `/api/v1/blockchain/store` | Write incident to chain | Sairaj+Skanda |

**WebSocket events** (all emitted by backend):
- `graph_update` — full graph every 5 seconds
- `alert` — new incident detected
- `healing_triggered` — node isolation event

---

## Technology Stack

```
Backend:     Python 3.10.11 | FastAPI 0.115 | PyTorch 2.4 | PyG 2.5
             NetworkX 3.3 | SQLite | python-socketio | Web3.py 7
             Mininet 2.3 | Open vSwitch | Scapy 2.5

Frontend:    React 18 | Vite 5 | react-force-graph-3d
             @react-three/fiber | Cytoscape.js | Recharts
             Framer Motion | Tailwind CSS | socket.io-client

Blockchain:  Solidity 0.8.19 | Hardhat 2.22 | Ganache 7.9
             ethers.js 6 | Web3.py 7

ML:          PyTorch 2.4 | PyTorch Geometric 2.5 | scikit-learn 1.5
             CICIDS2017 dataset | GraphSAGE (3-layer, mean aggregation)
             Google Colab (T4/A100 GPU for training)

OS:          Windows 11 (host) + WSL2 Ubuntu 22.04 (backend/ML)
```

---

## 5 Attack Types Detected

| Attack | Source File | Key Signal | CICIDS2017 File |
|--------|------------|-----------|----------------|
| **DDoS** | Friday-Afternoon-DDos.csv | Extreme connection_rate | Friday AM/PM |
| **PortScan** | Friday-Afternoon-PortScan.csv | High port_entropy | Friday PM |
| **SSH-Patator** | Tuesday.csv | High syn_ratio + port 22 | Tuesday |
| **Botnet** | Friday-Morning.csv | byte_asymmetry + C2 ports | Friday AM |
| **DoS Hulk** | Wednesday.csv | HTTP flood + port 80 | Wednesday |

---

## Important Files

| File | Purpose |
|------|---------|
| `docs/API_CONTRACTS.md` | Frozen API shapes — read before building |
| `docs/DATA_SCHEMAS.md` | All JSON schemas shared between members |
| `docs/INTEGRATION_GUIDE.md` | How to connect all 4 systems |
| `docs/SAIRAJ_BACKEND_PLAN.md` | Backend week-by-week implementation |
| `docs/SUSHEEP_FRONTEND_PLAN.md` | Frontend week-by-week implementation |
| `docs/SKANDA_BLOCKCHAIN_PLAN.md` | Blockchain week-by-week implementation |
| `docs/SATHVIK_ML_PLAN.md` | ML/GNN week-by-week implementation |
| `GRAPHSENTINEL_MASTER_PROMPT.md` | God-tier AI IDE master prompt |

---

## Git Workflow

```bash
# Branch naming:
feature/sairaj-backend
feature/susheep-frontend
feature/skanda-blockchain
feature/sathvik-ml

# Weekly integration:
integration/week-1  →  integration/week-8

# Protected: main, develop (PR required)
# Never: git push origin main

# Commit convention:
[BACKEND]  feat: add self-healing engine
[FRONTEND] feat: implement 3D force graph
[CHAIN]    feat: deploy IncidentLogger contract
[ML]       feat: complete GraphSAGE training
```

---

## Environment Variables

Copy `.env.shared.example` to `.env` in each subdirectory and fill in values:

```bash
# Required in backend/.env
WEIGHTS_PATH=../ml/models/graphsage_weights.pt
SCALER_PATH=../ml/models/scaler.pkl
CONTRACT_ADDRESS=<from Skanda's deploy.js>
GANACHE_URL=http://127.0.0.1:8545
THREAT_THRESHOLD=0.75

# Required in frontend/.env
VITE_BACKEND_URL=http://localhost:8000
VITE_USE_MOCK=false

# Required in blockchain/.env
CONTRACT_ADDRESS=<filled automatically by deploy.js>
GANACHE_URL=http://127.0.0.1:8545
```

---

## Demo Fallback

If any component fails during the 60-minute demo:
- Frontend can run on mock data (`VITE_USE_MOCK=true`) — UI looks identical
- Pre-recorded demo video: `docs/fallback_demo.mp4`
- Detailed fallback protocol: see `docs/INTEGRATION_GUIDE.md` Section 9

---

*GraphSentinel — Major Project | Built with FastAPI + PyTorch Geometric + Hardhat + React*
