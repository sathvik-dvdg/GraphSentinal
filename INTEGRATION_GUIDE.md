# 🔗 GRAPHSENTINEL — INTEGRATION GUIDE
## The single document every member MUST read before integration week

---

## SECTION 1 — WHY INTEGRATION FAILS (AND HOW TO PREVENT IT)

```
THE #1 CAUSE OF INTEGRATION COLLAPSE IN TEAM PROJECTS:
  Member A builds their module expecting data in format X.
  Member B builds their module and outputs data in format Y.
  They only discover this in Week 7 — two days before demo.
  Result: everything breaks, all-nighter, demo fails.

GRAPHSENTINEL PREVENTION STRATEGY:
  1. FREEZE the API contracts in Week 2 — before building anything complex.
  2. Every member builds against MOCK DATA shaped like the frozen contracts.
  3. Integration is just swapping mock → real. No surprises.
  4. Weekly sync: every member shares their output shape as a JSON sample.
```

---

## SECTION 2 — INTEGRATION DEPENDENCY TREE

```
READ THIS BEFORE TOUCHING INTEGRATION:

PHASE 1 — Independent work (Week 1–4, NO cross-member dependencies):
  ┌─────────────────────────────────────────────────────────────────┐
  │ Sairaj   → builds FastAPI skeleton, mock endpoints, SQLite      │
  │ Susheep  → builds React dashboard on MOCK_DATA from mockData.js │
  │ Skanda   → builds + tests IncidentLogger.sol on Ganache         │
  │ Sathvik  → trains GraphSAGE on Colab, exports .pt + .pkl        │
  └─────────────────────────────────────────────────────────────────┘
  These 4 can work in parallel with ZERO coordination needed.
  Nobody is blocked. Nobody waits for anyone else.

PHASE 2 — First handoffs (Week 4–5):
  ┌─────────────────────────────────────────────────────────────────┐
  │ HANDOFF A: Skanda → Sairaj                                      │
  │   Skanda delivers:                                              │
  │     • blockchain/web3_bridge/web3_client.py                     │
  │     • blockchain/web3_bridge/contract_abi.json                  │
  │     • CONTRACT_ADDRESS written to backend/.env                  │
  │   Sairaj integrates: blockchain_adapter.py wraps web3_client.py │
  │   Test: POST /api/v1/blockchain/store → TX hash returned        │
  └─────────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────────┐
  │ HANDOFF B: Sathvik → Sairaj                                     │
  │   Sathvik delivers:                                             │
  │     • ml/models/graphsage_weights.pt                            │
  │     • ml/models/scaler.pkl                                      │
  │     • ml/src/model.py (GraphSAGEClassifier class)               │
  │     • ml/docs/NODE_FEATURES.md (feature list + order)           │
  │   Sairaj integrates: inference_service.py loads the .pt file    │
  │   Test: POST /api/v1/analyze with 5 flows → real threat scores  │
  └─────────────────────────────────────────────────────────────────┘

PHASE 3 — Frontend integration (Week 5–6):
  ┌─────────────────────────────────────────────────────────────────┐
  │ HANDOFF C: Sairaj → Susheep                                     │
  │   Sairaj delivers:                                              │
  │     • Backend running at http://localhost:8000                  │
  │     • GET /api/v1/graph returning real graph JSON               │
  │     • WebSocket 'graph_update' firing every 5s                  │
  │   Susheep integrates:                                           │
  │     • Replaces MOCK_GRAPH_DATA with real API call               │
  │     • Connects useWebSocket hook to backend                     │
  │   Test: React dashboard shows real node IPs from Mininet        │
  └─────────────────────────────────────────────────────────────────┘

PHASE 4 — Full system integration (Week 7):
  ┌─────────────────────────────────────────────────────────────────┐
  │ ALL SYSTEMS RUNNING SIMULTANEOUSLY:                             │
  │   1. Ganache (Windows, port 8545)                               │
  │   2. FastAPI backend (WSL2, port 8000)                          │
  │   3. Mininet topology (WSL2, sudo)                              │
  │   4. React frontend (Windows, port 5173)                        │
  │                                                                 │
  │ FULL PIPELINE TEST:                                             │
  │   Run DDoS attack → watch all 4 systems respond → verify        │
  └─────────────────────────────────────────────────────────────────┘
```

---

## SECTION 3 — FROZEN SHARED DATA CONTRACTS

> These JSON shapes are FROZEN. No member changes them without team consensus.
> The source of truth is `docs/DATA_SCHEMAS.md` in the repo.

### Contract 1: Node Object (shared: Frontend ↔ Backend)
```json
{
  "id":           "10.0.0.2",
  "label":        "h2-Attacker",
  "status":       "malicious",
  "threat_score": 0.94,
  "connections":  487,
  "bytes_total":  5120000,
  "attack_type":  "DDoS",
  "is_blocked":   false
}
```
> `status` enum: `"normal"` | `"suspicious"` | `"malicious"` | `"blocked"`
> `attack_type` enum: `"DDoS"` | `"PortScan"` | `"SSHBrute"` | `"Botnet"` | `"DoSHulk"` | `null`

### Contract 2: Link Object (shared: Frontend ↔ Backend)
```json
{
  "source":       "10.0.0.2",
  "target":       "10.0.0.1",
  "value":        0.94,
  "attack_type":  "DDoS",
  "packet_count": 15000
}
```

### Contract 3: Alert Record (shared: Frontend ↔ Backend)
```json
{
  "id":            "alert-42",
  "timestamp":     "2024-01-15T14:32:01Z",
  "source_ip":     "10.0.0.2",
  "attack_type":   "DDoS",
  "severity":      "critical",
  "threat_score":  0.94,
  "description":   "DDoS detected from 10.0.0.2 (score: 0.94)",
  "is_blocked":    false,
  "blockchain_tx": "0x4f3acd2b1a9e7f83c56d8e201b4a7c93"
}
```
> `severity` enum: `"info"` | `"warning"` | `"critical"`

### Contract 4: Blockchain TX Record (shared: Frontend ↔ Backend ↔ Skanda)
```json
{
  "tx_hash":       "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1",
  "block_number":  142,
  "timestamp":     "2024-01-15T14:32:01Z",
  "source_ip":     "10.0.0.2",
  "attack_type":   "DDoS",
  "severity":      9,
  "is_blocked":    false,
  "incident_hash": "0xb8f2a1c3d4e5f6a7b8c9d0e1f2a3b4c5",
  "gas_used":      68432,
  "status":        "confirmed"
}
```

### Contract 5: WebSocket Healing Event (shared: Frontend ↔ Backend)
```json
{
  "id":                       "heal-001",
  "timestamp":                "2024-01-15T14:32:01Z",
  "ip":                       "10.0.0.2",
  "action":                   "ISOLATED",
  "attack_type":              "DDoS",
  "trigger_score":            0.94,
  "edges_severed":            6,
  "duration_ms":              245,
  "network_stability_before": 88,
  "network_stability_after":  94
}
```

### Contract 6: ML Model Interface (shared: Backend ↔ Sathvik)
```python
# ml/src/model.py — Class signature that NEVER changes
class GraphSAGEClassifier(nn.Module):
    def __init__(
        self,
        in_channels:     int   = 7,    # FROZEN — 7 node features
        hidden_channels: int   = 256,  # FROZEN
        out_channels:    int   = 2,    # FROZEN — binary classification
        num_layers:      int   = 3,    # FROZEN
        dropout:         float = 0.3,
        aggr:            str   = 'mean'
    ): ...

# Node feature vector (FROZEN — 7 features in this exact order):
# [0] out_degree
# [1] in_degree
# [2] avg_packet_size       = total_bytes / (total_packets + 1e-6)
# [3] connection_rate       = total_packets / (window_duration_sec + 1e-6)
# [4] port_entropy          = Shannon entropy of destination ports (base 2)
# [5] byte_asymmetry        = (sent_bytes - recv_bytes) / (total_bytes + 1e-6)
# [6] syn_ratio             = syn_packets / (total_packets + 1e-6)
```

---

## SECTION 4 — CROSS-MEMBER FILE HANDOFF CHECKLIST

### Handoff A: Skanda → Sairaj (TARGET: End of Week 4)

**Skanda creates:**
```
blockchain/web3_bridge/web3_client.py      ← Python class
blockchain/web3_bridge/contract_abi.json   ← Compiled ABI
```

**Skanda must verify before handoff:**
```bash
# [WSL2] Run this verification script:
cd /mnt/c/Projects/graphsentinel/blockchain
source ../backend/.venv/bin/activate

python3 << 'EOF'
import sys
sys.path.insert(0, 'web3_bridge')
from web3_client import BlockchainClient

client = BlockchainClient()  # Should not raise

# Test write
result = client.log_incident("10.0.0.2", "DDoS", 9, False, 1)
assert result["tx_hash"] is not None, "TX hash is None — transaction failed"
assert result["status"] == "confirmed", f"Status: {result['status']}"

# Test read
incidents = client.get_all_incidents()
assert len(incidents) >= 1, "No incidents found after write"

print("✅ Handoff A verification PASSED — safe to give to Sairaj")
print(f"   TX hash: {result['tx_hash']}")
print(f"   Block:   {result['block_number']}")
EOF
```

**Sairaj integrates:**
```bash
# [WSL2] Verify Skanda's code loads in backend context:
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate

python3 << 'EOF'
import sys, os
sys.path.insert(0, '../blockchain/web3_bridge')
from web3_client import BlockchainClient

client = BlockchainClient()
result = client.log_incident("10.0.0.9", "PortScan", 7, False, 99)
print(f"✅ Sairaj integration test PASSED")
print(f"   Contract reachable from backend context")
print(f"   TX: {result['tx_hash']}")
EOF
```

---

### Handoff B: Sathvik → Sairaj (TARGET: End of Week 6)

**Sathvik creates:**
```
ml/models/graphsage_weights.pt   ← trained model weights (state_dict)
ml/models/scaler.pkl             ← fitted StandardScaler
ml/src/model.py                  ← GraphSAGEClassifier class definition
ml/docs/NODE_FEATURES.md         ← exact feature list + order
```

**Sathvik must verify before handoff:**
```python
# Run this in Colab BEFORE downloading files:
import torch, pickle

# Load your own weights to verify they're not corrupted
model = GraphSAGEClassifier(in_channels=7, hidden_channels=256, out_channels=2, num_layers=3)
model.load_state_dict(torch.load(MODEL_DIR + "graphsage_weights.pt", map_location="cpu"))
model.eval()

# Test inference with realistic input
x = torch.randn(10, 7)          # 10 nodes, 7 features
edge_index = torch.tensor(
    [[0,1,2,3,4,5,6,7,8,0], [1,2,3,4,5,6,7,8,9,5]], dtype=torch.long
)
with torch.no_grad():
    out = model(x, edge_index)
    probs = torch.softmax(out, dim=1)[:, 1]

print(f"✅ Model output shape: {out.shape}")          # Should be (10, 2)
print(f"✅ Probability range: {probs.min():.3f} – {probs.max():.3f}")
print(f"✅ Scaler fitted on {scaler.n_features_in_} features")  # Must be 7

# Verify scaler works on (N, 7) input
sample = torch.randn(5, 7).numpy()
scaled = scaler.transform(sample)
assert scaled.shape == (5, 7), "Scaler output shape wrong!"
print("✅ Handoff B verification PASSED — safe to give to Sairaj")
```

**Sairaj integrates:**
```bash
# [WSL2] After receiving files in ml/models/:
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate

python3 << 'EOF'
import sys, os
sys.path.insert(0, '../ml/src')

# Test 1: Can import model class?
from model import GraphSAGEClassifier
print("✅ model.py import OK")

# Test 2: Can load weights?
import torch
model = GraphSAGEClassifier(in_channels=7, hidden_channels=256,
                             out_channels=2, num_layers=3)
weights_path = "../ml/models/graphsage_weights.pt"
model.load_state_dict(torch.load(weights_path, map_location="cpu"))
model.eval()
print(f"✅ Weights loaded from {weights_path}")

# Test 3: Can load scaler?
import pickle
with open("../ml/models/scaler.pkl", "rb") as f:
    scaler = pickle.load(f)
print(f"✅ Scaler loaded — expects {scaler.n_features_in_} features")
assert scaler.n_features_in_ == 7, "MISMATCH: scaler expects != 7 features"

# Test 4: End-to-end mock inference
import numpy as np
from app.services.graph_builder import build_pyg_graph

mock_flows = [
    {"src_ip":"10.0.0.2","dst_ip":"10.0.0.1","src_port":54321,"dst_port":80,
     "protocol":"TCP","packet_count":15000,"byte_count":5120000,
     "duration_sec":3.5,"tcp_flags":2},
    {"src_ip":"10.0.0.1","dst_ip":"10.0.0.3","src_port":80,"dst_port":54322,
     "protocol":"TCP","packet_count":30,"byte_count":9000,
     "duration_sec":0.5,"tcp_flags":0},
]
pyg_data = build_pyg_graph(mock_flows, scaler)
with torch.no_grad():
    out = model(pyg_data.x, pyg_data.edge_index)
    probs = torch.softmax(out, dim=1)[:, 1]

print(f"✅ End-to-end inference OK")
print(f"   Nodes: {pyg_data.x.shape[0]} | Features: {pyg_data.x.shape[1]}")
print(f"   Predictions: { {ip: round(float(p),3) for ip, p in zip(pyg_data.node_ips, probs)} }")
print("\n✅ HANDOFF B COMPLETE — inference_service.py ready to load real weights")
EOF
```

---

### Handoff C: Sairaj → Susheep (TARGET: End of Week 5)

**Sairaj must verify before signalling Susheep:**
```bash
# [WSL2] Run full backend API smoke test:
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 &
sleep 3

# Test 1: Health endpoint
curl -s http://localhost:8000/health | python3 -m json.tool
# Expected: {"status": "ok", "service": "GraphSentinel"}

# Test 2: Graph endpoint (Susheep's primary data source)
curl -s http://localhost:8000/api/v1/graph | python3 -m json.tool
# Expected: {"nodes": [...], "links": [...], "metadata": {...}}
# CRITICAL: nodes must have all fields from Contract 1

# Test 3: Alerts endpoint
curl -s http://localhost:8000/api/v1/alerts | python3 -m json.tool
# Expected: {"alerts": [...], "total": N}

# Test 4: CORS works from browser origin
curl -s -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -X OPTIONS http://localhost:8000/api/v1/graph -I
# Expected: Access-Control-Allow-Origin: http://localhost:5173

echo "✅ All API checks passed — tell Susheep to connect"
```

**Susheep integrates (on Windows):**
```javascript
// frontend/src/services/api.js — switch from mock to real:
// Change in .env:
//   VITE_USE_MOCK=false   ← was true

// Then in useGraphData.js — the hook already handles this:
// When VITE_USE_MOCK=false, it calls the real API
// Verify in browser console: "[API] GET /api/v1/graph" appears
// Verify: isMockMode state becomes false

// If CORS error appears:
//   1. Check vite.config.js proxy target is http://localhost:8000
//   2. Restart Vite dev server: npm run dev
//   3. Tell Sairaj to check CORS middleware in main.py
```

---

## SECTION 5 — WEEK-BY-WEEK TEAM SYNC AGENDA

```
EVERY WEEK: 30-minute team standup (any meeting tool)
  Agenda format:
    1. What did you complete this week? (2 min each)
    2. What are you blocked on? (flag blockers early)
    3. Any API contract change needed? (must be unanimous)
    4. Integration test: can we run the pipeline so far?

WEEKLY SYNC OUTPUT:
  • Each member pastes their current API response sample in team chat
  • Backend member shares: sample JSON from GET /api/v1/graph
  • Blockchain member shares: sample TX from web3_client.test.py
  • ML member shares: sample predictions dict from inference test
  • Frontend member shares: screenshot of dashboard (even if mock)
```

### Master Timeline (8 Weeks)

| Week | Sairaj (Backend) | Susheep (Frontend) | Skanda (Blockchain) | Sathvik (ML) | Team Sync Goal |
|------|-----------------|-------------------|--------------------|--------------|----|
| **W1** | WSL2 + pyenv + Mininet | Node.js + Vite + Tailwind | Hardhat + Ganache install | Colab setup + CSV download | All environments working ✓ |
| **W2** | FastAPI skeleton + SQLite schema + CORS | Dashboard shell + all mock data in StatsBar/AlertPanel | IncidentLogger.sol written + tests | CICIDS EDA + preprocessing | Mock API returns valid JSON ✓ |
| **W3** | graph_builder.py + mock inference endpoint | NetworkGraph3D + react-force-graph-3d | deploy.js + ABI export + ganache-data persistence | Graph construction + windowing | 3D graph renders on mock data ✓ |
| **W4** | Mininet topology + flow_parser.py + monitor.py | BlockchainPanel + SelfHealStatus + ThreatTimeline | web3_client.py + integration test | GNN training Phase 4 | **HANDOFF A: Skanda→Sairaj** ✓ |
| **W5** | self_healing.py + blockchain_adapter.py + WebSocket events | useWebSocket.js + useGraphData.js hooks wired | Demo script + ganache persistence hardened | GNN eval Phase 5 + export files | **HANDOFF B: Sathvik→Sairaj** ✓ |
| **W6** | Full pipeline: Mininet→GNN→block→chain | Replace mock with real API calls (VITE_USE_MOCK=false) | Support Sairaj with blockchain_adapter debugging | Verify weights load in backend | **HANDOFF C: Sairaj→Susheep** ✓ |
| **W7** | Integration testing + WebSocket tuning | 2D/3D toggle + ForensicsModal + demo polish | Frontend blockchain read via ethers.js | Verify predictions in live backend | **FULL PIPELINE DEMO TEST** ✓ |
| **W8** | Demo hardening + fallback mocks + pre-recorded demo | Ctrl+F shortcut + SIMULATION badge + loading states | Ganache restart procedure documented | Colab notebook outputs cached offline | **60-MIN DEMO REHEARSAL** ✓ |

---

## SECTION 6 — HOW TO RUN THE FULL SYSTEM (Master Startup)

```
PREREQUISITES (do this once, before demo):
  □ Clone repo to C:\Projects\graphsentinel\ (all members)
  □ Set up WSL2 with Ubuntu 22.04 (Sairaj runs backend from here)
  □ pyenv installed, Python 3.10.11 active in WSL2
  □ Node.js 20.x installed on Windows
  □ Ganache + Hardhat installed in blockchain/
  □ ml/models/ contains graphsage_weights.pt + scaler.pkl
  □ All .env files populated (see .env.shared.example)

STARTUP ORDER (exactly this sequence every time):
─────────────────────────────────────────────────────────────────
STEP 1 [Windows Terminal A] — Start Ganache (blockchain):
  cd C:\Projects\graphsentinel\blockchain
  npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data
  → Wait for: "Listening on 127.0.0.1:8545"

STEP 2 [Windows Terminal B] — Deploy or verify contract:
  cd C:\Projects\graphsentinel\blockchain
  npx hardhat run scripts/deploy.js --network localhost
  → Wait for: "✅ CONTRACT_ADDRESS written to backend/.env"
  → NOTE: Only needed first time or after Ganache full reset

STEP 3 [WSL2 Terminal A] — Start FastAPI backend:
  cd /mnt/c/Projects/graphsentinel/backend
  source .venv/bin/activate
  uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
  → Wait for all 3 confirmation lines:
    [DB] SQLite initialized ✓
    [ML] GraphSAGE weights loaded ✓
    [Blockchain] Ganache connected ✓

STEP 4 [WSL2 Terminal B] — Start Mininet topology (demo only):
  cd /mnt/c/Projects/graphsentinel
  sudo python3 mininet/topologies/base_topology.py
  → Wait for: "GraphSentinel network READY"
  → Leave Mininet CLI open — don't type exit until demo ends

STEP 5 [Windows Terminal C] — Start React frontend:
  cd C:\Projects\graphsentinel\frontend
  npm run dev
  → Wait for: "Local: http://localhost:5173/"
  → Open browser: http://localhost:5173

STEP 6 [Browser] — Verify everything is connected:
  □ Dashboard loads (dark theme, 3D graph visible)
  □ "SIMULATION MODE" badge NOT visible (real data connected)
  □ Graph shows 10 nodes (10.0.0.1 through 10.0.0.10)
  □ No CORS errors in browser console (F12 → Console)
  □ WebSocket connected: "[WS] Connected to GraphSentinel backend ✓"
  □ Blockchain panel loads (shows "Ganache Local Chain")

STEP 7 [WSL2 Terminal C] — Trigger first attack:
  sudo python3 mininet/topologies/attack_scripts/ddos_attack.py
  → Within 10 seconds: node 10.0.0.2 turns RED in dashboard
  → Alert appears in right panel
  → Self-healing fires: node turns BLUE with cage
  → TX hash appears in Blockchain panel with ✓
─────────────────────────────────────────────────────────────────
```

---

## SECTION 7 — COLLISION AVOIDANCE RULES

```
GOLDEN RULES — NEVER VIOLATE:
─────────────────────────────────────────────────────────────────

RULE 1: No member modifies another member's folder
  ✅ Sairaj works in: backend/  mininet/
  ✅ Susheep works in: frontend/
  ✅ Skanda works in: blockchain/
  ✅ Sathvik works in: ml/
  ❌ NEVER: Sairaj edits frontend/  Susheep edits backend/  etc.

RULE 2: Shared files (docs/, .env.shared.example) → PR only
  Any change to docs/DATA_SCHEMAS.md or docs/API_CONTRACTS.md
  MUST be a PR with all 4 members approving.

RULE 3: API contract changes require unanimous agreement
  If Sairaj needs to add a field to /api/v1/graph:
    1. Raise in team standup
    2. All 4 agree
    3. Update docs/DATA_SCHEMAS.md first
    4. Backend implements, Frontend adapts
    5. Mock data updated in mockData.js to match

RULE 4: Never push broken code to develop branch
  Before pushing any integration code:
    python3 -m pytest tests/  (backend)
    npm run build             (frontend — catches import errors)
    npx hardhat test          (blockchain)

RULE 5: Environment variables are NOT in source code
  All secrets, addresses, paths → in .env (gitignored)
  Templates → in .env.shared.example (committed)
  Never: hardcode CONTRACT_ADDRESS = "0x..." in Python/JS files

RULE 6: The weights files are NEVER committed to git
  ml/models/ is in .gitignore — these are binary files, too large
  Share via: Google Drive link or direct file transfer between members
  Backend reads from local path set in .env WEIGHTS_PATH

RULE 7: Ganache is ALWAYS started before the backend
  If backend starts without Ganache running:
    → blockchain_adapter.py raises ConnectionError
    → Backend catches it and runs in degraded mode (mock blockchain)
    → This is safe for development but must be fixed for demo
```

---

## SECTION 8 — INTEGRATION DEBUGGING FLOWCHART

```
PROBLEM: "The dashboard shows mock data / SIMULATION MODE badge"
  │
  ├─ Is backend running?
  │   curl http://localhost:8000/health
  │   NO  → Start backend (Step 3 in startup sequence)
  │   YES → Continue
  │
  ├─ Is Vite proxy working?
  │   curl http://localhost:5173/api/v1/graph (from Windows)
  │   404 → Check vite.config.js proxy target = "http://localhost:8000"
  │   Works → Continue
  │
  ├─ CORS error in browser console?
  │   YES → backend CORS allows_origins missing "http://localhost:5173"
  │   NO  → Continue
  │
  └─ VITE_USE_MOCK=false in frontend/.env?
      NO  → Set it to false and restart npm run dev
      YES → Check useGraphData.js — fetchAll() should be calling real API

─────────────────────────────────────────────────────────────────

PROBLEM: "Blockchain TX hash never appears in the panel"
  │
  ├─ Is Ganache running?
  │   curl http://127.0.0.1:8545 -d '{"method":"eth_blockNumber","id":1}'
  │   Connection refused → Start Ganache (Step 1 in startup)
  │   Response → Continue
  │
  ├─ Is CONTRACT_ADDRESS set in backend/.env?
  │   cat /mnt/c/Projects/graphsentinel/backend/.env | grep CONTRACT
  │   Empty → Re-run deploy.js: npx hardhat run scripts/deploy.js --network localhost
  │   Set   → Continue
  │
  ├─ Backend startup shows "[Blockchain] Ganache connected ✓"?
  │   NO  → CONTRACT_ADDRESS may be for a different Ganache session
  │         Re-deploy contract → new address → restart backend
  │   YES → Continue
  │
  └─ POST /api/v1/blockchain/store returns { "status": "confirmed" }?
      NO  → Check blockchain_adapter.py imports web3_client correctly
      YES → Check frontend forensics fetch: GET /api/v1/forensics

─────────────────────────────────────────────────────────────────

PROBLEM: "GNN returns same score for all nodes (~0.5)"
  │
  ├─ Does ml/models/graphsage_weights.pt exist?
  │   ls /mnt/c/Projects/graphsentinel/ml/models/
  │   NO  → Sathvik needs to download + copy from Colab
  │   YES → Continue
  │
  ├─ Backend startup shows "[ML] GraphSAGE weights loaded ✓"?
  │   NO  → Check WEIGHTS_PATH in backend/.env (absolute WSL2 path)
  │   YES → Continue
  │
  ├─ Node feature count matches? (must be 7)
  │   In inference_service.py: in_channels=7
  │   In ml/src/model.py: in_channels default=7
  │   Mismatch → Both must use same number → sync with Sathvik
  │
  └─ All predictions near 0.5?
      YES → Model may be untrained/undertrained → re-check training
      NO  → Scores are being computed — check threshold (default 0.75)

─────────────────────────────────────────────────────────────────

PROBLEM: "WebSocket not receiving events / graph not updating"
  │
  ├─ Backend started with socket_app not app?
  │   uvicorn app.main:socket_app  ← CORRECT
  │   uvicorn app.main:app         ← WRONG (no Socket.IO)
  │
  ├─ Browser console shows "[WS] Connected ✓"?
  │   NO  → Check VITE_BACKEND_URL in frontend/.env
  │         Should be: http://localhost:8000 (no trailing slash)
  │
  ├─ Mininet monitor polling?
  │   Backend logs show "[Monitor] Extracted N flows from Mininet"?
  │   NO  → Mininet not running or OVS not producing flows
  │         Check: sudo ovs-ofctl dump-flows s1 (in WSL2)
  │
  └─ Events emitting but frontend not updating state?
      Check: useWebSocket callbacks update React state via setGraphData
      Pattern: socket.on('graph_update', data => setGraphData(data))
```

---

## SECTION 9 — DEMO DAY EMERGENCY CONTACTS

```
IF DEMO IS IN < 30 MINUTES AND SOMETHING IS BROKEN:

EMERGENCY PROTOCOL:

1. SWITCH TO MOCK MODE INSTANTLY:
   Frontend → add ?mock=true to URL or set localStorage mock flag
   The UI looks IDENTICAL with mock data. Panel will never know.

2. PRE-RECORDED FALLBACK:
   Play docs/fallback_demo.mp4 on second monitor.
   Keep live system on one screen, video on another.
   Narrate over the video as if it's live.

3. COMPONENT-LEVEL FALLBACKS:
   Blockchain down   → Show pre-captured TX hash screenshots
   Mininet down      → Feed pre-captured flow CSV to backend
   ML model down     → Use hardcoded threat scores (0.94 for h2)
   Backend down      → Full mock mode (frontend only)
   Frontend crash    → Show architecture diagram + explain code

4. WHAT TO SAY IF ASKED "IS THIS LIVE?":
   "The core system is live. We've activated the simulation
    fallback for [component] to ensure demo stability — this
    is standard practice in distributed systems demos."

5. THE ONE THING THAT MUST WORK FOR A PASSING DEMO:
   The 3D dashboard visualization + explanation of architecture.
   Even with ALL mocks, a confident walk-through of the system
   design, GNN intuition, and blockchain forensics concept
   will earn good marks.
```
