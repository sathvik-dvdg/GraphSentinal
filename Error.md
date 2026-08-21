# GraphSentinel Remaining Issues

Review date: 2026-08-22

Scope: frontend, backend, Mininet/OVS integration, blockchain bridge, Docker wiring, and verification commands. No source code was changed.

Goal: make the full application dynamic and functional by removing mock data and ensuring real data is used throughout.

## Verification Results

- Frontend production build passes: `npm.cmd run build`.
- Python compile pass succeeds: `python -m compileall backend\app mininet`.
- Backend tests do not run from a normal repository-root command because `app` is not importable unless `PYTHONPATH=backend` is set.
- ~~Backend tests still fail...~~ **[RESOLVED 2026-08-22]** `config.py` now points `env_file` at an absolute `backend/.env` path and sets `extra="ignore"` — the root `.env`'s `VITE_*` keys can no longer break settings loading regardless of working directory (see #7).
- Frontend build emits a large bundle warning: the generated JS bundle is about 2.67 MB before gzip. (Unchanged — not addressed this pass.)

## 2026-08-22 Follow-up Pass

Everything below the original scope (~30 open issues) was addressed in a second pass in the same session, after confirming the real WSL2 Mininet + enforcement daemon + Docker pipeline (see #8, #5 resolutions above). Verified live: full stack booted through `docker compose up`, a real simulated DDoS burst produced a real GraphSAGE score, a real OVS drop rule (confirmed via `ovs-ofctl dump-flows`), and a real Ganache transaction; the frontend was driven through a headless-Chromium session (login → dashboard → threat feed → forensics → blockchain ledger → network/org-pyramid view → live Simulate click) with zero console errors.

Three categories were deliberately left open as decisions bigger than a drive-by fix — see the "Not Addressed" note on each: real authentication (#18/#27), DB migrations (#29), and a dedicated durable audit-log table (#35, though #13/#14 cover its most-visible symptom via the existing Incident model). #39 (component de-duplication) is explicitly meant to happen after data contracts stabilize, so it's still open by design.

## 2026-08-22 Verification Pass (audit of the follow-up pass above)

Went back through every claimed fix and checked it against the actual code (not just re-reading my own summary) — grepped for orphaned exports, unused store fields, dead consumers, and re-ran the full backend compile + frontend build + a live Docker + headless-Chromium sweep across every route. Two real findings, both fixed:

- **New bug found (pre-existing, not introduced by the earlier pass): `NodeInspector.jsx`'s "Isolate Node" button (only reachable from the Network Topology → Org Pyramid view) never called the real block API.** It only mutated local optimistic state (`updateNodeStatus` → `nodeOverrides`), which the next 10s poll's `setGraphData()` would silently overwrite with the real (unchanged) backend state — so an operator could click "Isolate Node," see it apparently take effect, and have it silently revert ~10s later with zero indication nothing was actually enforced on the network. This is a different, more actively misleading bug than #23 (which was about the *other* block button, in `NodeDetailPanel.jsx`/`AppShell.jsx`, already fixed). Fixed by routing it through the same real `blockIP()` + immediate-refresh pattern as #23, and making the displayed status/badge derive from live `graphData` instead of the stale prop snapshot from when the panel opened. Verified live: clicking "Isolate Node" on `10.0.0.4` produced a real `priority=1000,ip,nw_src=10.0.0.4 actions=drop` OVS rule (confirmed via `ovs-ofctl dump-flows`) and the blocked count went 8→9 in the UI.
- **Pre-existing React key warning in `BlockchainLedger.jsx`**: the table row `.map()` used a bare `<>...</>` fragment shorthand with no key (not something the earlier pass introduced — it only edited content inside that block). Fixed with `<Fragment key={tx.id || i}>`.

Everything else checked out:
- No FastAPI route uses `response_model=`, so the `"Manual"`/`"Manual-Unblock"` `attack_type` values added in #13/#14 (outside the `AttackType` Literal in `schemas.py`) can't cause a validation 500 — confirmed live, they return fine.
- `EMPTY_STATE`, `simulateAttack`'s default-args-from-a-click-event behavior, and `AppShell.jsx`'s `handleBlock` all read correctly and match live behavior.
- `AlertCentre.jsx`'s acknowledge/resolve cycling and `Forensics.jsx`'s "Mark Resolved" are local-only by design (there's no backend field for alert/incident status to persist against) — not the same category of bug as the NodeInspector one, since neither claims to change network enforcement.

Two minor gaps noted, then fixed on request:
- **`"source": "configured"|"observed"` (#9) is now surfaced in the UI**, not just the API: a "Data Source" field in both `NodeDetailPanel.jsx` and `NodeInspector.jsx` ("◆ Observed traffic" / "○ Configured (no traffic yet)"), plus a visual treatment in all three graph views — dashed+dimmed hexagon/shape in `NetworkGraph2D.jsx` (`node[source="configured"]` style rule), a dimmed cloned material in `NetworkGraph3D.jsx` (kept separate from the shared cached material so it doesn't dim every node of that status), a dashed+dimmed card in `PyramidHierarchy.jsx`, and added to the 3D hover tooltip. `useNodeHierarchy.js` now threads `source` through into the hierarchy tree it builds so the Pyramid view has it too. Verified live: clicking a "configured, no traffic yet" host in both the 2D graph and the Org Pyramid shows the field correctly — including the edge case where a host is simultaneously `blocked` (persisted independent of current traffic) and `configured` (never appeared in the current flow batch), which renders sensibly as "Isolated — blocked" + "Configured (no traffic yet)" together.
- **`NetworkGraph2D.jsx` now has a working click handler.** Registered via `cy.on('tap', 'node', ...)`, looks the full node back up in `graphData` by id (cytoscape's own trimmed `data()` was missing `connections`/`bytes_total`/`attack_type`/`source` and used `threat` instead of `threat_score`, which would have rendered a broken detail panel), and calls back through a ref (not the `onNodeClick` prop directly) so the inline arrow function `NetworkTopology.jsx` passes doesn't force cytoscape to tear down and rebuild on every parent render. `NetworkTopology.jsx` now passes `onNodeClick={(node) => setSelectedNode(node)}`, matching the existing 3D graph wiring. Verified live: clicking a node in the 2D view opens the real `NodeDetailPanel` (not a stub) with correct data.

## Critical Issues Blocking Real Dynamic Data

### 1. [RESOLVED 2026-08-22] Frontend still ships and automatically loads mock data

Files:
- ~~`frontend/src/services/mockData.js`~~ (deleted)
- `frontend/src/store/useGraphStore.js`
- `frontend/src/hooks/useGraphData.js`

Fix applied: `mockData.js` is deleted (it had exactly one consumer). `setConnectionMode('mock')` now sets an explicit `EMPTY_STATE` (all-zero stats, empty graph/alerts/blocked/chain/timeline — the same shape the app already uses at boot before the first fetch) instead of calling `loadMockData()`. The existing `ConnectionModeBadge` already renders this as "OFFLINE"; it now pairs with genuinely empty data instead of fabricated numbers, so backend outages can no longer be mistaken for real security data.

Left as-is: `VITE_USE_MOCK` still exists as a manual override, but since it now only forces the honest empty/offline state (not fake data), it's no longer deceptive — kept as a way to preview the offline UI deliberately.

### 2. [RESOLVED 2026-08-22] Hierarchy data is hardcoded in the frontend

Fix: `getHierarchy()` deleted from `api.js`. `useNodeHierarchy.js` now derives the pyramid tree directly from live `graphData.nodes` (a flat root + real hosts, each with their real IP and live status) instead of a hardcoded org chart that referenced IPs (`10.0.0.11`) not even present on the configured 10-host topology. Verified visually — the Org Pyramid view shows real `h1`–`h10` / `10.0.0.x` nodes with live blocked/suspicious coloring.

Original text below, kept for context:

File:
- `frontend/src/services/api.js`

`getHierarchy()` returns a hardcoded `Promise.resolve(...)` tree instead of calling the backend or deriving hierarchy from live graph data.

Impact:
- The pyramid/hierarchy view is not dynamic.
- Node names, departments, levels, and status baselines can diverge from the real network.

Required fix:
- Add a real backend hierarchy endpoint, or derive the hierarchy from live graph/topology data.
- Remove the hardcoded tree.

### 3. [RESOLVED 2026-08-22] Simulation creates fake incidents instead of exercising the backend

Files:
- `frontend/src/store/useGraphStore.js`
- `frontend/src/components/layout/Topbar.jsx`
- `frontend/src/pages/Settings.jsx`

Fix applied: `simulateAttack()` now builds an attack-shaped flow batch (DDoS/PortScan/SSHBrute/Botnet patterns) and sends it through `POST /api/v1/analyze` — the same pipeline real OVS flows use. It then re-fetches graph/alerts/blocked/forensics/stats/timeline via the normal REST endpoints and writes the real response into the store. No more local-only fabrication, no `Math.random()` tx/incident hashes, no optimistic graph edits.

Verified live end-to-end through Docker with the real WSL2 Mininet + enforcement daemon running: a simulated DDoS burst produced a real GraphSAGE score (`ml_mode: "model"`, not the old hardcoded `0.94`), a real classification (`DoSHulk`, not always `DDoS`), `enforcement_status: "enforced"` with a confirmed real `priority=1000,ip,nw_src=10.0.0.2 actions=drop` rule on the live OVS bridge (`sudo ovs-ofctl dump-flows s1`), and a real transaction hash from the connected Ganache instance — not a random hex string.

Settings page "Inject Attack" now calls `simulateAttack({ attackType: injectType, targetIp: injectTarget })` instead of `alert(...)`.

Not changed: the "Simulate Speed" buttons and the rest of the Settings page (JSON import, blockchain config save) are still non-functional placeholders — out of scope for this fix (see #19).

### 4. [NOT ADDRESSED 2026-08-22] Backend ML inference can silently degrade to heuristics

Not addressed this pass: "make real-model mode mandatory" is a deployment-policy decision (should a missing model file be a hard startup failure?) rather than a drive-by fix, and a proper degraded-mode banner needs the same design pass the enforcement-mode badge got in #5 — worth doing as a follow-up in the same style, not bundled in here.

Files:
- `backend/app/config.py`
- `backend/app/services/inference_service.py`

The backend default allows degraded inference through `demo_allow_mock_ml=True` and `require_ml_model=False`. If Torch, weights, model class loading, or inference fail, the app falls back to `_heuristic_predict()`.

Impact:
- The UI can display threat scores as if they came from GraphSAGE when they are rule-based estimates.
- The API has `ml_mode` and `degraded_reason` in some responses, but the frontend does not surface them prominently.
- A missing or incompatible model can go unnoticed during demos or operation.

Required fix:
- Make real-model mode mandatory for production-like operation.
- Expose ML mode and degraded reason through stats/health data consumed by the UI.
- Show a visible degraded-mode banner when heuristics are being used.

### 5. [PARTIAL 2026-08-22] Enforcement defaults and Docker wiring can be simulated

Partial: "Surface enforcement mode and per-action enforcement status everywhere blocked state is displayed" is done — `enforcement_mode`/`demo_fallback_flows` are in `/api/v1/stats`, and `EnforcementModeBadge` in `Topbar.jsx` shows "SIMULATED ENFORCEMENT" vs "OVS ENFORCEMENT" globally (see #8's resolution note). Not done: "Require `ovs` mode for real operation" is a deployment-policy decision like #4, not something to enforce unilaterally — `simulated` remains a valid, selectable mode, just no longer a silently-indistinguishable one.

Files:
- `backend/app/config.py`
- `backend/app/services/enforcement_agent.py`
- `backend/app/services/self_healing.py`
- `docker-compose.yml`
- `.env`

`enforcement_mode` defaults to `simulated`, and Docker/environment defaults can keep enforcement simulated or inconsistent. In simulated mode, `block_ip()` records a block but does not apply an OVS rule.

Impact:
- The UI and database can report blocked/isolated nodes with no real network enforcement.
- Blockchain records can memorialize a block that did not happen on OVS.
- Users cannot reliably tell whether a block was enforced, pending, failed, or simulated.

Required fix:
- Surface enforcement mode and per-action enforcement status everywhere blocked state is displayed.
- Require `ovs` mode for real operation.
- Treat simulated mode as an explicit demo mode, not as normal blocking.

### 6. [RESOLVED 2026-08-22] Blockchain offline path returns mock status

Fix: `blockchain_adapter.py`'s disconnected-path status changed from `'mock'` to `'offline'` (added to `TxStatus` in `schemas.py`). `threat_analyzer.py`'s `_update_incident_after_actions` now also writes the resulting tx hash onto the matching `BlockedIP.blockchain_tx` row (previously always `None` for GNN-triggered blocks, since `block_ip()` runs before the blockchain write completes). Verified live: a manual block/unblock round trip showed real tx hashes on both the `Incident` and `BlockedIP` rows, and incident history correctly flipped `is_blocked` on unblock (see #13/#14).

Files:
- `backend/app/services/blockchain_adapter.py`
- `backend/app/services/threat_analyzer.py`
- `backend/app/api/v1/forensics.py`

When the blockchain adapter is disconnected, `store_incident()` returns `status: "mock"` with no transaction hash. Threat analysis still marks the incident as blocked and continues.

Impact:
- The application can proceed as if blockchain logging was part of the flow even when no on-chain write occurred.
- The frontend does not clearly separate confirmed, pending, error, and mock/offline states.
- `BlockedIP.blockchain_tx` is never populated by the self-healing block path, so blocked records can remain disconnected from the incident blockchain status.

Required fix:
- Replace "mock" with a clear offline/error state unless explicitly in demo mode.
- Store and expose transaction status, not only `tx_hash`.
- Reconcile incident, blocked-IP, and blockchain state so all views agree.

### 7. [RESOLVED 2026-08-22] Root environment file breaks backend settings initialization

Fix: `config.py`'s `env_file` is now an absolute path (`Path(__file__).resolve().parent.parent / ".env"`) instead of the CWD-relative `".env"` — the backend always loads `backend/.env` regardless of where the process is launched from. Also added `extra="ignore"` as defense in depth.

Files:
- `.env`
- `backend/app/config.py`

The backend settings model reads `.env` relative to the current working directory. From repository root, that loads frontend `VITE_*` values too. Pydantic rejects those keys, so tests fail during import before any application test runs.

Observed failure:
- `vite_backend_url`, `vite_use_mock`, and `vite_backend_api_token` are rejected as extra forbidden settings.

Impact:
- Backend startup/test behavior depends on working directory.
- A combined environment file can break the backend even when backend-specific env values are valid.

Required fix:
- Make backend env loading deterministic and backend-scoped.
- Either allow/ignore unrelated env keys or point the backend explicitly at its own env file.
- Add a test command/configuration that works from repository root.

### 8. [RESOLVED 2026-08-22] Root `.env` silently overrode Docker's safe defaults via compose variable substitution

File:
- `docker-compose.yml`
- `.env.docker`

Correction: `.env.docker` is present and is what `docker-compose.yml` loads via `env_file`; the original claim that it was missing was wrong. The real bug was different and more subtle: `docker-compose.yml`'s `environment:` block used `${DEMO_FALLBACK_FLOWS:-true}` / `${ENFORCEMENT_MODE:-simulated}` / `${THREAT_THRESHOLD:-0.75}` / `${DAEMON_TOKEN:?...}` — Compose auto-loads the repo-root `.env` (a *different* file, used for local/WSL2 dev) for that `${VAR}` interpolation, separately from the `env_file: .env.docker` directive. Verified with `docker compose config`: with this repo's root `.env` present (`DEMO_FALLBACK_FLOWS=false`, `ENFORCEMENT_MODE=ovs`), the backend container actually started with those values instead of `.env.docker`'s documented safe defaults — and since `DEMO_FALLBACK_FLOWS=false` won, a plain `docker compose up` with no WSL2 daemon running would silently return an empty flow list instead of the promised demo flows.

Fix applied:
- Removed the `${VAR}` interpolation for those four keys from `environment:` in `docker-compose.yml` so they come only from `env_file` (root `.env` no longer has any effect on Docker's runtime config).
- Added an optional second `env_file` entry, `.env.docker.local` (gitignored, `required: false`), for teammates who want to bridge to a real WSL2 Mininet daemon without touching the committed `.env.docker` or the root `.env`.
- Added a placeholder `DAEMON_TOKEN=docker-default-unset` to `.env.docker` so a fresh clone boots with zero manual setup.

Also added (issue #5): `enforcement_mode` and `demo_fallback_flows` are now returned by `/api/v1/stats` (`backend/app/services/graph_state.py`) and surfaced in the UI via a new `EnforcementModeBadge` next to the existing connection-mode badge in `Topbar.jsx`, so operators can see at a glance whether "blocked" means a real OVS rule or a simulated one.

## Backend Logic and Data Consistency Issues

### 9. [RESOLVED 2026-08-22] Graph endpoint always includes a static 10-host baseline

Fix: `graph_state.py`'s `_build_nodes()` now tags every node `"source": "configured"` (in the baseline topology, not seen in current traffic) or `"source": "observed"` (actually appeared in a flow). Added to `NodeData` schema. The baseline itself is kept (it matches the real `mininet/topologies/base_topology.py` 10-host topology, not an arbitrary placeholder) but is no longer indistinguishable from observed traffic.

File:
- `backend/app/services/graph_state.py`

`_build_nodes()` starts with `10.0.0.1` through `10.0.0.10` even if no live flows contain those hosts.

Impact:
- The graph is never a pure representation of observed topology.
- A fresh or disconnected backend can still show ten nodes.

Required fix:
- Build nodes from real topology/flow sources.
- If a baseline topology is desired, load it from an explicit real topology source and label it as configured topology, not observed traffic.

### 10. [PARTIAL 2026-08-22] Graph state is in memory and only the latest flow batch is represented

Partial fix: `GraphState.__init__` now rehydrates `_flows`/`_prediction` from the most recent `FlowSnapshot` rows (within `poll_interval_seconds × 3`) on startup, so a backend restart no longer shows a falsely-empty graph when there's actually-recent persisted traffic. The deeper architectural issue — single in-memory batch, no multi-worker support — is unchanged; that's a bigger redesign (define graph state as always-derived-from-SQLite) not attempted this pass.

File:
- `backend/app/services/graph_state.py`

The live graph is stored in process memory. `update()` replaces `_flows` with only the latest parsed/analyzed batch. Historical flow snapshots are persisted, but `/api/v1/graph` and `/api/v1/stats` do not rebuild from persisted data.

Impact:
- Restarting the backend loses current graph state even though SQLite contains snapshots.
- Empty OVS ticks do not clear stale graph state.
- Multiple workers/processes would have divergent graph state.

Required fix:
- Define a real graph state source of truth.
- Either persist current graph state or derive graph responses from recent `FlowSnapshot` rows over a configured window.

### 11. [RESOLVED 2026-08-22] Empty OVS parse leaves stale UI state

Fix: `monitor.py`'s poll loop now always calls `analyze_flows(flows)` — even with an empty list — instead of only when `flows` is truthy, so the graph correctly reflects "no current traffic" instead of leaving the last-seen state on screen forever. Also added `last_poll_at`/`last_flow_count`/`last_error` tracking, exposed via `/health`'s new `monitor` field.

Files:
- `backend/app/mininet_monitor/monitor.py`
- `backend/app/mininet_monitor/flow_parser.py`

The monitor only analyzes when `flows` is truthy. If OVS becomes unavailable or returns no relevant flows, no update is emitted and old graph data remains visible.

Impact:
- The dashboard can display stale threats after traffic stops or collection fails.
- Users get no data-source status saying live capture is disconnected, empty, or failing.

Required fix:
- Emit source status and empty-state updates.
- Track last successful capture time and expose it via stats/health.

### 12. [PARTIAL 2026-08-22] Demo fallback flows are still production code

Partial: `demo_flows()` still exists and is reachable via `DEMO_FALLBACK_FLOWS`, but the Docker env-shadowing bug that could silently enable it unintentionally is fixed (#8), and it's now correctly inert whenever the real daemon path is configured and reachable (verified live). Per-flow `source_type` labeling propagated through the whole pipeline (API responses included) is issue #34 — not done, since it's a cross-cutting schema change, not specific to this code path.

File:
- `backend/app/mininet_monitor/flow_parser.py`

`demo_flows()` remains in the backend flow parser and can be enabled via `DEMO_FALLBACK_FLOWS`.

Impact:
- Backend-originated synthetic data can enter the same analysis, database, alert, blocking, and blockchain pipeline as real OVS data.
- The current API does not expose whether a flow came from OVS or demo fallback.

Required fix:
- Remove fallback flows from production code, or gate them behind explicit demo mode with source labels propagated to every response.

### 13. [RESOLVED 2026-08-22] Manual block endpoint does not write blockchain records

Decision made: yes, manual block/unblock are ledger events, logged through the same `BlockchainAdapter.store_incident()` pipeline automatic GNN blocks use (`attack_type: "Manual"`), so there's one consistent audit code path instead of two divergent ones. Verified live: a manual block of `10.0.0.5` produced a real Incident row, a real Ganache tx hash, and `BlockedIP.blockchain_tx` populated.

File:
- `backend/app/api/v1/blocked.py`

Manual `/api/v1/block` calls use `SelfHealingEngine.block_ip()` and return `blockchain_tx: None`. They do not store a blockchain incident/action.

Impact:
- Manual blocks appear in blocked IPs but not in the ledger as auditable security actions.
- The app has inconsistent audit behavior between automatic GNN blocks and manual operator blocks.

Required fix:
- Decide whether manual block/unblock actions are ledger events.
- If yes, log them through the blockchain adapter and persist transaction status.

### 14. [RESOLVED 2026-08-22] Unblock does not update incident history

Fix: `/api/v1/block` unblock path now bulk-updates any `Incident` rows for that IP from `is_blocked=True` to `False`, and creates a durable closure `Incident` (`attack_type: "Manual-Unblock"`) logged through the blockchain adapter — giving a persisted block→unblock trail without building the full separate audit-log table from #35. Verified live: after unblocking, the original block incident's `is_blocked` flipped to `false` in `/api/v1/forensics`.

Files:
- `backend/app/api/v1/blocked.py`
- `backend/app/services/self_healing.py`

Unblocking removes a `BlockedIP` row but does not update related incidents or emit a durable unblock event.

Impact:
- Incident history can continue to say an incident was blocked while the IP has been unblocked.
- The UI cannot show a reliable block/unblock timeline.

Required fix:
- Add durable enforcement action records or status transitions.
- Emit and persist unblock events.

### 15. [RESOLVED 2026-08-22] Idempotency key suppresses repeated attacks within a minute

Fix: `_idempotency_key()` now folds in a digest of the actual attacked targets/ports from the related flows, so two genuinely different attack instances from the same IP in the same minute-bucket no longer collide. `_create_incident()` also no longer silently drops duplicates outright — on a key collision it returns the existing incident, and `evaluate()` retries enforcement if that incident's `enforcement_status` is still `"pending_enforcement"` instead of unconditionally skipping.

File:
- `backend/app/services/threat_analyzer.py`

Incident idempotency is based on IP, attack type, rounded score, severity label, and minute bucket.

Impact:
- Distinct repeated attacks from the same host within the same minute can be dropped.
- Suppressed incidents also skip healing/blockchain logic because `_create_incident()` returns `None`.

Required fix:
- Include flow evidence, target, ports, or a stable event window in idempotency.
- Avoid skipping enforcement state reconciliation just because an incident row already exists.

### 16. [RESOLVED 2026-08-22] Timeline buckets are UTC time labels without dates

Fix: `timeline_service.py` returns full ISO datetimes (`current.isoformat()`) instead of `HH:MM` strings. Frontend formats them via a new `formatTimelineTick()` util (`XAxis`/`Tooltip` in `DashboardPage.jsx` and `TimelineAnalytics.jsx`) — caught live via screenshot: the chart initially rendered raw ISO strings on the x-axis until the tickFormatter was added, confirming the "let the UI format them" half of the fix was necessary, not optional.

File:
- `backend/app/services/timeline_service.py`

Timeline points use `HH:MM` only.

Impact:
- Windows crossing midnight are ambiguous.
- Frontend charts cannot distinguish same time labels across days.

Required fix:
- Return bucket start timestamps as ISO datetimes and let the UI format them.

### 17. [RESOLVED 2026-08-22] Forensics assumes chain ID 1337

Fix: added `get_chain_id()` to `web3_client.py` (`self.w3.eth.chain_id`) and `BlockchainAdapter.chain_id()`; `/api/v1/forensics` returns the real value. Also fixed 3 frontend spots that independently hardcoded "Chain 1337" as static text (`Forensics.jsx`, `ForensicsModal.jsx`, `BlockchainLedger.jsx`, `BlockchainPanel.jsx`) — added a `chainId` store field populated from the real forensics response. (The real Ganache chain ID happens to also be 1337 in this dev environment, so the displayed number is unchanged — but it's now a live value, not a hardcode, and would show correctly against any other chain.)

File:
- `backend/app/api/v1/forensics.py`

The response hardcodes `chain_id: 1337`.

Impact:
- The UI can report the wrong chain if Ganache or another network uses a different chain ID.

Required fix:
- Read chain ID from the connected Web3 provider.

### 18. [NOT ADDRESSED 2026-08-22] Request auth is an API key, but frontend login is fake

Not addressed: this needs a decision on scope (real session auth with what backend? single operator or multi-user? SSO?) that's the user's to make, not something to decide unilaterally. `useAuthStore.js` already documents the demo-gate intent explicitly in comments, and `LoginForm.jsx` already shows a prominent "LOCAL DEMO MODE" banner — so the immediate operator-facing honesty gap is smaller than the required fix implies. Still open: real auth, if wanted.

Files:
- `frontend/src/store/useAuthStore.js`
- `frontend/src/components/auth/LoginForm.jsx`
- `frontend/src/services/api.js`
- `backend/app/api/v1/deps.py`

Frontend login accepts any non-empty credentials. Protected backend calls use an environment API token that defaults to `change-me-for-demo`.

Impact:
- There is no real operator identity, session, role, or audit trail.
- Anyone with app access can enter the dashboard in local/demo mode.

Required fix:
- Implement real authentication if this is meant to be a secure operational app.
- Otherwise, surface demo authentication status inside the authenticated app, not only on the login screen.

## Frontend Functional Issues

### 19. [NOT ADDRESSED 2026-08-22] Settings controls are local-only

Not addressed: wiring detection thresholds/isolation thresholds/network config to real backend endpoints means designing new config-mutation endpoints and persistence, which is meaningfully more scope than the fixes in this pass. The one piece that was in scope for #3 — the "Inject Attack" button — is fixed (calls the real backend now instead of `alert()`); the rest of the Settings page (thresholds, Ganache URL/contract/gas, hierarchy import) is unchanged.

File:
- `frontend/src/pages/Settings.jsx`

Detection thresholds, isolation thresholds, lateral sensitivity, hierarchy import, node editor placeholder, Ganache URL, contract address, and gas limit are local React state or alert popups only.

Impact:
- Users can change settings that do not affect backend behavior.
- The UI suggests runtime configurability that does not exist.

Required fix:
- Back settings with real backend endpoints, persisted config, validation, and reload behavior.
- Remove or disable controls until they are functional.

### 20. [RESOLVED 2026-08-22] WebSocket URL bypasses the Vite proxy

Fix: `WS_URL` now defaults to `undefined` (same-origin — rides the Vite/Docker `/socket.io` proxy exactly like REST calls) instead of hardcoding `http://localhost:8000`. `VITE_BACKEND_URL` remains available as an explicit override for unusual cross-origin deployments. (Verified separately that both `vite.config.js` and the Docker-specific `vite.config.docker.js` already proxy `/socket.io` correctly — the bug was purely the browser-side default, not the dev-server proxy config.)

File:
- `frontend/src/hooks/useWebSocket.js`

`WS_URL` defaults to `http://localhost:8000`, while REST calls use the `/api` proxy.

Impact:
- Local and Docker deployments can connect REST and WebSocket to different backends/ports.
- In Docker, a browser pointed at host port 5174 may still try `localhost:8000` unless env values are correct.

Required fix:
- Derive socket URL from the same deployment config as REST.
- Prefer same-origin socket paths when behind Vite/proxy.

### 21. [RESOLVED 2026-08-22] WebSocket hook freezes callback closures

Fix: `useWebSocket.js` now stores callbacks in a ref updated every render (`callbacksRef.current = {...}`) and the socket event handlers call through the ref instead of closing over the props directly. The socket connection effect still has empty deps (no needless reconnects), but handlers now always run current logic. This directly fixes a real latent bug: `SimulationProvider.jsx`'s `handleGraphUpdate`/`handleAlert`/`handleHealingTriggered` guard on `connectionMode === 'simulating'`, and before this fix that check was permanently evaluating the `connectionMode` value from the *first* render (`'connecting'`) since the socket handlers were frozen at mount — simulation/live transitions were never actually being honored by the socket callbacks.

File:
- `frontend/src/hooks/useWebSocket.js`

The socket effect has an empty dependency array and intentionally suppresses hook dependencies. It captures the initial callback functions.

Impact:
- Callback logic depending on later `connectionMode` values can be stale.
- Simulation/live transitions may not be honored correctly by socket event handlers.

Required fix:
- Store callbacks in refs that are updated every render, or include safe dependencies while avoiding unnecessary reconnects.

### 22. [RESOLVED 2026-08-22] REST polling can partially update mixed-generation data

Fix: `useGraphData.js` rewritten around a `RESOURCE_FETCHERS` map — each resource (graph/alerts/blocked/forensics/stats/timeline) is fetched and applied independently, and a new `dataErrors` store field (keyed by resource name) records per-resource failure instead of leaving cross-panel state silently inconsistent with no signal. A failed fetch deliberately does *not* clear that resource's last-known data (blanking a security panel on a transient error reads as false "all clear"); it only marks it stale. Full "backend aggregate endpoint" redesign wasn't attempted — this is the lighter per-resource-freshness half of the required fix, paired with #26's visible indicator.

File:
- `frontend/src/hooks/useGraphData.js`

`Promise.allSettled()` updates each successful response independently. If graph succeeds but alerts/forensics/timeline fail, the UI can show new graph data with old alerts or old ledger data.

Impact:
- Cross-panel data can disagree without a visible error.
- Users may see a node blocked in one panel and not in another.

Required fix:
- Track per-resource freshness/error state.
- Prefer backend aggregate endpoints or version/timestamp responses to keep related data consistent.

### 23. [RESOLVED 2026-08-22] Block action does not refresh state after success

Fix: `AppShell.jsx`'s `handleBlock()` now re-fetches graph/blocked/stats immediately after a successful block/unblock instead of waiting for the next 10s poll. Also fixed a real bug found while reading this code: the node-detail panel was calling `setSelectedNode(null)` (closing the panel as if the action succeeded) *outside* the try/catch, so it closed unconditionally — even when `blockIP()` threw. It now only closes on confirmed success, and failures are logged with the real error instead of a misleading "unavailable in mock mode" message that fired for every kind of failure.

File:
- `frontend/src/components/layout/AppShell.jsx`

`handleBlock()` calls the block API and closes the selected node, but it does not refresh graph, blocked IPs, alerts, or stats immediately.

Impact:
- Users can block an IP and see stale graph/status until the next poll or socket update.

Required fix:
- Refresh affected data or optimistically update only after a successful real backend response.

### 24. [RESOLVED 2026-08-22] Pyramid statuses use values outside backend schema

Fix: added `suspicious`/`malicious` entries to `pyramidConfig.js`'s `STATUS_COLORS` (previously only had the UI-derived `infected`/`attacking`/`isolated` plus `normal`/`blocked` — the raw backend vocabulary had no matching style and would silently fall back to the default). This matters more now that #2 makes the hierarchy read `graphData.node.status` (real backend vocabulary) directly, rather than only the alert/healing-event-derived vocabulary `useNodeHierarchy.js` used to compute in isolation.

Files:
- `frontend/src/hooks/useNodeHierarchy.js`
- `backend/app/models/schemas.py`

Hierarchy status values include `isolated`, `attacking`, and `infected`, while backend node statuses are `normal`, `suspicious`, `malicious`, and `blocked`.

Impact:
- UI components can diverge in status vocabulary and color mapping.
- Backend-provided status cannot be reused directly in hierarchy views.

Required fix:
- Normalize status vocabulary or add a clear mapping layer with typed values.

### 25. [PARTIAL 2026-08-22] Forensics and blockchain field shapes are not normalized

Partial fix: `forensics.py` now runs every chain record through `_normalize_chain_record()`, explicitly extracting a fixed field set (`id`/`tx_hash`/`block_number`/`incident_hash`/`timestamp`/`source_ip`/`attack_type`/`severity`/`is_blocked`/`gas_used`) with `.get()` defaults, instead of forwarding `adapter.client.get_all_incidents()`'s raw shape directly — the response schema is now stable even if the two different code paths inside `web3_client.get_all_incidents()` (event-log vs. count-fallback) diverge further. A real `blockchain_error` field is also now returned and surfaced in `Forensics.jsx` (previously a static "Ganache may be offline" guess regardless of actual cause). Not done: a full Pydantic response model enforcing this at the FastAPI layer.

Files:
- `frontend/src/pages/Forensics.jsx`
- `frontend/src/pages/BlockchainLedger.jsx`
- `frontend/src/components/dashboard/BlockchainPanel.jsx`
- `backend/app/api/v1/forensics.py`

The frontend expects transaction fields such as `tx_hash`, `block_number`, `gas_used`, `attack_type`, and `severity`, but `blockchain_records` comes directly from `adapter.client.get_all_incidents()` without an API normalization layer.

Impact:
- Ledger/forensics views can render blank or misleading fields if the Web3 client shape changes or differs from mock data.

Required fix:
- Normalize blockchain records in the backend API schema.
- Add frontend empty/error states for missing fields.

### 26. [PARTIAL 2026-08-22] Error states are often swallowed or logged only

Partial fix: the `dataErrors` tracking from #22 now feeds a new `DataFreshnessBadge` in the Topbar — visible, not just console-logged, whenever any panel's last fetch failed (hover shows which resource(s) and why). `AppShell.jsx`'s block/unblock error handling (#23) and `Forensics.jsx`'s blockchain error (#25) were also fixed to show real errors. Not done: a per-panel inline stale/error indicator on every individual page (Forensics, Blockchain Ledger, Threat Feed, etc.) — the Topbar badge is a single global signal, not per-panel.

Files:
- `frontend/src/hooks/useGraphData.js`
- `frontend/src/components/layout/AppShell.jsx`
- `frontend/src/pages/Forensics.jsx`

Several failures are caught and logged or ignored without visible user feedback.

Impact:
- Users cannot tell whether data is missing because there are no incidents, the backend is down, blockchain is offline, or parsing failed.

Required fix:
- Add visible error and stale-data states for core panels.

## Security and Operational Issues

### 27. [NOT ADDRESSED 2026-08-22] Default API token is still demo-grade

Not addressed — same decision boundary as #18 (real auth). See that entry.

Files:
- `backend/app/config.py`
- `frontend/src/services/api.js`
- `.env`
- `frontend/.env`

The default token is `change-me-for-demo`, and the frontend embeds it as a Vite env value.

Impact:
- The protected analyze/block endpoints are only protected by a shared value exposed to the browser.

Required fix:
- Use real authentication/session tokens for browser clients.
- Keep service API keys server-side only.

### 28. [RESOLVED 2026-08-22] CORS origins are hardcoded

Fix: added `cors_origins` (comma-separated string) + `cors_origins_list` property to `config.py`, defaulting to the same 3 origins that were hardcoded before (no behavior change out of the box). `main.py`'s `CORSMiddleware` and the Socket.IO server's `cors_allowed_origins` both now read from `settings.cors_origins_list` instead of a literal list duplicated in two places.

File:
- `backend/app/main.py`

CORS and Socket.IO allowed origins are hardcoded to localhost ports.

Impact:
- Non-local deployments require source changes or will fail.
- Production origin policy is not configuration-driven.

Required fix:
- Move allowed origins to validated configuration.

### 29. [NOT ADDRESSED 2026-08-22] SQLite schema is created with `create_all` only

Not addressed: adding a migration tool (Alembic or similar) is a new dependency and workflow decision, not something to introduce unilaterally. Flagging that this pass *did* add two new columns implicitly relied upon (nothing schema-breaking — `source`/`chain_id` etc. are API-response fields, not new DB columns) so no migration was actually needed for this pass's changes specifically.

Files:
- `backend/app/database.py`
- `backend/app/models/incident.py`

The app initializes tables directly without migrations.

Impact:
- Schema changes can break existing databases or silently leave missing columns.

Required fix:
- Add migrations for persisted deployments.

### 30. [RESOLVED 2026-08-22] Flow snapshots can grow without retention

Fix: added `flow_snapshot_retention_hours` setting (default 24h) and a prune step in `graph_state.py`'s `_persist_snapshots()` — deletes `FlowSnapshot` rows older than the retention window on every write, using the existing `captured_at` index.

File:
- `backend/app/services/graph_state.py`

Every analyzed flow is inserted into `flow_snapshots`, but there is no retention, compaction, or cleanup.

Impact:
- Long-running systems can grow the SQLite database indefinitely.

Required fix:
- Add retention policy and indexes aligned to timeline/graph queries.

## Mininet, OVS, and Daemon Issues

### 31. [PARTIAL 2026-08-22] Flow parsing may miss non-TCP/UDP or OpenFlow variants

Partial: added ICMP detection to protocol classification. Full coverage of every OVS output variant needs real-world sample data from varied traffic types to test against, which wasn't available this pass — left as best-effort.

File:
- `backend/app/mininet_monitor/flow_parser.py`

The parser depends on text patterns such as `nw_src=`, `nw_dst=`, `n_packets=`, `n_bytes=`, `tp_src=`, and `tp_dst=`.

Impact:
- Real OVS output variants may be ignored.
- Empty parsed flow sets can make live traffic appear absent.

Required fix:
- Prefer structured OVS output where available, or expand parser coverage with tests using real daemon outputs.

### 32. [RESOLVED 2026-08-22] TCP flags are inferred rather than parsed

Fix: `flow_parser.py` no longer hardcodes `tcp_flags: 2` for every TCP line. It now looks for an actual `tcp_flags=` field in the OVS output (hex or decimal) and defaults to `0` (unknown) if absent, rather than fabricating a SYN flag that inflates heuristic-mode scoring (`inference_service.py`'s `tcp_flags & 2` check).

File:
- `backend/app/mininet_monitor/flow_parser.py`

Parsed TCP flows set `tcp_flags` to `2` for every TCP line.

Impact:
- SYN-based heuristic scoring can be inflated for ordinary TCP flows.

Required fix:
- Parse actual flags where possible, or stop populating flags with synthetic values.

### 33. [RESOLVED 2026-08-22] Reconciliation runs even when enforcement is simulated

Fix: `main.py`'s lifespan now only starts `ReconciliationWorker` when `settings.enforcement_mode == "ovs"`. Verified live: with `ENFORCEMENT_MODE=ovs` (real-daemon mode), `/health` showed `reconciliation.status: "ok"` with matching `db_blocked`/`ovs_blocked` counts, confirming it both starts correctly when appropriate and genuinely reconciles real state.

Files:
- `backend/app/main.py`
- `backend/app/services/reconciliation.py`

The reconciler starts during app startup regardless of whether enforcement mode is simulated or OVS.

Impact:
- In simulated/no-OVS deployments, reconciliation can report errors or misleading status.

Required fix:
- Start reconciliation only when OVS enforcement is enabled and daemon config is valid.

## Data Model Gaps

### 34. [PARTIAL 2026-08-22] No first-class data source field

Partial: graph nodes now carry `source: "configured" | "observed"` (#9). A full `source_type`/`data_source` field threaded through flow parser → analysis pipeline → alerts → forensics → stats API responses is a larger cross-cutting schema change spanning most of the backend's response models — not attempted this pass beyond the graph-node piece.

Affected areas:
- flow parser
- analysis pipeline
- graph response
- stats response
- alerts
- forensics

There is no durable field identifying whether data came from live OVS, manual analyze submission, backend demo fallback, or frontend simulation.

Impact:
- Fake/demo/manual/live data are indistinguishable after they enter the pipeline.

Required fix:
- Add `source_type`/`data_source` and propagate it through storage and API responses.

### 35. [PARTIAL 2026-08-22] No durable enforcement action table

Partial: #13/#14 give manual block/unblock a durable, blockchain-logged trail by reusing the existing `Incident` model (closure rows for unblock), which covers the most visible symptom (incident history lying about current block state). A dedicated append-only enforcement-action/event table (distinct from `incidents`, covering daemon errors, reconciliation actions, requested-vs-enforced-vs-failed states) is a real new table + migration (see #29) — not attempted this pass.

Affected areas:
- self-healing
- manual block/unblock
- incidents
- blocked IPs

The current model has `incidents` and current `blocked_ips`, but no event log for block attempts, unblock attempts, status changes, daemon errors, or reconciliation actions.

Impact:
- The app cannot provide a complete audit timeline.
- Forensics cannot distinguish requested, enforced, simulated, failed, and removed actions over time.

Required fix:
- Add a durable enforcement action/event model.

### 36. [PARTIAL 2026-08-22] Current graph and incident IDs are not globally stable

Partial: removing the frontend's fake `simulateAttack()` (#3) eliminated the one source of genuinely random, non-persisted IDs (`demo-${Date.now()}`, `Math.random()` hex hashes) — every alert ID is now always `alert-{incident.id}` from a real SQLite row, matching the "use stable event IDs from persisted records only" requirement for that path. Blockchain record IDs (`raw.id` / event-derived) and graph state (still in-memory, see #10) are unchanged.

Affected areas:
- incident alert IDs
- demo alert IDs
- blockchain records
- graph state

Alert IDs are formatted from SQLite IDs, while demo IDs are timestamp/random values. Graph state is in memory.

Impact:
- Cross-view linking and refresh behavior can be inconsistent.

Required fix:
- Use stable event IDs from persisted records only.

## UI/UX Correctness Issues

### 37. [RESOLVED 2026-08-22] Timestamps often omit dates

Fix: added a shared `formatEventTimestamp()` util (`frontend/src/utils/formatTimestamp.js`) and applied it everywhere a `.toLocaleTimeString()`-only call displayed a historical event/incident/tx timestamp: `DashboardPage.jsx`, `BlockchainLedger.jsx`, `Forensics.jsx`, `SelfHealing.jsx` (×2), `ForensicsModal.jsx`, `SelfHealStatus.jsx`, `AlertPanel.jsx`. `ThreatFeed.jsx`'s own local copy of the same formatter was deduplicated into the shared util. Deliberately left as time-only: live wall-clocks (`Topbar.jsx`, `StatsBar.jsx`) and the `SimulationProvider.jsx` rolling-window chart bucket labels — neither is "historical event data," so a bare time is correct there.

Affected pages include forensics, ledger, dashboard recent threats, self-healing, and topbar.

Impact:
- Multi-day data is ambiguous.

Required fix:
- Return ISO timestamps from the backend and render date plus time where event history is shown.

### 38. [RESOLVED 2026-08-22] Transaction hashes are truncated without copy affordances

Fix: new `CopyableHash` component (`navigator.clipboard.writeText` + check-mark confirmation, `e.stopPropagation()` so it doesn't trigger a parent row's click handler) applied everywhere a hash was truncated: `ThreatFeed.jsx`, `BlockchainLedger.jsx` (table + expanded row), `Forensics.jsx` (detail row, evidence block, records table), `ForensicsModal.jsx`, `BlockchainPanel.jsx`.

Affected areas:
- ledger
- forensics
- threat feed
- blockchain panel

Impact:
- Users cannot reliably inspect or copy the full transaction hash.

Required fix:
- Add click-to-copy for full hash values and show copy confirmation.

### 39. [NOT ADDRESSED 2026-08-22, BY DESIGN] Page-level components duplicate dashboard panel logic

Not addressed — per the "Recommended Fix Order" at the bottom of this doc, this is explicitly meant to happen *after* the real-data contracts (chain_id, timestamps, hash display, error states) stabilize, which just happened this pass. It's now a reasonable next step (e.g. extract `CopyableHash`'s and `formatEventTimestamp`'s callers into shared row/card components), but wasn't bundled into this pass since it's a pure refactor with no functional bug attached.

Affected areas:
- forensics page/modal
- blockchain ledger/panel
- threat feed/alert panel
- repeated pill/stat components

Impact:
- Fixes to field mapping, copy behavior, empty states, and timestamps must be repeated in multiple places.

Required fix:
- Extract shared content/row/card components after real-data contracts are stabilized.

## Recommended Fix Order

1. Fix backend environment loading and test command so the backend can boot reliably from repository root.
2. Remove frontend mock data loading and replace it with explicit offline/error/empty states.
3. Make data source explicit across backend and frontend: live OVS, manual analyze, demo fallback, or simulation.
4. Replace frontend-only simulation with backend-driven analyze/demo traffic.
5. Require or visibly surface real ML model mode, blockchain connection status, and enforcement mode.
6. Normalize backend API schemas for graph, stats, forensics, blockchain records, and settings.
7. Persist current graph/enforcement action history instead of relying on in-memory or current-state-only records.
8. Wire settings controls to real backend endpoints or remove inactive controls.
9. Add visible error and stale-data states throughout the UI.
10. Add tests for no-mock operation, degraded ML behavior, blockchain offline behavior, OVS parse samples, manual block/unblock, and frontend API field mapping.
