# GraphSentinel — Decision Log

> **Purpose:** Decisions that block implementation. Each item below is not a
> code problem — it is a policy or architecture call that only the project
> owner can make. Once you answer each question, the code becomes mechanical
> and can be written immediately.
>
> Items are ordered from smallest blast-radius (one config line) to largest
> (infrastructure redesign).

---

## Decision #4 — ML Model Failure Mode

### What this controls
`config.py` has two settings that together decide what happens when the
GraphSAGE weights file is missing, `torch` fails to load, or the model
throws an error at inference time:

```
require_ml_model: bool = False        # Docker default: False
demo_allow_mock_ml: bool = True       # Docker default: True
```

Combined effect of the four possible combinations:

| `require_ml_model` | `demo_allow_mock_ml` | What happens on model failure |
|---|---|---|
| `False` | `True` (**current**) | Silently falls back to heuristic scorer. App keeps running, no banner, no log warning visible in UI. |
| `False` | `False` | Falls back to heuristic scorer, but `degraded_reason` is populated in the API response so the UI can show a warning banner. |
| `True` | `True` | Startup still succeeds (allow_mock wins). This combination is contradictory and effectively the same as the first row. |
| `True` | `False` | **Hard fail.** `RuntimeError` is raised inside `InferenceService.__init__()`. Uvicorn/FastAPI startup will abort. The backend container will crash-loop. |

### The real question
> **If the model weights are missing or broken, should the backend refuse to
> start — or should it start in degraded mode and tell the user?**

**Option A — Fail hard** (`require_ml_model=True`, `demo_allow_mock_ml=False`)

- Backend will not start without valid weights.
- Guarantees threat scores always come from the GNN — no silent heuristic.
- Risk: any weights file corruption or missing file kills the entire service,
  including the dashboard, blockchain, and all other unrelated features.
- Appropriate if: this is a production security tool where heuristic scores
  are considered worse than no scores at all.

**Option B — Degrade with visible warning** (`require_ml_model=False`, `demo_allow_mock_ml=False`)

- Backend starts even without the model.
- The API response includes `mode: "degraded"` and `degraded_reason: "weights not found"`.
- The frontend can read these fields and show a persistent warning banner.
- Threat scores are still computed (heuristically) — the dashboard stays usable.
- Appropriate if: you want the monitoring dashboard to always be available,
  even when ML infrastructure has a problem.

**Option C — Current (silent degradation)** (`demo_allow_mock_ml=True`)

- Everything the same as B, but no warning is shown anywhere.
- **Recommended to move away from this** — it is the worst of both worlds:
  the model might not be running and nobody knows.

### Recommended answer
**Option B.** Hard-failing the whole backend because of a model file is
disproportionate for a monitoring system. But silent degradation is dangerous
for a security tool. Degraded-with-banner is the right middle ground.

### What becomes code once you decide
One line in `.env.docker` / `config.py`:
```
DEMO_ALLOW_MOCK_ML=false
```
Plus: the frontend reads `stats.ml_mode` / `stats.degraded_reason` from the
`/api/v1/stats` response (already returned by `graph_state.stats_response()`)
and shows a banner. That is the only code change.

---

## Decision #5 — Enforcement Mode: Should "Simulated" Ever Be Rejected?

### What this controls
`enforcement_mode` in `config.py` / `.env` controls whether `block_ip()` in
`enforcement_agent.py` issues a real OVS flow rule via the daemon, or just
logs and returns `"simulated"`.

Current valid values: `"simulated"` (default) | `"ovs"`

There is no validation that rejects an invalid value, and there is no
configuration that makes `"simulated"` an error.

### The real question
> **Should there be any environment (production, graded demo, etc.) where
> `enforcement_mode=simulated` is explicitly rejected as a misconfiguration?**

**Option A — No, simulated always stays a valid mode**

- `"simulated"` is a legitimate deployment option forever (Docker, dev, CI).
- No changes needed.
- Risk: someone accidentally runs `enforcement_mode=simulated` in a
  real-network deployment and thinks IPs are actually being blocked.

**Option B — Add a `require_real_enforcement` flag**

- A new config field: `require_real_enforcement: bool = False`
- When `True`, startup rejects `enforcement_mode=simulated` with a clear error.
- Operators who need guaranteed real blocking can set this flag and it acts
  as a safety net against misconfiguration.
- When `False` (default), `"simulated"` is always valid — Docker/dev
  workflows are unaffected.

**Option C — Warn but never reject**

- Keep `"simulated"` always valid.
- But: always log a startup warning when `enforcement_mode=simulated` so it
  appears in the container log:
  ```
  [WARN] Enforcement mode is SIMULATED — no OVS flow rules will be applied.
  ```
- Cheapest option. No config change needed, just one `logging.warning()` call
  in `EnforcementAgent.__init__()`.

### Recommended answer
**Option C** now (trivial, one line), with Option B available later if a
production real-network deployment becomes a goal. There is no Mininet+OVS
production deployment target defined yet, so Option B would be premature.

### What becomes code once you decide
Option C: one `logging.warning()` call in `EnforcementAgent.__init__()`.
Option B: one new `bool` field in `Settings` + one `if` block in the same
`__init__`.

---

## Decision #12 — Synthetic Demo Flows: Delete or Keep?

### What this controls
`flow_parser.py` → `demo_flows()` returns two hardcoded flows whenever the
OVS daemon is unreachable AND `DEMO_FALLBACK_FLOWS=true`. This is the only
way the system has any data in Docker (no Mininet).

### The real question
> **Should `demo_flows()` and the `DEMO_FALLBACK_FLOWS` config flag be
> permanently removed, or kept as a documented "no-Mininet demo path"?**

**Option A — Delete the synthetic flow path entirely**

- Remove `demo_flows()` from `flow_parser.py`.
- Remove `DEMO_FALLBACK_FLOWS` from `config.py` and all env files.
- When the OVS daemon is unreachable, the parser returns `[]` (empty list).
- The graph shows only the baseline configured hosts (`10.0.0.1–10.0.0.10`)
  with zero threat scores — which is honest.
- **Consequence:** Docker mode shows a mostly-empty, mostly-static graph.
  The GNN still runs (on an empty input) but produces no interesting output
  because there is no traffic to score. The dashboard is accurate but boring.
- Appropriate if: you consider synthetic data deceptive and want Docker mode
  to look exactly like "no data" rather than fake data.

**Option B — Keep as a fully labeled, opt-in demo mode**

- `demo_flows()` stays, but `DEMO_FALLBACK_FLOWS` defaults to `False` in all
  environments (including Docker).
- Docker operators who want the "looks alive" experience explicitly set
  `DEMO_FALLBACK_FLOWS=true` in their `.env.docker`.
- The UI shows a persistent banner: *"⚠ Demo mode — synthetic traffic only"*
  whenever `demo_fallback_flows=true` is detected in the stats response.
  (This field is already returned by `graph_state.stats_response()` line 153.)
- Appropriate if: teammates without Mininet still need a meaningful demo
  experience, as long as it is clearly labeled.

**Option C — Current (keep, defaults to true in Docker, no UI label)**

- Already documented as a problem in `Error.md` Issue 8.
- Not recommended going forward.

### Recommended answer
**Option B.** Demo flow data has real value for onboarding, grading, and
testing the full pipeline without a Mininet setup. The problem is not that it
exists — the problem is that it is invisible. Making it opt-in and adding the
UI banner turns it from "deceptive" into "useful and honest".

### What becomes code once you decide
Option A: delete ~25 lines across 2 files.
Option B:
1. Change `.env.docker`: `DEMO_FALLBACK_FLOWS=true` (stays true, intentional
   for Docker — no change needed there, it is already documented).
2. Change `config.py` default: `demo_fallback_flows: bool = False` (so local
   dev without Docker doesn't accidentally get fake flows).
3. Frontend reads `stats.demo_fallback_flows` (already in the API response)
   and shows a banner. That is the only new UI code.

---

## Decision #19 — Lateral Movement Detection: What Does It Mean in This System?

### What this controls
The Settings page has a "Lateral Movement Sensitivity" slider. Currently, this
slider writes to a Zustand store state variable but **there is no lateral
movement detection algorithm anywhere in the backend.** The slider is purely
cosmetic — changing it has no effect on threat scores, alerts, or the graph.

### The real question
> **What should "lateral movement" mean in the context of the GraphSentinel
> graph model, and should it be implemented?**

This is a spec decision, not a code decision. There are several reasonable
definitions:

**Definition A — Fan-out from a single source to many destinations**

A host is flagged for lateral movement if it makes connections to more than N
distinct destination IPs within one poll window. N is the "sensitivity" slider
value (higher sensitivity = lower N = flag sooner).

- Easy to implement in `graph_state.py` or `threat_analyzer.py`.
- Does not require the GNN — it is a structural graph metric.
- Risk of false positives: a DNS server, gateway, or scanner legitimately
  talks to many IPs.

**Definition B — Graph traversal: A→B→C chains**

A host is flagged if it appears as a destination in one flow and a source in
a different flow within the same window, suggesting it was compromised and is
now attacking further.

- More interesting from a GNN perspective — can be encoded as a graph
  feature.
- Requires tracking the direction of flows over time, not just the current
  snapshot.
- Would need a new field in `FlowSnapshot` or a separate query.

**Definition C — Do nothing, remove the slider**

Remove the lateral movement controls from the Settings page. The slider is
misleading because it implies a feature that does not exist.

- Honest, but loses a visible feature.

### Recommended answer
Decide which definition (A or B) matches your project's scope and whether
this is in scope for the current sprint. If it is not, **implement Option C
(remove the slider) now** — a non-functional slider is worse than no slider
because it implies correctness. Add it back when the detection algorithm is
ready.

### What becomes code once you decide
Definition A: ~30 lines in `threat_analyzer.py` + one new config field
`lateral_movement_threshold: int`. The slider wires to this via a new
`PATCH /api/v1/settings` endpoint.

Definition B: ~60 lines + a new `FlowTraversalEvent` model + an Alembic
migration. More work but more academically interesting.

Definition C: Delete ~20 lines from `Settings.jsx`.

---

## Decision #10 / #36 — In-Memory Graph State and Multi-Worker Scaling

### What this controls
`graph_state.py` maintains the live graph as a Python object in process
memory (`class GraphState`). This works perfectly for a single-worker
deployment (one uvicorn process, one thread). The `_lock = Lock()` guards
concurrent reads.

The problem emerges only if you ever want:
- Multiple uvicorn workers (`--workers N`)
- Multiple backend container replicas (horizontal scaling in Kubernetes/ECS)
- A separate process that needs to read or write graph state (e.g. a
  dedicated WebSocket process)

In any of these cases, each process has its own independent `graph_state`
instance, and they will diverge immediately. One worker will see threats that
another worker blocked. The WebSocket messages from worker A will contradict
the REST responses from worker B.

### The real question
> **Is multi-worker or multi-instance backend deployment ever a goal for this
> project?**

**Option A — No, single-worker forever (current)**

- No changes needed.
- `graph_state = GraphState()` as a module-level singleton is correct and
  safe for one process.
- The current `_rehydrate_from_snapshots()` on startup already handles
  backend restarts gracefully by reading recent `FlowSnapshot` rows from
  SQLite.
- **This is the right answer for a research/academic project or a
  single-node deployment.**

**Option B — Yes, multi-worker is a goal**

This requires moving graph state out of process memory. Two paths:

| Path | Mechanism | Complexity |
|---|---|---|
| **SQLite-derived state** | Every `graph_response()` call queries SQLite instead of reading the in-memory dict. The poll cycle writes to SQLite; reads come from SQLite. | Medium — no new infrastructure. Adds DB latency to every graph request (~10–50 ms on SQLite). |
| **Redis shared state** | `graph_state` is replaced by a Redis client. The in-memory dict becomes a Redis hash. | High — new infrastructure dependency. Adds Redis to docker-compose. Adds operational overhead. Near-zero latency. |

**Option C — Defer**

Keep single-worker now. Add a comment in `graph_state.py` explaining the
single-worker assumption. Revisit only if deployment actually demands scaling.

### Recommended answer
**Option A / C.** For a research/security tool running on one node, the
in-memory approach is the correct design — it is fast, simple, and has no
infrastructure dependencies. Multi-worker scaling should only be pursued if
there is a concrete deployment requirement (e.g. handling >1000 concurrent
dashboard users). Do not add Redis or SQLite-read-path overhead speculatively.

### What becomes code once you decide
Option A/C: Add one comment to `graph_state.py`. No code change.
Option B (SQLite path): Refactor `graph_response()` and `stats_response()` to
be database-read functions. ~100–150 lines across `graph_state.py` and
potentially `graph.py` / `stats.py` API routes.

---

## External Blocker #31 — OVS Flow Parser: Missing Traffic Variants

### What this controls
`flow_parser._parse_output()` uses regex patterns to extract IP addresses,
port numbers, packet counts, and byte counts from raw `ovs-ofctl dump-flows`
text output.

The parser was written against your 10-host TCP topology. It works for TCP
flows with `nw_src=` / `nw_dst=` / `n_packets=` fields. It silently drops any
line that does not have both `nw_src=` and `nw_dst=`.

### What is known to be missing

| Traffic type | OVS output format | Parser behavior |
|---|---|---|
| **ARP** | `arp,arp_spa=10.0.0.2,arp_tpa=10.0.0.1` | **Dropped** — uses `arp_spa`/`arp_tpa` not `nw_src`/`nw_dst` |
| **ICMP** | `icmp,nw_src=10.0.0.2,nw_dst=10.0.0.1,tp_src=0,tp_dst=8` | Parsed if `nw_src` present, but `tp_src/tp_dst` will be 0 (ping type/code, not ports) |
| **IPv6** | `ipv6,ipv6_src=...,ipv6_dst=...` | **Dropped** — uses `ipv6_src`/`ipv6_dst` not `nw_src`/`nw_dst` |
| **UDP** | `udp,nw_src=...,nw_dst=...,tp_src=...,tp_dst=...` | Parsed correctly |
| **OVS 2.x vs 3.x field names** | Some OVS versions use `dl_src`/`dl_dst` for L2, different ordering | Unknown — depends on version |
| **Table/cookie metadata** | `table=0,cookie=0x...` prefix fields | Ignored (correct — not needed) |

### Why this cannot be solved without real dumps

The exact format of `ovs-ofctl dump-flows` varies by:
- OVS version (2.x vs 3.x vs the version in your WSL2 image)
- Flow table configuration in your Mininet topology
- Which traffic your topology actually generates

Synthesizing parser test cases without real output would just be guessing.
Any extended parser written without real samples will break on the first
actual deployment.

### What is needed to unblock this

From a live Mininet session, run:
```bash
sudo ovs-ofctl dump-flows s1 -O OpenFlow13
```

Send the raw text output (copy-paste from terminal is fine). Even 20–30 lines
covering a mix of TCP, ARP, ICMP, and UDP flows will be enough to extend the
parser to cover all real-world cases.

**This is the only item in the entire backlog that requires external input.**
Everything else can be coded from what is already in the repository.

---

## Summary

| # | Decision | Size of resulting code change | Status |
|---|---|---|---|
| #4 | ML model fail mode (hard fail vs degrade-with-banner) | 1 config line + ~20 lines frontend | **Awaiting your answer** |
| #5 | Enforcement simulated mode: warn or reject | 1–5 lines backend | **Awaiting your answer** |
| #12 | Delete synthetic flows or keep as labeled demo path | 2–20 lines across 3 files | **Awaiting your answer** |
| #19 | Lateral movement: which definition, or remove slider | 20–60 lines + possible migration | **Awaiting your answer** |
| #10/#36 | Multi-worker scaling: needed or not | 0 (no) or ~150 lines (yes) | **Awaiting your answer** |
| #31 | OVS parser extension | ~40 lines | **Blocked — needs real `dump-flows` output** |
