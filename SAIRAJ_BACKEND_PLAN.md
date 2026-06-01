# 🔧 SAIRAJ — BACKEND IMPLEMENTATION PLAN
## GraphSentinel | Role: Backend Engineer
### AI IDE: Claude Code / AntGravity / Codex

---

## PASTE THIS EXACT BLOCK WHEN STARTING YOUR AI IDE SESSION

```
You are the backend implementation assistant for GraphSentinel — a
Self-Healing Cyber Defense System using Graph Deep Learning and
Immutable Audit Trails.

YOUR ROLE: You assist Sairaj who is building the FastAPI backend.

FROZEN CONSTRAINTS — NEVER VIOLATE:
- Python: 3.10.11 via pyenv in WSL2 Ubuntu 22.04
- FastAPI: 0.115.x | Uvicorn: 0.35.x
- PyTorch: 2.4.x (CPU) | PyG: 2.5.x
- Web3.py: 7.x | NetworkX: 3.3.x
- Database: SQLite only (built-in)
- OS: All backend code runs in WSL2 ONLY (not Windows)
- Port: Backend runs on 0.0.0.0:8000
- CORS: Allow http://localhost:5173 (React frontend)
- Blockchain: Ganache at http://127.0.0.1:8545

YOUR SCOPE — ONLY GENERATE CODE FOR:
  backend/app/*
  backend/mininet_monitor/*
  mininet/topologies/*

DO NOT touch: frontend/, ml/, blockchain/

INTEGRATION CONTRACTS (Frozen — do not change):
  POST /api/v1/analyze   → receives flows → returns predictions
  GET  /api/v1/alerts    → returns incidents from SQLite
  GET  /api/v1/blocked   → returns blocked IPs from SQLite
  POST /api/v1/block     → block/unblock IP (manual override)
  GET  /api/v1/forensics → returns SQLite + blockchain records
  POST /api/v1/blockchain/store → writes incident to Ganache

FILES SAIRAJ RECEIVES FROM TEAMMATES:
  From Sathvik (ML):     ml/models/graphsage_weights.pt
                         ml/models/scaler.pkl
                         ml/src/model.py  ← import this class
  From Skanda (Chain):   blockchain/web3_bridge/web3_client.py
                         blockchain/web3_bridge/contract_abi.json
                         .env: CONTRACT_ADDRESS + GANACHE_URL

WEBSOCKET EVENTS TO EMIT (python-socketio 5.x):
  'graph_update'      → every 5 seconds → full graph JSON
  'alert'             → on new threat    → single AlertRecord
  'healing_triggered' → on block action  → HealingEvent

When I ask you to scaffold, generate file-by-file with full code.
When I describe a bug, fix only the minimum necessary code.
Always add # [WSL2] comment at top of every Python file.
```

---

## WEEK-BY-WEEK TASK BREAKDOWN

### WEEK 1 — Environment + Mininet Setup [WSL2]

```bash
# ── TASK 1.1: WSL2 + Ubuntu 22.04 ────────────────────────────────
# Run in Windows PowerShell as Admin:
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
# Restart PC after install

# ── TASK 1.2: System packages ─────────────────────────────────────
# [WSL2 Ubuntu Terminal]
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
  build-essential curl git wget \
  libssl-dev libffi-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev \
  openvswitch-switch openvswitch-testcontroller \
  net-tools iproute2 iptables

# Start OVS service
sudo service openvswitch-switch start
sudo ovs-vsctl show  # Should show "ovs-version: x.x.x"

# ── TASK 1.3: pyenv → Python 3.10.11 ─────────────────────────────
curl https://pyenv.run | bash
# Add to ~/.bashrc:
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

pyenv install 3.10.11
pyenv global 3.10.11
python --version  # MUST print: Python 3.10.11

# ── TASK 1.4: Mininet install ─────────────────────────────────────
cd ~
git clone https://github.com/mininet/mininet
cd mininet
git checkout 2.3.1b4  # Stable version
sudo PYTHON=python3 ./util/install.sh -a
# Takes 5-10 minutes

# Verify:
sudo mn --test pingall
# Expected: *** Results: 0% dropped

# ── TASK 1.5: Project virtualenv ──────────────────────────────────
cd /mnt/c/Projects/graphsentinel/backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# ── TASK 1.6: Install all backend deps ────────────────────────────
pip install fastapi==0.115.6 "uvicorn[standard]==0.35.0"
pip install python-socketio==5.11.0 python-dotenv==1.0.0
pip install sqlalchemy==2.0.x pydantic==2.x
pip install networkx==3.3 pandas==2.2.0 numpy==1.26.0 scikit-learn==1.5.0
pip install scapy==2.5.0

# PyTorch CPU (for inference)
pip install torch==2.4.0 torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cpu

# PyTorch Geometric
pip install torch-geometric==2.5.0
pip install torch-scatter torch-sparse \
  -f https://data.pyg.org/whl/torch-2.4.0+cpu.html

# Web3
pip install web3==7.4.0

# Freeze
pip freeze > requirements.txt

# ── TASK 1.7: Repo structure scaffold ────────────────────────────
mkdir -p app/{api/v1,models,services,mininet_monitor,websocket}
touch app/__init__.py app/main.py app/config.py app/database.py
touch app/models/{__init__.py,incident.py,schemas.py}
touch app/api/__init__.py app/api/v1/__init__.py
touch app/api/v1/{analyze.py,alerts.py,blocked.py,forensics.py,blockchain.py}
touch app/services/{__init__.py,inference_service.py,graph_builder.py}
touch app/services/{threat_analyzer.py,self_healing.py,blockchain_adapter.py,forensics_service.py}
touch app/mininet_monitor/{__init__.py,monitor.py,flow_parser.py}
touch app/websocket/{__init__.py,events.py}
touch .env.example README.md

echo "Week 1 complete ✓"
```

**Week 1 Checkpoint:** `sudo mn --test pingall` passes. FastAPI starts: `uvicorn app.main:app --reload`

---

### WEEK 2 — FastAPI Skeleton + SQLite Schema

**Primary Deliverable:** All 6 API endpoints return valid mock responses. Frontend can call them.

```python
# app/database.py  [WSL2]
from sqlalchemy import create_engine, Column, String, Float, Boolean, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DATABASE_URL = f"sqlite:///{os.getenv('SQLITE_PATH', './graphsentinel.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Enable WAL mode for concurrent writes — CRITICAL for demo stability
with engine.connect() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    conn.exec_driver_sql("PRAGMA synchronous=NORMAL")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Tables ────────────────────────────────────────────────────────
class Incident(Base):
    __tablename__ = "incidents"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    source_ip       = Column(String(20), nullable=False, index=True)
    attack_type     = Column(String(50), nullable=False)
    threat_score    = Column(Float, nullable=False)
    severity        = Column(Integer, nullable=False)  # 1–10
    is_blocked      = Column(Boolean, default=False)
    raw_flow_json   = Column(Text)                     # serialized flow data
    blockchain_tx   = Column(String(100), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

class BlockedIP(Base):
    __tablename__ = "blocked_ips"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    ip_address  = Column(String(20), unique=True, nullable=False, index=True)
    reason      = Column(String(50), default="GNN_DETECTED")
    attack_type = Column(String(50))
    threat_score = Column(Float)
    blockchain_tx = Column(String(100), nullable=True)
    blocked_at  = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

```python
# app/config.py  [WSL2]
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    sqlite_path: str = "./graphsentinel.db"
    threat_threshold: float = 0.75
    poll_interval_seconds: int = 5

    # ML model
    weights_path: str = "../ml/models/graphsage_weights.pt"
    scaler_path: str = "../ml/models/scaler.pkl"
    node_feature_count: int = 7

    # Blockchain
    ganache_url: str = "http://127.0.0.1:8545"
    contract_address: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# app/models/schemas.py  [WSL2]
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class FlowRecord(BaseModel):
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    packet_count: int
    byte_count: int
    duration_sec: float
    tcp_flags: int = 0

class AnalyzeRequest(BaseModel):
    flows: List[FlowRecord]

class NodeData(BaseModel):
    id: str                   # IP address
    label: str
    status: str               # normal|suspicious|malicious|blocked
    threat_score: float
    connections: int
    bytes_total: int
    attack_type: Optional[str]
    is_blocked: bool

class LinkData(BaseModel):
    source: str
    target: str
    value: float              # threat weight
    attack_type: Optional[str]
    packet_count: int

class GraphResponse(BaseModel):
    nodes: List[NodeData]
    links: List[LinkData]
    metadata: dict

class AlertRecord(BaseModel):
    id: str
    timestamp: str
    source_ip: str
    attack_type: str
    severity: str             # info|warning|critical
    threat_score: float
    description: str
    is_blocked: bool
    blockchain_tx: Optional[str]

class BlockchainStoreRequest(BaseModel):
    source_ip: str
    attack_type: str
    severity: int             # 1–10
    is_blocked: bool
    sqlite_incident_id: int

class BlockedIPRecord(BaseModel):
    ip: str
    blocked_at: str
    reason: str
    attack_type: Optional[str]
    threat_score: float
    blockchain_tx: Optional[str]
```

```python
# app/main.py  [WSL2]
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import init_db
from app.config import settings

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=["http://localhost:5173", "http://localhost:3000"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("[DB] SQLite initialized ✓")

    # Start Mininet monitor in background thread
    try:
        from app.mininet_monitor.monitor import MininetMonitor
        monitor = MininetMonitor(sio=sio)
        monitor.start()
        print("[Monitor] Mininet polling started ✓")
    except Exception as e:
        print(f"[Monitor] WARN: Mininet not available ({e}) — using mock flows")

    # Load ML model
    try:
        from app.services.inference_service import InferenceService
        InferenceService.get_instance()
        print("[ML] GraphSAGE weights loaded ✓")
    except Exception as e:
        print(f"[ML] WARN: Model not loaded ({e}) — using random scores")

    # Connect blockchain
    try:
        from app.services.blockchain_adapter import BlockchainAdapter
        BlockchainAdapter.get_instance()
        print("[Blockchain] Ganache connected ✓")
    except Exception as e:
        print(f"[Blockchain] WARN: Ganache not connected ({e})")

    yield  # App runs here

    # Shutdown (cleanup if needed)

app = FastAPI(
    title="GraphSentinel API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.api.v1 import analyze, alerts, blocked, forensics, blockchain
app.include_router(analyze.router,    prefix="/api/v1", tags=["analyze"])
app.include_router(alerts.router,     prefix="/api/v1", tags=["alerts"])
app.include_router(blocked.router,    prefix="/api/v1", tags=["blocked"])
app.include_router(forensics.router,  prefix="/api/v1", tags=["forensics"])
app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "GraphSentinel"}

# Wrap with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Run: uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

**Week 2 Checkpoint:** `curl http://localhost:8000/api/v1/alerts` → `{"alerts":[],"total":0}`

---

### WEEK 3 — Graph Builder + Mock Inference

**Primary Deliverable:** `POST /api/v1/analyze` returns predictions (even with random scores until W6).

```python
# app/services/graph_builder.py  [WSL2]
# Converts raw FlowRecord list → NetworkX DiGraph → PyG Data object

import torch
import networkx as nx
import numpy as np
from collections import defaultdict
from scipy.stats import entropy as scipy_entropy
from torch_geometric.data import Data
from typing import List
from app.models.schemas import FlowRecord

def build_pyg_graph(flows: List[FlowRecord], scaler=None) -> Data:
    """
    Convert flow records to a PyG Data object.
    NODE FEATURES (7 — MUST match Sathvik's training exactly):
      0: out_degree
      1: in_degree
      2: avg_packet_size      = total_bytes / (total_packets + ε)
      3: connection_rate      = total_packets / (window_duration + ε)
      4: port_entropy         = Shannon entropy of destination ports contacted
      5: byte_asymmetry       = (sent - received) / (sent + received + ε)
      6: syn_ratio            = (estimated SYN packets) / (total_packets + ε)
    """
    G = nx.DiGraph()
    node_stats = defaultdict(lambda: {
        "out_bytes": 0, "in_bytes": 0,
        "out_packets": 0, "in_packets": 0,
        "duration": 0.0, "dst_ports": []
    })

    for flow in flows:
        G.add_edge(flow.src_ip, flow.dst_ip,
                   packets=flow.packet_count,
                   bytes=flow.byte_count,
                   duration=flow.duration_sec)
        node_stats[flow.src_ip]["out_bytes"]   += flow.byte_count
        node_stats[flow.src_ip]["out_packets"] += flow.packet_count
        node_stats[flow.src_ip]["duration"]    += flow.duration_sec
        node_stats[flow.src_ip]["dst_ports"].append(flow.dst_port)
        node_stats[flow.dst_ip]["in_bytes"]    += flow.byte_count
        node_stats[flow.dst_ip]["in_packets"]  += flow.packet_count

    nodes = list(G.nodes())
    node_to_idx = {ip: i for i, ip in enumerate(nodes)}

    # Build feature matrix
    features = []
    for ip in nodes:
        s = node_stats[ip]
        total_packets = s["out_packets"] + s["in_packets"]
        total_bytes   = s["out_bytes"]   + s["in_bytes"]
        duration      = max(s["duration"], 0.001)
        ports         = s["dst_ports"]

        # port_entropy: high = port scan
        if len(ports) > 1:
            counts = np.bincount(ports)
            probs  = counts[counts > 0] / len(ports)
            pe     = float(scipy_entropy(probs, base=2))
        else:
            pe = 0.0

        eps = 1e-6
        f = [
            float(G.out_degree(ip)),                        # 0: out_degree
            float(G.in_degree(ip)),                         # 1: in_degree
            total_bytes / (total_packets + eps),            # 2: avg_packet_size
            total_packets / (duration + eps),               # 3: connection_rate
            pe,                                             # 4: port_entropy
            (s["out_bytes"] - s["in_bytes"]) /              # 5: byte_asymmetry
                (total_bytes + eps),
            min(s["out_packets"] / (total_packets + eps),   # 6: syn_ratio (approx)
                1.0)
        ]
        features.append(f)

    x = torch.tensor(features, dtype=torch.float32)

    # Normalize using scaler from Sathvik
    if scaler is not None:
        x_np = x.numpy()
        x_np = scaler.transform(x_np)
        x = torch.tensor(x_np, dtype=torch.float32)

    # Build edge_index
    edge_list = [(node_to_idx[u], node_to_idx[v]) for u, v in G.edges()]
    if edge_list:
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    data = Data(x=x, edge_index=edge_index)
    data.node_ips = nodes  # Keep IP mapping for results
    return data
```

```python
# app/services/inference_service.py  [WSL2]
import os
import pickle
import torch
from app.config import settings

class InferenceService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Import model class from ML teammate's shared file
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../ml/src"))
        from model import GraphSAGEClassifier

        self.model = GraphSAGEClassifier(
            in_channels=settings.node_feature_count,  # 7
            hidden_channels=256,
            out_channels=2,
            num_layers=3
        )

        weights_path = settings.weights_path
        if os.path.exists(weights_path):
            self.model.load_state_dict(
                torch.load(weights_path, map_location="cpu")
            )
            self.model.eval()
            self._using_mock = False
            print(f"[Inference] Loaded weights from {weights_path} ✓")
        else:
            self._using_mock = True
            print(f"[Inference] WARN: weights not found at {weights_path} — using random scores")

        scaler_path = settings.scaler_path
        if os.path.exists(scaler_path):
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
        else:
            self.scaler = None

    def predict(self, flows: list) -> dict:
        """Returns { ip: malicious_probability } for all nodes."""
        from app.services.graph_builder import build_pyg_graph
        pyg_data = build_pyg_graph(flows, self.scaler)

        if self._using_mock or len(pyg_data.node_ips) == 0:
            # Fallback: random scores (still realistic-looking for demo)
            import random
            return {ip: round(random.uniform(0.02, 0.15), 3)
                    for ip in pyg_data.node_ips}

        with torch.no_grad():
            logits = self.model(pyg_data.x, pyg_data.edge_index)
            probs = torch.softmax(logits, dim=1)[:, 1]

        return {
            ip: round(float(prob), 4)
            for ip, prob in zip(pyg_data.node_ips, probs.tolist())
        }
```

**Week 3 Checkpoint:** `POST /api/v1/analyze` with 5 mock flows → returns dict of IPs with scores.

---

### WEEK 4 — Mininet Topology + Flow Parser

```python
# mininet/topologies/base_topology.py  [WSL2 — requires sudo]
# Run: sudo python3 base_topology.py

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.log import setLogLevel
from mininet.cli import CLI
import threading
import time
import json

class GraphSentinelTopology:
    """
    10-host star topology for GraphSentinel.
    All hosts connect through switch s1.
    IP assignment: 10.0.0.1 – 10.0.0.10
    """

    def __init__(self):
        setLogLevel('warning')
        self.net = Mininet(
            switch=OVSSwitch,
            controller=Controller,
            autoSetMacs=True
        )
        self._build()

    def _build(self):
        c0 = self.net.addController('c0')
        s1 = self.net.addSwitch('s1')

        self.hosts = {}
        for i in range(1, 11):
            h = self.net.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
            self.net.addLink(h, s1)
            self.hosts[f'10.0.0.{i}'] = h

    def start(self):
        self.net.start()
        print("[Mininet] Topology started — 10 hosts on 10.0.0.0/24")

    def stop(self):
        self.net.stop()

    def get_host(self, ip: str):
        return self.hosts.get(ip)
```

```python
# app/mininet_monitor/flow_parser.py  [WSL2]
import subprocess
import re
from typing import List
from app.models.schemas import FlowRecord

def parse_ovs_flows(switch: str = "s1") -> List[dict]:
    """
    Extracts current flow stats from OVS switch.
    Returns raw flow dicts for graph_builder.
    """
    try:
        result = subprocess.run(
            ["sudo", "ovs-ofctl", "dump-flows", switch],
            capture_output=True, text=True, timeout=3
        )
        return _parse_output(result.stdout)
    except Exception as e:
        print(f"[FlowParser] Error: {e}")
        return []

def _parse_output(raw: str) -> List[dict]:
    flows = []
    pattern = re.compile(
        r"nw_src=(\d+\.\d+\.\d+\.\d+).*?nw_dst=(\d+\.\d+\.\d+\.\d+)"
        r".*?tp_src=(\d+).*?tp_dst=(\d+)"
        r".*?n_packets=(\d+).*?n_bytes=(\d+)"
    )
    for match in pattern.finditer(raw):
        flows.append({
            "src_ip": match.group(1),
            "dst_ip": match.group(2),
            "src_port": int(match.group(3)),
            "dst_port": int(match.group(4)),
            "packet_count": int(match.group(5)),
            "byte_count": int(match.group(6)),
            "protocol": "TCP",
            "duration_sec": 5.0,
            "tcp_flags": 0
        })
    return flows
```

```python
# app/mininet_monitor/monitor.py  [WSL2]
import threading
import asyncio
import time
from app.config import settings
from app.mininet_monitor.flow_parser import parse_ovs_flows

class MininetMonitor:
    """
    Background thread that polls Mininet/OVS every POLL_INTERVAL_SECONDS.
    On each tick: extract flows → analyze → emit WebSocket event.
    """

    def __init__(self, sio):
        self.sio = sio
        self.interval = settings.poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        print(f"[Monitor] Polling every {self.interval}s")
        while not self._stop_event.is_set():
            try:
                flows = parse_ovs_flows("s1")
                if flows:
                    asyncio.run(self._process(flows))
            except Exception as e:
                print(f"[Monitor] Tick error: {e}")
            time.sleep(self.interval)

    async def _process(self, flows: list):
        from app.services.inference_service import InferenceService
        from app.services.threat_analyzer import ThreatAnalyzer
        from app.services.graph_builder import build_pyg_graph

        inference = InferenceService.get_instance()
        analyzer  = ThreatAnalyzer()
        predictions = inference.predict(flows)

        incidents = analyzer.evaluate(predictions, flows)
        graph_snapshot = analyzer.build_graph_response(predictions, flows)

        # Push to all connected frontend clients
        await self.sio.emit("graph_update", graph_snapshot)

        for incident in incidents:
            await self.sio.emit("alert", incident)
            print(f"[Monitor] Alert: {incident['source_ip']} — {incident['attack_type']}")
```

**Week 4 Checkpoint:** Mininet running, flows extracted, graph_update fires every 5s on WebSocket.

---

### WEEK 5 — Self-Healing + Blocking Engine

```python
# app/services/threat_analyzer.py  [WSL2]
import uuid
from datetime import datetime, timezone
from app.config import settings
from app.models.schemas import AlertRecord

ATTACK_MAP = {
    (0.75, 1.0): "critical",
    (0.50, 0.75): "warning",
    (0.0,  0.50): "info",
}

def score_to_severity(score: float) -> str:
    if score >= 0.75: return "critical"
    if score >= 0.50: return "warning"
    return "info"

def score_to_attack_type(score: float, ip: str) -> str:
    """Simple heuristic for demo — in production use port features."""
    seed = sum(ord(c) for c in ip) + int(score * 100)
    attacks = ["DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk"]
    return attacks[seed % len(attacks)]

class ThreatAnalyzer:
    def __init__(self):
        self.threshold = settings.threat_threshold  # 0.75

    def evaluate(self, predictions: dict, flows: list) -> list:
        """
        Returns list of incident dicts for any node above threshold.
        Also triggers self-healing for critical threats.
        """
        from app.services.self_healing import SelfHealingEngine
        from app.database import SessionLocal
        from app.models.incident import Incident as IncidentModel

        incidents = []
        healer = SelfHealingEngine()

        for ip, score in predictions.items():
            if score >= self.threshold:
                attack_type = score_to_attack_type(score, ip)
                severity_val = int(score * 10)

                # Write to SQLite
                db = SessionLocal()
                incident = IncidentModel(
                    source_ip=ip,
                    attack_type=attack_type,
                    threat_score=score,
                    severity=severity_val,
                    is_blocked=False,
                )
                db.add(incident)
                db.commit()
                db.refresh(incident)
                db.close()

                # Trigger self-healing
                healed = healer.evaluate_and_act({ip: score})

                incidents.append({
                    "id": f"alert-{incident.id}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_ip": ip,
                    "attack_type": attack_type,
                    "severity": score_to_severity(score),
                    "threat_score": score,
                    "description": f"{attack_type} detected from {ip} (score: {score:.2f})",
                    "is_blocked": bool(healed),
                    "blockchain_tx": None,  # Filled after blockchain call
                })

        return incidents

    def build_graph_response(self, predictions: dict, flows: list) -> dict:
        """Builds the full graph JSON for frontend."""
        from app.database import SessionLocal
        from app.models.incident import BlockedIP as BlockedIPModel

        db = SessionLocal()
        blocked_ips = {b.ip_address for b in db.query(BlockedIPModel).all()}
        db.close()

        seen_nodes = set()
        nodes, links = [], []
        flow_agg = {}

        for flow in flows:
            key = (flow["src_ip"], flow["dst_ip"])
            if key not in flow_agg:
                flow_agg[key] = {"packet_count": 0, "byte_count": 0}
            flow_agg[key]["packet_count"] += flow["packet_count"]
            flow_agg[key]["byte_count"]   += flow["byte_count"]

        for ip in set(predictions.keys()):
            if ip in seen_nodes: continue
            seen_nodes.add(ip)
            score = predictions[ip]
            if ip in blocked_ips:
                status = "blocked"
            elif score >= 0.75:
                status = "malicious"
            elif score >= 0.50:
                status = "suspicious"
            else:
                status = "normal"

            nodes.append({
                "id": ip,
                "label": f"h{ip.split('.')[-1]}",
                "status": status,
                "threat_score": score,
                "connections": sum(1 for k in flow_agg if k[0] == ip or k[1] == ip),
                "bytes_total": sum(v["byte_count"] for k, v in flow_agg.items()
                                   if k[0] == ip or k[1] == ip),
                "attack_type": score_to_attack_type(score, ip) if score >= 0.50 else None,
                "is_blocked": ip in blocked_ips,
            })

        for (src, dst), agg in flow_agg.items():
            score = max(predictions.get(src, 0), predictions.get(dst, 0))
            links.append({
                "source": src,
                "target": dst,
                "value": score,
                "attack_type": score_to_attack_type(score, src) if score >= 0.50 else None,
                "packet_count": agg["packet_count"],
            })

        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "total_nodes": len(nodes),
                "malicious_nodes": sum(1 for n in nodes if n["status"] == "malicious"),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        }
```

**Week 5 Checkpoint:** Attack triggers → node blocked → WebSocket fires `healing_triggered`.

---

### WEEK 6 — Blockchain Adapter (Integrates Skanda's Work)

```python
# app/services/blockchain_adapter.py  [WSL2]
# Wraps Skanda's web3_client.py

import os
import sys

class BlockchainAdapter:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Add Skanda's bridge to path
        bridge_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../blockchain/web3_bridge")
        )
        sys.path.insert(0, bridge_path)

        try:
            from web3_client import BlockchainClient
            self.client = BlockchainClient()
            self._connected = True
        except Exception as e:
            print(f"[Blockchain] Not connected: {e}")
            self._connected = False

    def store_incident(self, source_ip, attack_type, severity, is_blocked, incident_id) -> dict:
        if not self._connected:
            return {"tx_hash": "0xMOCK_HASH_BLOCKCHAIN_OFFLINE", "status": "mock"}
        try:
            return self.client.log_incident(
                source_ip=source_ip,
                attack_type=attack_type,
                severity=min(max(int(severity), 1), 10),
                is_blocked=is_blocked,
                sqlite_incident_id=incident_id
            )
        except Exception as e:
            print(f"[Blockchain] store error: {e}")
            return {"tx_hash": None, "status": "error", "error": str(e)}
```

---

### WEEK 7–8 — API Endpoint Completions

```python
# app/api/v1/analyze.py  [WSL2]
from fastapi import APIRouter, Depends
from app.models.schemas import AnalyzeRequest
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import ThreatAnalyzer

router = APIRouter()

@router.post("/analyze")
async def analyze_traffic(request: AnalyzeRequest):
    inference = InferenceService.get_instance()
    analyzer  = ThreatAnalyzer()

    predictions = inference.predict([f.dict() for f in request.flows])
    incidents   = analyzer.evaluate(predictions, [f.dict() for f in request.flows])
    graph       = analyzer.build_graph_response(predictions, [f.dict() for f in request.flows])

    return {
        "predictions": predictions,
        "incidents_created": [i["id"] for i in incidents],
        "healing_triggered": [i["source_ip"] for i in incidents if i["is_blocked"]],
        "graph_snapshot": graph,
    }

# app/api/v1/alerts.py
@router.get("/alerts")
async def get_alerts(limit: int = 50, db=Depends(get_db)):
    from app.models.incident import Incident
    rows = db.query(Incident).order_by(Incident.created_at.desc()).limit(limit).all()
    return {"alerts": [r.__dict__ for r in rows], "total": len(rows)}

# app/api/v1/forensics.py
@router.get("/forensics")
async def get_forensics(db=Depends(get_db)):
    from app.models.incident import Incident
    from app.services.blockchain_adapter import BlockchainAdapter
    incidents = db.query(Incident).all()
    chain_records = []
    try:
        adapter = BlockchainAdapter.get_instance()
        if adapter._connected:
            chain_records = adapter.client.get_all_incidents()
    except: pass
    return {
        "incidents": [i.__dict__ for i in incidents],
        "blockchain_records": chain_records,
        "total_on_chain": len(chain_records),
    }
```

---

## STARTUP COMMAND SEQUENCE (Run in this exact order)

```bash
# STEP 1: [Windows Terminal] — Start Ganache
cd C:\Projects\graphsentinel\blockchain
npx ganache --port 8545 --deterministic --db ./ganache-data
# Wait for: "Listening on 127.0.0.1:8545"

# STEP 2: [Windows Terminal 2] — Deploy contract
npx hardhat run scripts/deploy.js --network localhost
# Wait for: "CONTRACT_ADDRESS written to backend/.env"

# STEP 3: [WSL2 Terminal] — Start backend
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
# Wait for all 3 "✓" lines:
# [DB] SQLite initialized ✓
# [ML] GraphSAGE weights loaded ✓
# [Blockchain] Ganache connected ✓

# STEP 4: [WSL2 Terminal 2] — Start Mininet (demo only)
sudo python3 /mnt/c/Projects/graphsentinel/mininet/topologies/base_topology.py

# STEP 5: [Windows Terminal 3] — Start frontend
cd C:\Projects\graphsentinel\frontend
npm run dev
```

---

## FAILURE TRIAGE GUIDE

```
SYMPTOM: uvicorn fails to start
  → Check: python --version shows 3.10.11?
  → Check: source .venv/bin/activate was run?
  → Fix: pip install fastapi uvicorn again inside .venv

SYMPTOM: [ML] WARN: weights not found
  → Check: WEIGHTS_PATH in .env points to correct absolute path
  → Check: ml/models/ directory exists
  → Fix: Copy weights.pt from Sathvik, update WEIGHTS_PATH

SYMPTOM: [Blockchain] Not connected
  → Check: Ganache terminal shows "Listening on 8545"?
  → Check: CONTRACT_ADDRESS in backend .env is set?
  → Fix: Re-run Skanda's deploy.js, then restart backend

SYMPTOM: Frontend shows CORS error
  → Check: allow_origins includes "http://localhost:5173"
  → Fix: Restart uvicorn after updating CORS config

SYMPTOM: WebSocket not receiving events
  → Check: Frontend connects to correct URL (port 8000)
  → Check: socket_app (not app) passed to uvicorn
  → Fix: uvicorn app.main:socket_app (NOT app.main:app)

SYMPTOM: iptables block fails
  → Check: WSL2 has iptables capability
  → Fix: sudo sysctl -w net.ipv4.ip_forward=1
  → Alternative: simulate block by just updating SQLite + WebSocket
```
