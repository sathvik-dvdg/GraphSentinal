# 📜 GRAPHSENTINEL — FROZEN API CONTRACTS
## docs/API_CONTRACTS.md
### ⚠️ FROZEN — Any change requires all 4 members to approve via PR ⚠️

---

## BASE URL
```
http://localhost:8000
```
All API calls from the frontend go through the Vite proxy:
```javascript
// vite.config.js — proxy config
'/api': { target: 'http://localhost:8000', changeOrigin: true }
```

---

## REST ENDPOINTS

---

### `GET /api/v1/graph`
**Owner:** Sairaj  
**Called by:** Susheep (initial page load + polling fallback)  
**Purpose:** Returns full current network state — the primary data source for the 3D graph

**Request:** No body, no params

**Response 200:**
```json
{
  "nodes": [
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
  ],
  "links": [
    {
      "source":       "10.0.0.2",
      "target":       "10.0.0.1",
      "value":        0.94,
      "attack_type":  "DDoS",
      "packet_count": 15000
    }
  ],
  "metadata": {
    "total_nodes":     10,
    "malicious_nodes": 2,
    "last_updated":    "2024-01-15T14:32:01Z"
  }
}
```

**Field Contracts:**
- `status`: MUST be one of: `"normal"` | `"suspicious"` | `"malicious"` | `"blocked"`
- `attack_type`: MUST be one of: `"DDoS"` | `"PortScan"` | `"SSHBrute"` | `"Botnet"` | `"DoSHulk"` | `null`
- `threat_score`: float between 0.0 and 1.0
- `value` (link): threat weight float between 0.0 and 1.0

---

### `GET /api/v1/alerts`
**Owner:** Sairaj  
**Called by:** Susheep (alert panel, initial load)

**Query params:**
- `limit` (optional, default: 50) — max alerts to return
- `severity` (optional) — filter: `"critical"` | `"warning"` | `"info"`

**Request:** `GET /api/v1/alerts?limit=50&severity=critical`

**Response 200:**
```json
{
  "alerts": [
    {
      "id":            "alert-42",
      "timestamp":     "2024-01-15T14:32:01Z",
      "source_ip":     "10.0.0.2",
      "attack_type":   "DDoS",
      "severity":      "critical",
      "threat_score":  0.94,
      "description":   "DDoS detected from 10.0.0.2 (score: 0.94)",
      "is_blocked":    false,
      "blockchain_tx": "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1"
    }
  ],
  "total": 7
}
```

**Field Contracts:**
- `severity`: MUST be one of: `"info"` | `"warning"` | `"critical"`
- `blockchain_tx`: string (TX hash) or `null` if not yet stored on chain
- `timestamp`: ISO 8601 format with timezone (UTC)
- Sorted by `timestamp` descending (newest first)

---

### `GET /api/v1/blocked`
**Owner:** Sairaj  
**Called by:** Susheep (blocked nodes panel)

**Request:** No body, no params

**Response 200:**
```json
{
  "blocked_ips": [
    {
      "ip":            "10.0.0.5",
      "blocked_at":    "2024-01-15T14:31:50Z",
      "reason":        "GNN_DETECTED",
      "attack_type":   "SSHBrute",
      "threat_score":  0.88,
      "blockchain_tx": "0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8"
    }
  ],
  "count": 1
}
```

**Field Contracts:**
- `reason`: MUST be one of: `"GNN_DETECTED"` | `"MANUAL_OVERRIDE"`
- `blockchain_tx`: TX hash of the blocking event on chain, or `null`

---

### `POST /api/v1/block`
**Owner:** Sairaj  
**Called by:** Susheep (manual block/unblock button in UI)

**Request body:**
```json
{
  "ip":     "10.0.0.2",
  "reason": "MANUAL_OVERRIDE",
  "action": "block"
}
```

**Field Contracts:**
- `action`: `"block"` | `"unblock"` (defaults to `"block"` if omitted)
- `reason`: string, free text but prefer: `"GNN_DETECTED"` | `"MANUAL_OVERRIDE"`

**Response 200 (block):**
```json
{
  "status":      "blocked",
  "ip":          "10.0.0.2",
  "blockchain_tx": "0x..."
}
```

**Response 200 (unblock):**
```json
{
  "status": "unblocked",
  "ip":     "10.0.0.2"
}
```

---

### `GET /api/v1/forensics`
**Owner:** Sairaj (SQLite) + Skanda (blockchain records)  
**Called by:** Susheep (ForensicsModal component)  
**Purpose:** Returns full forensic report — both SQLite incidents AND on-chain records

**Request:** No body, no params

**Response 200:**
```json
{
  "incidents": [
    {
      "id":              42,
      "source_ip":       "10.0.0.2",
      "attack_type":     "DDoS",
      "threat_score":    0.94,
      "severity":        9,
      "is_blocked":      false,
      "blockchain_tx":   "0x4f3acd...",
      "created_at":      "2024-01-15T14:32:01Z"
    }
  ],
  "blockchain_records": [
    {
      "id":              1,
      "incident_hash":   "0xb8f2a1c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      "timestamp":       "2024-01-15T14:32:01Z",
      "source_ip":       "10.0.0.2",
      "attack_type":     "DDoS",
      "severity":        9,
      "is_blocked":      false,
      "forensics_uri":   "local://incident/42",
      "tx_hash":         "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1",
      "block_number":    142,
      "gas_used":        68432,
      "status":          "confirmed"
    }
  ],
  "total_incidents":  7,
  "total_on_chain":   5,
  "chain_id":         1337,
  "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"
}
```

**Field Contracts:**
- `forensics_uri`: always `"local://incident/{sqlite_id}"` — links chain record to SQLite
- `status`: `"confirmed"` | `"pending"` | `"failed"`
- `chain_id`: 1337 (Ganache local chain — always)

---

### `POST /api/v1/blockchain/store`
**Owner:** Sairaj (calls this internally, not exposed to frontend)  
**Called by:** Backend's own threat_analyzer after incident is written to SQLite

**Request body:**
```json
{
  "source_ip":          "10.0.0.2",
  "attack_type":        "DDoS",
  "severity":           9,
  "is_blocked":         false,
  "sqlite_incident_id": 42
}
```

**Field Contracts:**
- `severity`: integer 1–10 (not float, not string)
- `sqlite_incident_id`: must match a real incident in the SQLite DB

**Response 200:**
```json
{
  "tx_hash":      "0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1",
  "block_number": 142,
  "status":       "confirmed",
  "gas_used":     68432
}
```

---

### `POST /api/v1/analyze`
**Owner:** Sairaj  
**Called by:** Internal (Mininet monitor calls this automatically)  
**Note:** Frontend does NOT call this directly — it receives results via WebSocket

**Request body:**
```json
{
  "flows": [
    {
      "src_ip":       "10.0.0.2",
      "dst_ip":       "10.0.0.1",
      "src_port":     54321,
      "dst_port":     80,
      "protocol":     "TCP",
      "packet_count": 15000,
      "byte_count":   5120000,
      "duration_sec": 3.5,
      "tcp_flags":    2
    }
  ]
}
```

**Response 200:**
```json
{
  "predictions": {
    "10.0.0.2": 0.94,
    "10.0.0.1": 0.08
  },
  "incidents_created":  ["alert-42"],
  "healing_triggered":  ["10.0.0.2"],
  "graph_snapshot":     { "nodes": [], "links": [], "metadata": {} }
}
```

---

## WEBSOCKET EVENTS (Socket.IO)

**Connection:** `http://localhost:8000`  
**Transport:** WebSocket with polling fallback  
**Library (frontend):** `socket.io-client@4`  
**Library (backend):** `python-socketio@5`

---

### Event: `graph_update`
**Direction:** Server → All clients  
**Frequency:** Every 5 seconds (from Mininet monitor poll cycle)  
**Payload shape:** Same as `GET /api/v1/graph` response

```javascript
socket.on('graph_update', (data) => {
  // data: { nodes: [...], links: [...], metadata: {...} }
  setGraphData(data)
})
```

---

### Event: `alert`
**Direction:** Server → All clients  
**Frequency:** Fires once per new incident (when threat_score ≥ 0.75)  
**Payload shape:** Same as a single item in `GET /api/v1/alerts` response

```javascript
socket.on('alert', (data) => {
  // data: single AlertRecord object
  // { id, timestamp, source_ip, attack_type, severity, threat_score, ... }
  setAlerts(prev => [data, ...prev].slice(0, 50))
})
```

---

### Event: `healing_triggered`
**Direction:** Server → All clients  
**Frequency:** Once per node isolation event  
**Payload:**

```javascript
// Shape (FROZEN):
{
  id:                       "heal-001",
  timestamp:                "2024-01-15T14:32:01Z",
  ip:                       "10.0.0.2",
  action:                   "ISOLATED",
  attack_type:              "DDoS",
  trigger_score:            0.94,
  edges_severed:            6,
  duration_ms:              245,
  network_stability_before: 88,
  network_stability_after:  94
}

// Frontend handler:
socket.on('healing_triggered', (data) => {
  setHealingNodeId(data.ip)              // triggers Blue cage animation
  setHealingEvents(prev => [data, ...prev])
  setTimeout(() => setHealingNodeId(null), 3500)
})
```

---

## PYTHON TYPE HINTS (for Sairaj's Pydantic models)

```python
# Exact Pydantic schemas that implement the contracts above
# backend/app/models/schemas.py

from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime

# ── Shared types ──────────────────────────────────────────────────
NodeStatus    = Literal["normal", "suspicious", "malicious", "blocked"]
AttackType    = Literal["DDoS", "PortScan", "SSHBrute", "Botnet", "DoSHulk"]
Severity      = Literal["info", "warning", "critical"]
BlockAction   = Literal["block", "unblock"]
BlockReason   = Literal["GNN_DETECTED", "MANUAL_OVERRIDE"]
TxStatus      = Literal["confirmed", "pending", "failed"]

# ── /api/v1/graph ─────────────────────────────────────────────────
class NodeData(BaseModel):
    id:           str
    label:        str
    status:       NodeStatus
    threat_score: float               # 0.0 – 1.0
    connections:  int
    bytes_total:  int
    attack_type:  Optional[AttackType] = None
    is_blocked:   bool

class LinkData(BaseModel):
    source:       str
    target:       str
    value:        float               # 0.0 – 1.0
    attack_type:  Optional[AttackType] = None
    packet_count: int

class GraphResponse(BaseModel):
    nodes:    List[NodeData]
    links:    List[LinkData]
    metadata: dict

# ── /api/v1/alerts ────────────────────────────────────────────────
class AlertRecord(BaseModel):
    id:             str
    timestamp:      str               # ISO 8601 UTC
    source_ip:      str
    attack_type:    AttackType
    severity:       Severity
    threat_score:   float
    description:    str
    is_blocked:     bool
    blockchain_tx:  Optional[str] = None

class AlertsResponse(BaseModel):
    alerts: List[AlertRecord]
    total:  int

# ── /api/v1/blocked ───────────────────────────────────────────────
class BlockedIPRecord(BaseModel):
    ip:             str
    blocked_at:     str
    reason:         BlockReason
    attack_type:    Optional[AttackType] = None
    threat_score:   float
    blockchain_tx:  Optional[str] = None

class BlockedResponse(BaseModel):
    blocked_ips: List[BlockedIPRecord]
    count:       int

# ── /api/v1/blockchain/store ──────────────────────────────────────
class BlockchainStoreRequest(BaseModel):
    source_ip:          str
    attack_type:        AttackType
    severity:           int           # 1–10
    is_blocked:         bool
    sqlite_incident_id: int

class BlockchainStoreResponse(BaseModel):
    tx_hash:      Optional[str]
    block_number: Optional[int]
    status:       TxStatus
    gas_used:     Optional[int] = None

# ── WebSocket: healing_triggered event ────────────────────────────
class HealingEvent(BaseModel):
    id:                       str
    timestamp:                str
    ip:                       str
    action:                   Literal["ISOLATED"]
    attack_type:              AttackType
    trigger_score:            float
    edges_severed:            int
    duration_ms:              int
    network_stability_before: int     # percentage
    network_stability_after:  int     # percentage
```

---

## TYPESCRIPT TYPES (for Susheep's React components)

```typescript
// frontend/src/types/index.ts

export type NodeStatus   = "normal" | "suspicious" | "malicious" | "blocked"
export type AttackType   = "DDoS" | "PortScan" | "SSHBrute" | "Botnet" | "DoSHulk"
export type Severity     = "info" | "warning" | "critical"
export type TxStatus     = "confirmed" | "pending" | "failed"

export interface NodeData {
  id:           string
  label:        string
  status:       NodeStatus
  threat_score: number              // 0.0 – 1.0
  connections:  number
  bytes_total:  number
  attack_type:  AttackType | null
  is_blocked:   boolean
}

export interface LinkData {
  source:       string
  target:       string
  value:        number              // 0.0 – 1.0
  attack_type:  AttackType | null
  packet_count: number
}

export interface GraphState {
  nodes:    NodeData[]
  links:    LinkData[]
  metadata: {
    total_nodes:     number
    malicious_nodes: number
    last_updated:    string
  }
}

export interface AlertRecord {
  id:            string
  timestamp:     string
  source_ip:     string
  attack_type:   AttackType
  severity:      Severity
  threat_score:  number
  description:   string
  is_blocked:    boolean
  blockchain_tx: string | null
}

export interface BlockchainTxRecord {
  id:             number
  incident_hash:  string
  timestamp:      string
  source_ip:      string
  attack_type:    AttackType
  severity:       number            // 1–10
  is_blocked:     boolean
  forensics_uri:  string
  tx_hash:        string
  block_number:   number
  gas_used:       number
  status:         TxStatus
}

export interface HealingEvent {
  id:                       string
  timestamp:                string
  ip:                       string
  action:                   "ISOLATED"
  attack_type:              AttackType
  trigger_score:            number
  edges_severed:            number
  duration_ms:              number
  network_stability_before: number
  network_stability_after:  number
}

export interface BlockedIPRecord {
  ip:            string
  blocked_at:    string
  reason:        "GNN_DETECTED" | "MANUAL_OVERRIDE"
  attack_type:   AttackType | null
  threat_score:  number
  blockchain_tx: string | null
}
```

---

## CHANGE LOG

| Version | Date | Change | Approved By |
|---------|------|--------|------------|
| v1.0 | Week 2 | Initial freeze | Sairaj, Susheep, Skanda, Sathvik |

> **To propose a change:** Open a PR, add entry to this table, get all 4 approvals.
