# Frontend handover

For Susheep. Written from the code on branch `fix/audit-p0-p1` at `5fd69a6`
(the frontend was last changed in `ae34631`; `5fd69a6` added only the demo
scripts). No source file was changed to write this. Every file and line cited
was read; where something could only be confirmed in a browser, it says so.

One thing to hold on to while reading: **nothing in the frontend changes of
2026-10-05 has been seen rendered.** It builds, it lints, and 16 unit tests pass
(`node --test tests/unit/*.test.js` from `frontend/`). Section 6 is the list of
what you need to look at.

---

## 1. What the frontend is

A React 18 single-page app built with Vite 8, with Zustand 5 for state,
Tailwind 4 (through `@tailwindcss/postcss`) for utility classes, the Socket.IO
client for live pushes and axios for REST. Graphs are drawn with
`react-force-graph-3d` / three.js and Cytoscape, charts with Recharts. The entry
point is `frontend/src/main.jsx`, which renders `App.jsx`; `App.jsx` holds the
routes. Start it with `npm run dev` from `frontend/` (serves
`http://localhost:5173`; `npm ci` first if `node_modules` is missing) and build
it with `npm run build`.

Two environment variables change behaviour (`frontend/.env.example`):

| Variable | Read in | Effect |
|---|---|---|
| `VITE_BACKEND_URL` | `src/services/api.js:16`, `src/hooks/useWebSocket.js:15` | Base URL for REST and the socket. Unset, both go to the same origin and ride the Vite proxy, which targets `http://localhost:8000` (`vite.config.js:9-23`). On the manual path the backend is on **8001**, so set `VITE_BACKEND_URL=http://localhost:8001` in `frontend/.env` or the dashboard will read OFFLINE. |
| `VITE_USE_MOCK` | `src/hooks/useGraphData.js:9`, `src/components/layout/Topbar.jsx:18`, `src/pages/Settings.jsx:11` | `true` stops all polling, forces the OFFLINE state, and enables the Simulate Attack button. It does not work well against a running backend: see BUG FE-21. |

There is no `VITE_API_URL`; the name in older notes is wrong. Never put a secret
in a `VITE_` variable: the browser receives every one of them.

---

## 2. Page inventory

Routes are in `src/App.jsx:49-76`. Everything except the first two sits inside
`ProtectedRoute` → `SimulationProvider` → `AppShell`.

| Page (file) | Route | What it shows | Own hook / own API calls |
|---|---|---|---|
| `LandingPage.jsx` | `/` | Marketing page. Redirects a signed-in user to `/dashboard` (`:108-111`). | None. |
| `LoginPage.jsx` | `/login` | Clerk's `<SignIn>` beside a decorative, hard-coded "terminal". | None: sign-in is Clerk's. |
| `DashboardPage.jsx` | `/dashboard` | Four stat cards, five recent threats, three recent healing events, a mini timeline. | None; reads the store. |
| `NetworkTopology.jsx` | `/network` | 3D or 2D graph plus the pyramid hierarchy. Adds a configured controller and switch around the hosts (`utils/topologyScaffold.js`). | None for data. The pyramid's `NodeInspector` calls `POST /api/v1/block`. |
| `ThreatFeed.jsx` | `/threats` | The alert list with severity, type, IP and time filters. | None; reads `alerts` from the store. |
| `Forensics.jsx` | `/forensics` | Incident list, one incident's detail and derived timeline, and the on-chain records table. | `useForensicsData`: its **own** `GET /api/v1/forensics` every 5 s. `PATCH /api/v1/incidents/{id}/status` for Mark Resolved. |
| `BlockchainLedger.jsx` | `/blockchain` (titled "Audit & Ledger") | Tab 1: on-chain records. Tab 2: the enforcement log. CSV / JSON export. | Reads the store. Export calls `GET /api/v1/forensics?limit=500` or `GET /api/v1/enforcement-actions?limit=500`. |
| `TimelineAnalytics.jsx` | `/timeline` | The timeline chart, an hourly table and attack types per hour. | None; reads the store. |
| `SelfHealing.jsx` | `/healing` | Healing event feed, a stability gauge, a response log table. | None; reads the store. |
| `AlertCentre.jsx` | `/alerts` | Threat alerts and healing notices as one list, with an open → acknowledged → resolved cycle. | `useAlerts` (derives from the store). `PATCH /api/v1/incidents/{id}/status`. |
| `AuditLog.jsx` | `/audit` | Who did what: manual blocks, settings changes. Admin only; a 403 is shown as "needs admin". | Own `GET /api/v1/audit-logs` on mount and on Refresh; no polling. |
| `Settings.jsx` | `/settings` | Simulation controls, the threat threshold, model reload, read-only chain config. | Own `GET /api/v1/settings` on mount; `PATCH /api/v1/settings`; `POST /api/v1/ml/reload`. |

Two overlays live in the shell and are available on every protected page:
`NodeDetailPanel` (Block / Unblock, `POST /api/v1/block`) and `ForensicsModal`
(its own `GET /api/v1/forensics` every 3 s while open).

---

## 3. Data flow: how the UI stays live

### Two feeds, one store

`SimulationProvider` (`src/providers/SimulationProvider.jsx`) mounts once, above
the shell, and starts both feeds. Pages do not fetch the shared data themselves;
they read the Zustand store.

**REST polling.** `useGraphData` (`src/hooks/useGraphData.js`) fetches nine
resources together with `Promise.allSettled`, at mount and then every 10 s
(`:72-76`). Each has its own entry in `RESOURCE_FETCHERS` (`:16-32`):

| Resource | Endpoint | Store setter |
|---|---|---|
| `graph` | `GET /api/v1/graph` | `setGraphData` |
| `alerts` | `GET /api/v1/alerts?limit=50` | `setAlerts`, then `reconcileResolvedWithServer` |
| `blocked` | `GET /api/v1/blocked` | `setBlockedIPs` |
| `forensics` | `GET /api/v1/forensics` | `setChainTxs`, `setChainId` (the incident list in this response is **not** stored; the Forensics page fetches its own) |
| `stats` | `GET /api/v1/stats` | `updateStats` |
| `timeline` | `GET /api/v1/timeline?last=60min` | `setTimeline` |
| `health` | `GET /health` | `setMlHealth` (v1), `setMlV2Health` (v2). Nothing else from `/health` is kept: not `blockchain`, not `monitor`. |
| `enforcement` | `GET /api/v1/enforcement-actions?limit=100` | `setEnforcementActions` |
| `healing` | `GET /api/v1/healing?limit=50` | `setHealingEvents` |

**Socket.** `useWebSocket` (`src/hooks/useWebSocket.js`) opens one Socket.IO
connection, authenticated with the Clerk session token. Three events arrive, all produced by v1's pipeline
(`backend/app/websocket/events.py:73`, `:79`, `:85`):

| Event | Handler (`SimulationProvider.jsx`) | Store slices updated |
|---|---|---|
| `graph_update` | `handleGraphUpdate` (`:29-33`) | `connectionMode` → `'live'`; `graphData`, `graphTruncated`, `lastDataAt` via `setGraphData`. The payload is capped by the server at 50 nodes and 100 links. |
| `alert` | `handleAlert` (`:35-39`) | `alerts` via `addAlert` (newest first, capped at 50, an id already present is skipped); one point appended to `timeline`. |
| `healing_triggered` | `handleHealingTriggered` (`:41-45`) | `healingNodeId` for 3.5 s (the highlight), `healingEvents` via `addHealingEvent`, one point appended to `timeline`. |

Two details you will notice in a browser. `addHealingEvent` keeps only the newest
**10** events (`useGraphStore.js:193-196`) while the poll loads 50, so a pushed
event shortens the list until the next poll restores it. And the timeline points
the socket appends are not the server's five-minute buckets, so the chart's last
point can jump when the next poll replaces the array.

The first two handlers do nothing while `connectionMode` is `'simulating'`.

### The connection badge

The badge is drawn by `ConnectionModeBadge.jsx` from two facts in the store, and
the wording is decided in one pure function, `connectionDisplay`
(`src/utils/connection.js:44-55`):

- `connectionMode`: does REST answer? Set from polls by `modeAfterPoll`
  (`connection.js:32-38`, applied at `useGraphData.js:57-58`), keyed on whether
  **the graph fetch** of that poll succeeded.
- `socketStatus`: what the socket is doing. `'connected'` or `'reconnecting'`
  from `setConnected` (`useGraphStore.js:374-375`); `'reconnecting'` for
  attempts 1 to 5 and `'lost'` from attempt 6 on, from `socketStatusFor`
  (`connection.js:23-25`) via `useWebSocket.js:64`.

| Badge text | When |
|---|---|
| `CONNECTING` | Before the first poll has come back. |
| `LIVE` | REST answers and the socket is connected (or has not reported yet). |
| `RECONNECTING…` | The socket dropped and is in its five fast retries (2 s apart), whether or not REST still answers. |
| `CONNECTION LOST — RETRYING` | REST was answering and has stopped (`'offline'`), and the socket's fast retries are used up. |
| `LIVE (POLLING) — SOCKET RETRYING` | REST answers, the socket has been down for more than five attempts. Data is current, by polling. |
| `OFFLINE` | The backend was never reached (`'mock'`): the very first poll failed, or `VITE_USE_MOCK=true`. Entering this state blanks every panel (`useGraphStore.js:114-121`). |
| `SIMULATION` | A simulated attack is in progress. |

Transitions, in order, when the backend dies while you are looking at `LIVE`:

1. The socket's `disconnect` fires. `onDisconnect` sets `socketStatus` to
   `'reconnecting'` and triggers a poll at once (`SimulationProvider.jsx:56`).
   The badge reads `RECONNECTING…`.
2. That poll's graph fetch fails. `modeAfterPoll('live', false)` gives
   `'offline'`. The panels keep their data.
3. After five failed socket attempts (about 10 s) `socketStatus` becomes
   `'lost'`. The badge reads `CONNECTION LOST — RETRYING`. The socket keeps
   trying for ever: 5 s, 10 s, 20 s, then every 30 s (`connection.js:17-20`).

A successful poll from any state except `'simulating'` returns the mode to
`'live'`. A `graph_update` push also sets it to `'live'` directly.

### The stale-data badge

Each of the nine resources has a slot in `dataErrors`. After every poll each
slot is set to `null` if its fetch succeeded, or to a short reason if it failed
(`useGraphData.js:61-69`): `HTTP <status>` when the server answered with an
error, `timed out` on an axios timeout, `no answer` otherwise
(`connection.js:81-86`). A failed fetch leaves that resource's last data in the
store untouched; that is deliberate, so a transient error never blanks a
security panel.

`DataFreshnessBadge.jsx` renders `STALE: <RESOURCE> (<REASON>), …` for every
non-null slot. The header shows all nine; each page also shows one filtered to
the resources it draws. A slot clears on the next successful fetch of that
resource. Nothing else clears it.

---

## 4. Store structure

### `useGraphStore` (`src/store/useGraphStore.js`)

| Key | Type | Holds |
|---|---|---|
| `graphData` | `{ nodes, links }` | The current graph. `setGraphData` merges into existing node objects so the 3D layout keeps its coordinates. |
| `graphTruncated` | boolean | Whether the last graph payload said `truncated`. Only socket payloads carry that field. |
| `alerts` | array | v1 incidents as alerts, newest first, at most 50. |
| `blockedIPs` | array | Currently blocked hosts. |
| `chainTxs` | array | On-chain records from `/forensics`. |
| `chainId` | number or null | The chain id the backend is connected to; null when it is not. |
| `mlHealth` | `{ mode, degraded_reason }` | v1's state. `mode` is `'model'` or `'degraded'`. |
| `mlV2Health` | object or null | `/health`'s `ml_v2`. Null until `/health` has answered once. |
| `healingEvents` | array | Block events. 50 from the poll, cut to 10 by a socket push. |
| `healingNodeId` | string or null | The host to highlight; cleared by one timer after 3.5 s. |
| `timeline` | array of `{ time, threats, blocked }` | Twelve five-minute buckets from the poll, plus socket-appended points. |
| `enforcementActions` | array | The enforcement audit trail, newest 100. |
| `lastDataAt` | ms epoch or null | When graph data last landed. Drives "Updated Ns ago" on the dashboard. |
| `stats` | object | `total_nodes`, `active_threats`, `blocked_ips`, `system_health` (clamped 0 to 100), `total_packets`, `total_bytes`, `enforcement_mode`, `demo_fallback_flows`. |
| `nodeOverrides` | `{ ip: status }` | Local status overrides read by `useNodeHierarchy`. |
| `resolvedIncidentIds` | number[] | Optimistic "resolved" overlay, persisted in `localStorage`. Cleared by every successful fetch except ids still in flight. |
| `resolveInFlight` | number[] | Incident ids whose PATCH has not returned. Not persisted. |
| `dataErrors` | `{ resource: string or null }` | Section 3. |
| `connectionMode` | `'connecting' \| 'live' \| 'offline' \| 'mock' \| 'simulating'` | Section 3. |
| `socketStatus` | `'idle' \| 'connected' \| 'reconnecting' \| 'lost'` | Section 3. |
| `initialLoadDone` | boolean | False until the first poll has returned. |
| `modeBeforeSimulation` | string or null | The mode a simulation interrupted, restored by `endSimulation`. |
| `use3D`, `selectedNode`, `forensicsOpen`, `isConnected` | UI state | `selectedNode` opens `NodeDetailPanel`; `forensicsOpen` opens the modal. |

`isMockMode` and `isSimulating` are legacy getters; nothing outside the store
reads them. `simulateAttack` (`:240-329`) posts synthetic flows tagged
`data_source: 'simulation'` to `POST /api/v1/analyze` and then re-fetches seven
resources.

### Session and role (Clerk)

The session is Clerk's. `App.jsx` (`AxiosInterceptorSetter`) adds the Clerk token
as a `Bearer` header to every request, and `useSessionUser`
(`src/hooks/useSessionUser.js`) reads the role from `publicMetadata.role`. The
old `useAuthStore` and its operator login were removed in the repo cleanup:
nothing used them after the move to Clerk.

Role enforcement is in two places and you need both in mind:

- **The backend decides.** The role comes from the Clerk session
  (`publicMetadata.role`, `backend/app/api/v1/deps.py`). Block, unblock, the
  threshold, model reload and the audit log require `admin`. Triage and
  `/analyze` refuse `readonly` only (`deps.py:63-87`).
- **The frontend shows it.** `canEnforce(role)` is `role === 'admin'`
  (`src/utils/triage.js:28-30`). `AppShell.jsx` and `NodeInspector.jsx` read the
  role from `useSessionUser()` and disable Block / Unblock / Isolate with the
  reason in text; `Settings.jsx` does the same for the threshold and Reload Model.

A 401 is only logged to the console by the axios response interceptor: there is
no app-level logout. BUG FE-02 (restarting the backend logs everyone out) was
about the old in-memory sessions and no longer applies.

---

## 5. Colour system

`src/constants/colors.js` is one object, `GS`, holding every colour the app
draws with, by name. Before `ae34631` the components carried these as hex
literals. (`OPEN_ITEMS.md` says 661; the comment at the top of `colors.js` says
658 across 32 files, 34 distinct values. The files disagree by three; I could
not tell which count is right.) They were moved to a JS module, not to Tailwind
classes, because most are used where a class cannot reach: Cytoscape and
three.js styles, Recharts props, canvas fills, and inline styles that append an
alpha suffix such as `${color}40`.

`tailwind.config.js:4` imports `GS` and exposes six of its values as utilities
(`gs-danger`, `gs-success`, `gs-primary`, `gs-subtle`, `gs-surface-header`,
`gs-border-strong`, lines 58-63), so a class and an inline style cannot drift.
The other `gs-*` tokens in that file are still literal hex values in the config.

`tests/unit/colors.test.js` enforces three things: no `.js` or `.jsx` file under
`src/` other than `colors.js` contains a hex colour literal; every `GS` value is
a lowercase 6- or 8-digit hex; every `GS.<name>` a component references exists.
It does not look at `tailwind.config.js` or `globals.css`, and it does not catch
`rgba(...)` literals, of which the pages still have many.

**There are two palettes.** The pages draw with `GS.danger` (`#e03c3c`),
`GS.textSubtle` (`#727a86`) and `GS.success` (`#12a672`). The Tailwind tokens
define a different red and grey: `gs-threat` (`#D92D2D`) and `gs-muted`
(`#5A616E`). Both sets are now named in `colors.js`. Merging them changes how
the app looks, so it is a design decision and it has not been made (BUG FE-16).

---

## 6. Bugs to fix or verify

Three groups. FE-01 to FE-13 are open item 1: built, unit-tested where there is
logic, never seen in a browser. FE-14 to FE-20 are open item 14: decisions that
need a person. FE-21 to FE-30 are things I found while reading the pages and
hooks; none is in `OPEN_ITEMS.md` yet.

Commits, so the "what was done" lines are exact: `72601c1` did B17, B19 and B20;
`3cf55ab` did the connection state, the socket retry schedule, B18 and the
simulate gate; `ae34631` did the colour module and removed dead CSS.

### Open item 1: look at it in a browser

### BUG FE-01: The header badges have never been seen and may wrap or be clipped
**File:** `src/components/layout/Topbar.jsx:89-113`; `src/components/ui/DetectionPathBadge.jsx:32`; `src/components/ui/ConnectionModeBadge.jsx:69`
**What is wrong:** The top bar is 48 px high with `overflow: hidden`. Its left group holds the page title and up to six badges in one row: connection, enforcement, `BLOCKS: v1 MODEL · v2: …`, heuristic scoring, stale data, demo mode. That group is allowed to shrink and scrolls sideways, with its scrollbar hidden (`gs-no-scrollbar`), so a badge pushed off the right edge leaves no visible sign that it exists. Only the connection and detection-path badges set `whitespace-nowrap`; `EnforcementModeBadge`, `MlModeBadge`, `DataFreshnessBadge` and `DemoModeBadge` do not, so their text may wrap onto a second line and be cut by the 48 px height. The longest labels are `LIVE (POLLING) — SOCKET RETRYING` and `DEMO MODE — SYNTHETIC TRAFFIC ALLOWED`.
**How to reproduce:** Open the dashboard at the projector's resolution and at laptop width (below 1280 px the centre telemetry is hidden by `globals.css:637-638`). Check each of the four v2 states: `DRY-RUN` (v2 on), `OFF` (backend started without `GS2_ENABLED`), `NO ANSWER` (v2 on, inference service stopped), `UNKNOWN` (the moment before the first `/health` answer).
**What done / what remains:** The badge reads `ml_v2.enabled` from `/health` and its text stands alone without a tooltip. Not seen rendered. If it clips, the fix is `whitespace-nowrap` on the four badges and a decision on which badge yields first.

### BUG FE-02: Connection badge transitions when the backend stops
**File:** `src/utils/connection.js:32-55`; `src/hooks/useGraphData.js:57-58`; `src/hooks/useWebSocket.js:61-72`, `:102-112`
**What is wrong:** Nothing known. The rule is that the badge follows whether REST answers, not whether a socket once connected, and seven unit tests cover the pure functions. What has not been checked is the real sequence in a browser: that the badge leaves `LIVE` within one poll, passes through `RECONNECTING…` to `CONNECTION LOST — RETRYING`, and that the socket really does keep retrying.
**How to reproduce:** With the dashboard on `LIVE`, stop the backend (Ctrl+C in its terminal). Expect `RECONNECTING…` at once, `CONNECTION LOST — RETRYING` after about 10 s, panels still showing their last data. Watch the browser's network tab for socket attempts continuing past the fifth. **Then note what happens when you start the backend again:** its sessions were in memory, so the first poll returns 401 and you are sent to the login page with "Your session ended". That is correct behaviour, but it means a backend restart can never show you `LIVE (POLLING) — SOCKET RETRYING` or the return to `LIVE`. To see those two, keep the backend running and block only the socket: in the browser's dev tools, block requests matching `/socket.io/`, wait past five retries, then unblock.
**What done / what remains:** Implemented in `3cf55ab`. Not seen. One more thing to watch: a backend that hangs instead of refusing connections takes the axios timeout of 15 s (`api.js:27`) to fail a poll, so "within one poll" can be 15 s, not instant.

### BUG FE-03: The stale badge and its reason text
**File:** `src/hooks/useGraphData.js:61-69`; `src/utils/connection.js:81-86`; `src/components/ui/DataFreshnessBadge.jsx:17-31`
**What is wrong:** When the backend is down, all nine fetches fail together, so the header badge becomes one string of nine entries: `STALE: GRAPH (NO ANSWER), ALERTS (NO ANSWER), BLOCKED IPS (NO ANSWER), …`. That is roughly 200 characters in a 10 px mono font inside the same crowded row as FE-01, on a badge with no `whitespace-nowrap`. It will not fit. The per-page badges are short (one to three resources) and should be fine.
**How to reproduce:** Stop the backend with the dashboard open and read the header. Then test the other reason: an endpoint that answers with an error shows `HTTP <status>`. There is no switch for that in the app; the simplest way is to override one request in the browser's dev tools (for example, make `/api/v1/alerts` return 500) and wait for the next poll.
**What done / what remains:** The reason is in the text, not only in a tooltip (`3cf55ab`). Not seen. Decide what the header shows when everything is stale: probably `STALE: ALL (NO ANSWER)` when every slot has the same reason.

### BUG FE-04 (B17): A blocked alert reads "open" with a "Host blocked" marker
**File:** `src/utils/triage.js:10-12`; `src/hooks/useAlerts.js:21-41`; `src/pages/AlertCentre.jsx:202-215`
**What is wrong:** Before the fix a blocked alert was shown as "resolved" and could not be acknowledged or reopened. Now the status comes only from the server's `alert_status`, and blocking is shown as a separate `Host blocked` chip beside the status button.
**How to reproduce:** Run one attack (section 8). In Alert Centre the new alert must read `open` and carry the blue `Host blocked` chip. Click the status: it must move to `acknowledged`.
**What done / what remains:** Done in `72601c1`, two unit tests. Not seen. One leftover from the old rule is still in the sidebar: see FE-30.

### BUG FE-05 (B18): A triage click must not flicker back
**File:** `src/pages/AlertCentre.jsx:67-87`; `src/store/useGraphStore.js:171-177`
**What is wrong:** After a successful save, the row used to fall back to the server's old status for up to 10 s, until the next poll. The fix writes the confirmed status into the store (`applyAlertStatus`) before the optimistic local entry is removed.
**How to reproduce:** Click an alert's status button and watch that one row for 15 s. It must change once and stay.
**What done / what remains:** Done in `3cf55ab`. No unit test covers the ordering; it needs eyes.

### BUG FE-06 (B19): An incident reopened on the server must reappear
**File:** `src/utils/triage.js:17-20`; `src/store/useGraphStore.js:342-366`; `src/hooks/useForensicsData.js:34`; `src/pages/Forensics.jsx:31-39`
**What is wrong:** "Mark Resolved" on Forensics used to hide an incident on that device for ever, even after the server reopened it. Now the local list is only an overlay for requests still in flight and is cleared by every successful fetch.
**How to reproduce:** Mark an incident resolved on Forensics; it leaves the list. Reopen it in Alert Centre by cycling its status round to `open`. Go back to Forensics: it must be in the list again within one refresh (5 s).
**What done / what remains:** Done in `72601c1`, two unit tests. Not seen. Note that Forensics has no way to show resolved incidents or to reopen one; that is only possible from Alert Centre. And the same permanent-overlay problem still exists for Alert Centre's own local statuses: FE-24.

### BUG FE-07 (B20): Enforcement controls disabled for a non-admin, with the reason in text
**File:** `src/components/dashboard/NodeDetailPanel.jsx:130-159`; `src/components/pyramid/NodeInspector.jsx:285-295`; `src/pages/Settings.jsx:224-236`, `:462-479`; `src/components/layout/AppShell.jsx:27`, `:147`
**What is wrong:** The client used to throw the role away, leave the buttons enabled, and log the backend's 403 to the console, so an operator believed a block had happened. Now five controls are disabled for anyone who is not `admin`, each with a line of text saying an admin is required: Block Node, Unblock Node, Isolate / Deisolate Node (pyramid inspector), the threshold Save, and Reload Model. A refused request is shown in the panel.
**How to reproduce:** Sign in as the read-only user: `readonly` / `readonly-for-demo` unless `backend/.env` sets `READONLY_USERNAME` / `READONLY_PASSWORD` (`backend/app/config.py:68-69`). Click a host on Network Topology and check Block is greyed with the sentence under it. Open the pyramid inspector and check Isolate. Open Settings → Detection Thresholds and check the slider, Save and Reload Model.
**What done / what remains:** Done in `72601c1`, two unit tests. Not seen. Three gaps the fix did not reach: triage and Mark Resolved are not gated (FE-24); Simulate Attack is not gated by role (FE-24); and the old login form (the dead `LoginForm.jsx`) said "No per-user accounts or roles yet", which was no longer true; it was removed in the repo cleanup.

### BUG FE-08: Simulate Attack hidden on three pages and disabled on a live backend
**File:** `src/utils/connection.js:64-77`; `src/components/layout/Topbar.jsx:61-62`, `:227-256`; `src/pages/Settings.jsx:29`, `:192-205`
**What is wrong:** A simulation posts synthetic flows to the real backend, which records what follows as real incidents. So the button must not exist on the pages that show the historical record, and must be disabled against a live backend.
**How to reproduce:** With `VITE_USE_MOCK` unset and the badge on `LIVE`: the top-bar button must be absent on `/forensics`, `/blockchain` and `/timeline`, and present but greyed on the other pages. On Settings → Simulation the Simulate Attack button must be greyed with the reason printed under it.
**What done / what remains:** Done in `3cf55ab`. Not seen. Two things to check that are not in `OPEN_ITEMS.md`: in the top bar the reason is only a `title` tooltip on a disabled button (`Topbar.jsx:251`), which is not visible on a projector and which some browsers do not show on disabled buttons; and the "Enable Simulation" toggle on the same Settings tab is **not** gated at all (FE-22).

### BUG FE-09: The colour refactor should have changed nothing you can see
**File:** `src/constants/colors.js`; all 32 component files it replaced literals in
**What is wrong:** Nothing known. Every literal was replaced by a named value with the same hex, so no page should look different from before `ae34631`. One deliberate exception: a note colour in the pyramid's node inspector moved from `#6b7280` to `GS.textSubtle` (`#727a86`).
**How to reproduce:** Compare each page against a checkout of `3cf55ab` side by side, or against screenshots if you have them. Pay attention to the graphs (Cytoscape and three.js take colours as strings, so a wrong name fails silently to a default) and to anything drawn with an alpha suffix such as `${GS.danger}25`.
**What done / what remains:** Done in `ae34631`; three unit tests guard the module. Not seen.

### BUG FE-10: The first-load skeleton and the truncation banner
**File:** `src/components/shared/ShellNotices.jsx:49-59`; `src/components/layout/AppShell.jsx:46-49`, `:80`; `src/store/useGraphStore.js:155`
**What is wrong:** Three separate problems, all visible in the code. First, the skeleton is drawn by the shell, but the shell shows a full-page splash for a fixed 1.8 s before it renders anything (FE-17). The first poll starts at the same moment and normally returns well inside 1.8 s, so by the time the shell appears the skeleton's condition is already false. **You will probably never see the skeleton.** Second, the truncation banner appears only when a socket payload says `truncated`, which the server sets when the graph has more than 50 nodes or 100 links (`backend/app/websocket/events.py:12-13`, `:58`). The demo topology has 10 hosts and at most 90 host pairs, so **the banner cannot appear in the demo at all.** Third, if it ever did appear it would not stay dismissed: the REST poll's graph has no `truncated` field, so each poll sets `graphTruncated` to false and unmounts the banner, and the next socket push mounts a fresh one with its "dismissed" state reset. The graph itself would also alternate between the full REST graph and the truncated socket graph every few seconds.
**How to reproduce:** For the skeleton, throttle the network in dev tools to "Slow 3G" and reload. For the banner there is no honest way with this topology; temporarily lower `_MAX_BROADCAST_NODES` on a scratch backend, or call `useGraphStore.getState().setGraphData({ nodes: [], links: [], truncated: true })` from the console.
**What done / what remains:** Built in `3cf55ab`. Not seen. The dismiss state needs to live in the store, and the socket's truncated graph should not replace a fuller REST graph.

### BUG FE-11: Threat Feed filter pills (never reviewed)
**File:** `src/pages/ThreatFeed.jsx:16-18`, `:86-129`, `:241-255`
**What is wrong:** The type pills are `All, DDoS, SSHBrute, PortScan, Botnet`. The backend also produces `DoSHulk` and `Manual` (`backend/app/models/schemas.py:14`), so those alerts are reachable only under `All`, and the "Attack Types" bars on the right never count them. A manual block made during the demo will therefore appear in the list with no pill that selects it. The filter bar holds four groups of pills plus a search box in one wrapping row; how it wraps has not been looked at.
**How to reproduce:** Run the three demo attacks, block one host by hand, open `/threats`, and try each pill. Shrink the window and see how the bar wraps.
**What done / what remains:** Nothing was changed here in the recent passes. Add the two missing types or derive the pill list from the alerts present.

### BUG FE-12: The Forensics transaction-hash row (never reviewed)
**File:** `src/pages/Forensics.jsx:248-255`, `:285-297`
**What is wrong:** The detail card prints the whole 66-character hash on one line beside a label (`prefixLen` is set to the hash's full length), which may overflow the card at narrower widths. More important for the demo: the retry count and the "Last error" box are inside the branch that renders only when a hash exists. When Ganache is down the incident has no hash and status `retry`, which is exactly the case where the reason matters, and the card shows only "No transaction recorded". The reason is visible one panel up, as the last step of the derived timeline ("Blockchain retry scheduled" with the error), but not where an operator looks for it.
**How to reproduce:** Run one attack with Ganache stopped, open the incident on `/forensics`, and read the Blockchain Evidence card. Then repeat with Ganache running and check the hash fits.
**What done / what remains:** Not touched. Move the retry and last-error blocks outside the `blockchain_tx ?` branch.

### BUG FE-13: Audit & Ledger columns (never reviewed)
**File:** `src/pages/BlockchainLedger.jsx:14-15`, `:169`, `:230-241`, `:290`; `backend/app/api/v1/forensics.py:18-34`
**What is wrong:** The table reads fields the backend does not send. The expanded row prints "Forensics URI:" from `tx.forensics_uri`, but the backend's `_normalize_chain_record` drops that field, so the line is always blank. The same function hard-codes `status: "confirmed"` for every record, so the `pending` and `failed` status pills can never match anything and always show the empty table. The type pills have the same `DoSHulk` / `Manual` gap as FE-11. The eight-column table and the seven-column enforcement table have not been checked for width.
**How to reproduce:** With Ganache running and at least one incident on chain, open `/blockchain`, click a row to expand it, and click each pill.
**What done / what remains:** Not touched. The URI and the real status need a backend change (it is in BACKEND.md as BE-13); until then remove the URI line and the two dead pills, or leave them and say so.

### Open item 14: decisions that were not made

### BUG FE-14: Simulate Attack cannot be used against a live backend
**File:** `src/utils/connection.js:74-77`
**What is wrong:** By instruction, the button is disabled whenever the build is not a mock build and the backend is live. The consequence is that with `VITE_USE_MOCK` unset there is no way to produce an incident from the dashboard; it takes Mininet traffic. And the mock build is not a working alternative (FE-21).
**How to reproduce:** See FE-08.
**What done / what remains:** Working as instructed. **Decision needed:** does the presentation depend on the button? If it does, the rule has to be revisited, for example by allowing it for an admin with a confirmation that names what will be written. If it does not, the demo uses `mininet/demo/run_demo.py` and the button can stay disabled.

### BUG FE-15: The landing page states figures the project does not claim
**File:** `src/pages/LandingPage.jsx:30`, `:38`, `:56-57`, `:63-64`, `:95`
**What is wrong:** The page says "97.7% detection accuracy", "GNN Accuracy 97.7%", ">92% accuracy and <200ms inference latency", "F1 >= 0.88", isolation "in under 500ms", and that the model "Detects DDoS, PortScan, Botnet, SSH Brute Force, DoS Hulk". `MODEL_BEHAVIOUR.md` §10 says latency has never been measured, that no accuracy figure describes the running system, and that neither model detects Botnet. The figures guard does not scan `.jsx`, so nothing fails.
**How to reproduce:** Open `/` signed out.
**What done / what remains:** Left as written; it is the authors' copy. **Decision needed:** remove the figures, replace them with the scoped offline ones, or keep the page out of the presentation. If it is shown, the wording in section 7 applies.

### BUG FE-16: Two palettes
**File:** `src/constants/colors.js:33-40`; `frontend/tailwind.config.js:20-33`, `:58-63`
**What is wrong:** See section 5. Inline-styled pages use one red, grey and green; class-styled components (`NodeDetailPanel`, `BlockchainStatusBadge`, the landing page) use another. The reds differ by a few shades, the greys more.
**How to reproduce:** Put a `NodeDetailPanel` Block button next to an Alert Centre status chip.
**What done / what remains:** Both are named in one module. **Decision needed:** which palette wins. It is a visual change, so make it with the app in front of you.

### BUG FE-17: A fixed 1.8 s splash on every entry to the app
**File:** `src/components/layout/AppShell.jsx:23`, `:46-49`, `:80`
**What is wrong:** The shell shows a full-page loading screen for 1.8 s regardless of whether anything is loading, then mounts. It runs again every time the shell remounts (after login, after a hard refresh). It also hides the skeleton (FE-10).
**How to reproduce:** Reload any protected page.
**What done / what remains:** Left as it was. **Decision needed:** keep it as branding, or tie it to `initialLoadDone` so it ends when the first poll returns.

### BUG FE-18: The topology scaffold draws nodes the backend does not report
**File:** `src/utils/topologyScaffold.js:23-100`; `src/pages/NetworkTopology.jsx:29`
**What is wrong:** `/api/v1/graph` returns hosts and observed traffic links only. The scaffold adds a controller `c0`, a switch `s1` and a star of links, all marked `source: 'configured'`, so an idle network is not ten unconnected dots. It adds no hosts and draws nothing when the backend returns none. The switch turns "suspicious" when any host is malicious, which is a status the backend never assigned.
**How to reproduce:** Open `/network` with no traffic running.
**What done / what remains:** Kept. **Decision needed:** whether configured infrastructure counts as "data not from the API". If it stays, say during the demo that the switch and controller are drawn from configuration.

### BUG FE-19: The skeleton is one strip, not shaped like the panels
**File:** `src/components/shared/ShellNotices.jsx:12-25`
**What is wrong:** The first-load skeleton is three grey bars from the shell, the same on every page. Pages still render their own empty states underneath ("No threats detected. Network secure.") during the first load, which reads as a result.
**How to reproduce:** As FE-10.
**What done / what remains:** One strip was built. **Decision needed:** whether per-panel skeletons are worth building, given FE-10 shows the current one is almost never visible.

### BUG FE-20: Hand-written spacing utilities in `globals.css`
**File:** `src/styles/globals.css:49-118`
**What is wrong:** A block of hand-written utilities (`mt-1`, `p-2`, `gap-4`, …) sits under a comment saying it works around a Tailwind 4 regression. `OPEN_ITEMS.md` counts eighteen as unused by name; the block is longer than that. They were kept because they are utility names and may be the only reason those classes work in this setup.
**How to reproduce:** Delete the block on a scratch branch, rebuild, and compare the landing page and login page, which use these classes most.
**What done / what remains:** Kept. **Decision needed:** test whether the regression still exists with the installed Tailwind; if not, delete the block.

### Found while reading

### BUG FE-21: `VITE_USE_MOCK=true` blanks the dashboard every 10 s and fights the socket
**File:** `src/hooks/useGraphData.js:41-44`; `src/store/useGraphStore.js:114-121`; `src/providers/SimulationProvider.jsx:29-33`
**What is wrong:** In a mock build every poll tick calls `setConnectionMode('mock')` and returns, and that setter resets the graph, alerts, blocked list, chain records, timeline and stats to empty. The check comes **before** the "do not disturb a simulation" check. So when you click Simulate Attack, the results are fetched and shown, and the next tick, at most 10 s later, wipes them and cuts the simulation state short. If a real backend is also running, its socket still connects, and each `graph_update` push sets the mode back to `'live'`, so the badge and the graph flip between live data and blank every few seconds. The mock build is the only build in which the Simulate button is enabled, so this is the path FE-14 points people to.
**How to reproduce:** Set `VITE_USE_MOCK=true` in `frontend/.env`, restart `npm run dev`, sign in against a running backend, click Simulate Attack, and watch for 15 s.
**What done / what remains:** Not known before this reading. Open.

### BUG FE-22: The "Enable Simulation" toggle bypasses the gate and freezes the dashboard
**File:** `src/pages/Settings.jsx:77-83`, `:139`
**What is wrong:** The toggle at the top of Settings → Simulation calls `setConnectionMode('simulating')` directly. It is not disabled on a live backend, and it sends no attack. While the mode is `'simulating'`, polling skips every tick (`useGraphData.js:47`) and the socket handlers drop graph and alert pushes, so the whole dashboard freezes with a `SIMULATION` badge until someone switches the toggle off. Nothing ends it automatically.
**How to reproduce:** On a live backend open Settings → Simulation, click the toggle, go to the dashboard, and run a real attack. Nothing appears.
**What done / what remains:** Missed by the gate added in `3cf55ab`. Either remove the toggle or give it the same `simulateBlocked` rule as the button below it.

### BUG FE-23: The screen says a model classified the attack type, and other claims
**File:** `src/pages/Forensics.jsx:526-531`; `src/pages/NetworkTopology.jsx:186-188`; `src/pages/SelfHealing.jsx:16-21`, `:62-64`; `src/pages/LoginPage.jsx:9-20`
**What is wrong:** The incident timeline on Forensics has a step titled "GraphSAGE classified" with the text "`<attack type>` classified (threat score: N%)". The attack type is not GraphSAGE's output; it is a port and volume heuristic (section 7). For a manual block the step reads "GraphSAGE classified — Manual classified (threat score: 0%)". This contradicts, on screen, the one sentence the presenter is told to say first. Three smaller ones: the pyramid panel is headed "Org Hierarchy · Lateral Movement Detection" while Settings says lateral-movement detection does not exist; Self-Healing shows "Avg Response Time" in milliseconds, which in simulated mode is the duration of a log call (1 ms) and will be read as a measured latency; and the login page's terminal prints "system status: OPERATIONAL", "threat level: ELEVATED" and "backend: localhost:8000" as fixed text.
**How to reproduce:** Open any incident on `/forensics`; open `/network`; open `/healing` after one block; open `/login`.
**What done / what remains:** Open. The first is the one to change before the presentation: "Scored by GraphSAGE (N%) · labelled `<type>` by heuristic".

### BUG FE-24: Failed triage is silent, and Alert Centre's local status can override the server for ever
**File:** `src/pages/AlertCentre.jsx:72`, `:85`; `src/hooks/useAlerts.js:79-88`; `src/utils/alertStatus.js`; `src/pages/Forensics.jsx:34-39`; `src/store/useGraphStore.js:324-326`
**What is wrong:** Alert Centre writes the new status to `localStorage` before the PATCH and removes it only when the PATCH succeeds. On any failure the catch is empty, the local entry stays, and `useAlerts` lets a local entry win over the server. Nothing ever retries or clears it. The backend refuses triage from a `readonly` session with 403, so a read-only user who clicks a status sees it change and stay changed on their device while the server still says `open`. That is the B19 problem again, in the other of the two local stores (B19's fix covered `resolvedIncidentIds`, not `gs_alert_statuses`). Healing notices have no incident id, so their status is local-only by design, under a page header that says the state "is saved on the server". Related: Forensics' Mark Resolved swallows a 403 the same way (the incident disappears and returns after the next refresh, with no message), and Simulate Attack has no role check, so a read-only user in a mock build gets 8 s of `SIMULATION` and a console error.
**How to reproduce:** Sign in as `readonly`, cycle an alert's status in Alert Centre, reload the page. The changed status is still there. Sign in as admin in another browser: it says `open`.
**What done / what remains:** Open. Gate triage on role the way B20 gated enforcement, show the refusal, and drop the local entry on a 4xx.

### BUG FE-25: Labels that do not match what the number is
**File:** `src/pages/DashboardPage.jsx:84-85`; `src/pages/SelfHealing.jsx:22`, `:56`; `src/pages/BlockchainLedger.jsx:35`, `:147`; `src/pages/Settings.jsx:314-317`; `src/pages/AlertCentre.jsx:90-94`, `:97`, `:266`, `:291`; `src/pages/ThreatFeed.jsx:170-175`
**What is wrong:** Each of these is a label over a number that means something else. "Threats (24h)" on the dashboard is `stats.active_threats`, the count of hosts that are malicious or suspicious right now. "Total Isolations Today" is every healing event in the store, whatever its date. "Gas Used Today" is the sum over every chain record ever. "Gas Limit (fixed) 1,000,000" in Settings is a constant in the JSX; the backend estimates gas per call under a cap of 600,000 (`backend/app/config.py:51`). The Alert Centre donut is titled "Open by Severity" and its slices are named Critical, Warning and Resolved, but the values are the counts of open, acknowledged and resolved alerts. Its sparkline is titled "Alerts / Hour (last 6h)" and plots the last twelve five-minute buckets of a 60-minute window. Threat Feed prints "✓ on-chain" whenever a hash exists, including when the transaction is still pending or failed.
**How to reproduce:** Read each label beside its source line.
**What done / what remains:** Open. These are text changes. An examiner who asks "what is this number" will find them.

### BUG FE-26: The Timeline page's range pills do nothing
**File:** `src/pages/TimelineAnalytics.jsx:14`, `:19`, `:91-105`; `src/services/api.js:81-82`
**What is wrong:** The `1h / 6h / 24h / 7d` pills set a `timeRange` state that nothing reads. The chart always shows the store's timeline, which is always fetched with `last=60min`. The page opens with `24h` highlighted over 60 minutes of data. The stacked bar chart below it also has no colour for `DoSHulk` or `Manual`, so those incidents are not drawn.
**How to reproduce:** Click each pill; the chart does not change.
**What done / what remains:** Open. Either pass the range to `getTimeline` (the backend accepts up to `1440min`, `backend/app/services/timeline_service.py:45-51`; it has no 7-day window) or remove the pills.

### BUG FE-27: "Connected" on Audit & Ledger is not about the blockchain
**File:** `src/pages/BlockchainLedger.jsx:25`, `:109-120`; `src/hooks/useGraphData.js:29`
**What is wrong:** Beside "Ganache · Chain N" the page shows a green dot and "Connected". The dot is `connectionMode === 'live'`, which is whether the backend's REST API answers. It says nothing about Ganache. The frontend never stores `blockchain.connected` from `/health`. With Ganache down and the backend up, the page reads "Ganache · Chain — · Connected".
**How to reproduce:** Start the backend without Ganache and open `/blockchain`.
**What done / what remains:** Open. Store `health.blockchain` in the poll and drive the dot from it. Until then, the only on-screen hint that the chain is down is the dash in place of the chain id. Skanda needs to know this for his checklist.

### BUG FE-28: A typo puts a CSS property inside a font name
**File:** `src/pages/AlertCentre.jsx:190`
**What is wrong:** The style reads `fontFamily: "'DM Mono', monospace', cursor: 'pointer'"`. A quote is in the wrong place, so the browser gets an invalid `font-family` and ignores it, and the intended `cursor: pointer` is never set. The alert's IP renders in the inherited font, not the mono font the rest of the row uses.
**How to reproduce:** Inspect the IP span in any Alert Centre row.
**What done / what remains:** Open. One-line fix: `fontFamily: "'DM Mono', monospace", cursor: 'pointer'`.

### BUG FE-29: "DEMO MODE — SYNTHETIC TRAFFIC ALLOWED" shows before the backend has said anything
**File:** `src/store/useGraphStore.js:24`, `:55`; `src/components/ui/DemoModeBadge.jsx:9-10`
**What is wrong:** The store's initial `stats` and its reset state both set `demo_fallback_flows: true`. The badge shows whenever that field is true. So the badge is up during the first load and in the `OFFLINE` state, even though the backend's own default is false and on the demo path it will be false. On the first second of the demo the header carries a warning that is not true, and the longest badge in the row.
**How to reproduce:** Reload the dashboard and watch the header before the first poll returns; or open it with the backend stopped.
**What done / what remains:** Open. Default it to `false`, or to `null` and render nothing until the backend has answered.

### BUG FE-30: The sidebar's unread count still treats "blocked" as "handled"
**File:** `src/components/layout/Sidebar.jsx:30-36`
**What is wrong:** The Alert Centre badge in the sidebar skips every alert whose `is_blocked` is true. B17 established that blocking is not triage. v1 blocks every source it raises an incident for, so in the demo every alert is blocked and the sidebar badge stays empty while Alert Centre itself says "Open: 3". The same lines look up the local status under the keys `alert-<id>` and `<id>`, but Alert Centre stores it under `threat-<id>`, so an optimistic acknowledge never reaches the count either.
**How to reproduce:** Run the three demo attacks and compare the sidebar badge with the Open tile in Alert Centre.
**What done / what remains:** Missed by `72601c1`. Remove the `is_blocked` line and take the status from `useAlerts`.

---

## 7. How the two models appear in the frontend

The backend runs two models on every poll. They are not combined. Here is what
each puts on screen.

**v1 (GraphSAGE, two classes) produces everything you can click.**

- Its score per host is `threat_score` on graph nodes and alerts, and
  `threat_score` on incidents. It drives node colour and status (`normal`,
  `suspicious`, `malicious`, `blocked`), the severity label, and the stat cards.
- All three socket events are v1's: `graph_update`, `alert`,
  `healing_triggered`.
- Every incident, block, healing event, enforcement-log row and chain record on
  Dashboard, Network Topology, Threat Feed, Forensics, Audit & Ledger, Timeline,
  Self-Healing and Alert Centre comes from v1 crossing its threshold.
- Its health is the `HEURISTIC SCORING` badge, shown only when v1's weights
  failed to load and a hand-written formula is scoring instead
  (`MlModeBadge.jsx`). If you see that badge, the scores on screen are not from
  a model at all.

**v2 (GATv2, five classes) produces one badge.** The header reads
`BLOCKS: v1 MODEL · v2: <state>` (`DetectionPathBadge.jsx:13-20`):

| State | Meaning |
|---|---|
| `v2: DRY-RUN` | v2 is enabled and its inference service answers. It proposes rules that are logged and discarded. |
| `v2: OFF` | The backend was started without `GS2_ENABLED=true`. |
| `v2: NO ANSWER` | v2 is enabled but its service is not reachable: it is producing no scores. |
| `v2: UNKNOWN` | `/health` has not answered yet. |

Nothing else from v2 reaches the UI: no class, no confidence, no rule, no
incident. Settings does not show it either (the backend sends
`ml_binary_gate`, and the page ignores it).

**The attack-type label is not a model output.** `DDoS`, `PortScan`, `SSHBrute`,
`DoSHulk` and `Botnet` are assigned by `infer_attack_type` in
`backend/app/services/threat_analyzer.py:35-74`, a set of port and packet-count
rules: port 22 with more than 250 packets is `SSHBrute`; five or more
destination ports is `PortScan`; more than 1 MB to ports 80, 443 or 8080 is
`DoSHulk`; more than 5000 packets or a score of 0.90 or more is `DDoS`;
**anything else is `Botnet`**. v1 only says "malicious" or not. The frontend
shows this label on nodes, alerts, incidents, healing events and chain records
with no marking that it is a heuristic, and on Forensics it is attributed to
GraphSAGE outright (FE-23).

---

## 8. Demo checklist

Before the presentation, on the presentation machine.

**Bring the stack up** (`mininet/demo/DEMO_SETUP.md`, "Before you start"):

1. As root in WSL: `sync; echo 3 > /proc/sys/vm/drop_caches`
2. `sudo service openvswitch-switch start` and
   `sudo systemctl stop openvswitch-testcontroller`
3. `sudo python3 mininet/topologies/base_topology_headless.py` (leave the
   terminal open)
4. As root in WSL:
   `DAEMON_TOKEN=<the backend's> python3 backend/scripts/enforcement_daemon.py`
5. Start the inference service, then the backend, with
   `ENFORCEMENT_MODE=simulated` (commands in `RUN_GUIDE.md` §5; the backend is
   on port 8001)
6. `python ML/verify_stack.py`: all ten checks must pass
7. `cd frontend`, `npm run dev`, open `http://localhost:5173`, sign in as admin.
   The header must say `LIVE`. If it says `OFFLINE`, check
   `VITE_BACKEND_URL=http://localhost:8001` is in `frontend/.env`.

**Trigger incidents** from the repository root:

```
python mininet/demo/run_demo.py --backend-url http://localhost:8001
```

or one at a time, in WSL:

```
sudo python3 mininet/demo/attacks/flood.py
sudo python3 mininet/demo/attacks/portscan.py
sudo python3 mininet/demo/attacks/bruteforce.py
```

Allow about twenty seconds after each before looking at the dashboard. Do not
run benign traffic alongside, and do not use the Simulate button.

**Then check, in this order:**

- [ ] Every item FE-01 to FE-13 in section 6, ticking each off in the browser.
- [ ] The header badges fit on one line at the projector's resolution, in all
      four v2 states, without wrapping and without any badge scrolled out of
      view (FE-01). Check the first second after load too (FE-29).
- [ ] Stop the backend. The badge leaves `LIVE`, the panels keep their data,
      and the stale badge is readable with its reason (FE-02, FE-03). Expect to
      be sent to the login page when the backend comes back.
- [ ] Sign out, sign in as `readonly` / `readonly-for-demo`. Block, Unblock,
      Isolate, the threshold Save and Reload Model are greyed with the sentence
      "An admin is required…" in text (FE-07). Then click an alert's status as
      this user and see what happens (FE-24).
- [ ] Open one incident on Forensics and read the timeline step that names
      GraphSAGE (FE-23). Decide whether to change it or to say it aloud.
- [ ] Do not open Settings → Simulation and touch the toggle during the demo
      (FE-22).
- [ ] If the landing page will be on screen at any point, read FE-15 first.

What to say about the labels is in `DEMO_SETUP.md` under "What to say about the
labels". The first line of it: the model that acts is binary, and the attack
type on the dashboard is a port and volume heuristic, not a model output. Say it
before the first label appears.
