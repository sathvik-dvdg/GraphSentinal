# GraphSentinel v2 — backend integration contract

**For Sairaj.** This replaces `NODE_FEATURES.md`. The short version: stop
importing a Python class, start reading a JSON contract and calling an HTTP
endpoint. Nothing in your service should ever again know how many features the
model takes.

---

## What broke, and why

v1 pinned three things into your code:

```python
from model import GraphSAGEClassifier          # code coupling
model = GraphSAGEClassifier(in_channels=7)     # frozen feature count
scaler = pickle.load(open("scaler.pkl"))       # frozen distribution
```

Every one of those had to change to fix a modelling defect, and none of them
could change without breaking your build. So the ML work was pinned by an
import statement. That is the thing being removed — not just the number 7.

---

## The new contract

### 1. Read `model_card.json`

Everything you need is in it, machine-readable, versioned:

```jsonc
{
  "contract_version": "2.0.0",
  "graph":  { "node_entity": "ip_address", "edge_entity": "network_flow",
              "window_seconds": 60 },
  "inputs": {
    "node_features": { "count": 16, "names": ["log_out_degree", ...] },
    "edge_features": { "count": 20, "names": ["log_duration_s", ...] },
    "categorical":   { "edge_dst_port": {"vocab": 121}, ... }
  },
  "outputs": {
    "classes": ["BENIGN","DDoS","PortScan","Botnet","SSHBrute","DoSHulk"],
    "threat_score": "1 - softmax(logits)[BENIGN]"
  },
  "artifacts": { "weights": {"sha256": "..."} }
}
```

Read `contract_version` at startup. Fail loudly on a major-version bump rather
than silently mis-feeding the model. Check the `sha256` if you care whether the
weights on disk are the ones you were given.

### 2. Send flows, receive verdicts

```
POST /flows      {"flows": [ {...}, {...} ]}
GET  /contract   -> model_card.json
GET  /health     -> liveness, memory occupancy, drift state
POST /flush      -> force-close the current window
```

Each flow is a dict using CICFlowMeter column names — `graphsentinel/inference/
capture.py::FLOW_SCHEMA` is the authoritative list. You send raw flows. The
service does windowing, graph construction, scaling, memory and inference. You
do none of it.

Response, per closed window:

```jsonc
{
  "results": [{
    "window_start": 1499282400.0,
    "window_end":   1499282460.0,
    "n_flows": 8134, "n_hosts": 412, "latency_ms": 47.2,
    "detections": [{
      "ip": "172.16.0.99", "attack_class": "PortScan",
      "threat_score": 0.97,
      "class_probs": {"BENIGN": 0.03, "PortScan": 0.94, ...},
      "out_degree": 3122, "in_degree": 4
    }],
    "rules":    [ /* FlowRule objects, with the evidence that produced each */ ],
    "openflow": [ /* ready-to-install OFPFlowMod dicts */ ],
    "drift":    {"drifted": false, "max_z": 1.4, "feature_name": "log_total_bytes"}
  }]
}
```

### 3. Install rules — this is the part v1 could not do

v1 gave you a per-flow probability and you had to `max()` it up to an IP, then
guess what to block. Now every alert carries its own enforcement:

```python
for result in response["results"]:
    for rule in result["openflow"]:
        controller.install(rule)      # exact 5-tuple match, finite timeout
```

`rules[i]` and `openflow[i]` are the same rule in two forms — the first with
the evidence (`confidence`, `node_confidence`, `reason`), the second ready for
Ryu / ONOS / OpenDaylight. Every rule also renders as an `ovs-ofctl` string for
lab validation.

Mitigation is chosen per attack class, because the right response differs. A
DDoS gets a meter, not a drop — the victim still has to serve everyone else. A
brute force gets only its target port dropped, so the host stays reachable. A
botnet beacon gets a drop plus a quarantine flag, because one beacon means
there are more.

**Safety rails you should keep on.** The translator defaults to `dry_run=True`.
Before you flip it: set `allow_networks` to include your gateways, DNS
resolvers, and the controller itself. An IDS with write access to the network is
a denial-of-service tool when it is wrong, and it will sometimes be wrong. Every
rule carries a finite `idle_timeout` and `hard_timeout` by design — nothing
this system installs is permanent.

### 4. Scaling — do not pickle a scaler

`scaler.pkl` is gone. It was fitted once on an offline snapshot, and traffic is
not stationary: 03:00 does not look like 14:00, and a new service deployment
shifts byte volumes permanently. A frozen scaler turns that into false
positives that get worse every week.

The service now tracks feature statistics with an EMA (`edge_scaler.json`,
`node_scaler.json` are warm-start seeds, not frozen values). It reports a
`drift` verdict on every window. Surface `drifted: true` to your operators —
it means the live distribution has moved more than 3σ from what the model was
trained on, and it is clamped there rather than followed. That clamp is
deliberate: without it, an attacker who ramps traffic slowly enough could walk
the "normal" band out to meet their attack.

---

## Migration path

You do not have to do this in one step.

**Step 0 — nothing breaks.** `from graphsentinel.models.compat import
GraphSAGEClassifier` still works, still loads v1 weights. It emits a
`DeprecationWarning` and nothing else changes.

**Step 1 — new model, old method names.**

```python
from graphsentinel.models.compat import LegacyBinaryAdapter
adapter = LegacyBinaryAdapter(v2_model)
threat = adapter.predict_proba(window_graph)   # (N,) per-host, same as v1
```

You keep your `THREAT_THRESHOLD = 0.75` logic. You lose the manual
flow→IP `max()` aggregation, because hosts are nodes now — the aggregation the
old contract asked you to implement is the graph itself.

**Step 2 — the service.** Delete the model import. `POST /flows`. This is the
end state, and after it the ML side can ship a completely different
architecture without touching your code.

---

## What you should delete

| v1 artefact | status |
|---|---|
| `from model import GraphSAGEClassifier` | deprecated; shim keeps it alive |
| `in_channels=7` | retired — 16 node features, 20 edge features, and both are read from the card |
| `scaler.pkl` | retired — EMA scaler JSON |
| manual flow→IP `max()` aggregation | retired — IPs are nodes |
| `THREAT_THRESHOLD` on a binary score | still valid, but prefer `attack_class` — the playbook differs per attack |
| `NODE_FEATURES.md` | replaced by this document + `model_card.json` |
