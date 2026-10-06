// [Windows] GraphSentinel — Susheep
// Graph store — Zustand global state for dashboard
// § 4.5 Fix: connectionMode state machine replaces isMockMode + isSimulating booleans
// MOCK data is untangled from initial state.
import { create } from 'zustand'
import { loadResolvedIncidentIds, saveResolvedIncidentIds } from '../utils/alertStatus'
import { mergeGraph } from '../utils/graphMerge'
import { mergeRun } from '../utils/simulation'
import { overlayAfterFetch } from '../utils/triage'

// connectionMode values:
//   'connecting'  — app just started, trying to reach backend
//   'live'        — WebSocket/REST returning real data from backend
//   'mock'        — backend unreachable; UI shows an explicit empty/offline state (never fabricated data)
//   'simulating'  — a real attack burst was sent to POST /api/v1/analyze and results are loading

const EMPTY_STATE = {
  // demo_fallback_flows is null until /api/v1/stats says otherwise: the demo
  // badge must not claim synthetic traffic is allowed before the backend has
  // answered (it used to default to true, so it showed on every first load).
  graphData: { nodes: [], links: [] },
  alerts: [],
  blockedIPs: [],
  chainTxs: [],
  timeline: [],
  enforcementActions: [],
  lastDataAt: null,
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: null },
  dataErrors: { graph: null, alerts: null, blocked: null, forensics: null, stats: null, timeline: null, health: null, enforcement: null, healing: null },
}

// The pending "clear the healing highlight" timer (audit B34). Module scope: a
// timer id is not state anything renders from.
let healingTimer = null

const useGraphStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────
  graphData: { nodes: [], links: [] },
  alerts: [],
  blockedIPs: [],
  chainTxs: [],
  chainId: null, // Error.md #17 — real chain ID from the connected Web3 provider, not hardcoded
  // Error.md #4 — the API already returned ml.mode/degraded_reason via
  // /health, but nothing in the frontend fetched or displayed it, so an
  // operator couldn't tell real GraphSAGE scores from the heuristic fallback.
  mlHealth: { mode: 'model', degraded_reason: null },
  setMlHealth: (health) => set({ mlHealth: health }),
  // /health's ml_v2: whether the v2 path runs at all. null until /health answers.
  mlV2Health: null,
  setMlV2Health: (health) => set({ mlV2Health: health ?? null }),
  // /health's blockchain block ({ connected, error, contract_address }): whether
  // the BACKEND can reach Ganache. null until /health answers (FE-27).
  chainHealth: null,
  setChainHealth: (health) => set({ chainHealth: health ?? null }),
  healingEvents: [],
  healingNodeId: null,
  timeline: [],
  enforcementActions: [],
  // Error.md U4 — wall-clock of the last time real data landed (REST poll or
  // WebSocket push), so the UI can show "updated Ns ago" separately from the
  // connection badge.
  lastDataAt: null,
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: null },
  nodeOverrides: {},
  // Error.md H7 — persisted so incidents marked resolved in Forensics stay
  // resolved across a refresh (still per-device until there's a backend).
  resolvedIncidentIds: loadResolvedIncidentIds(),
  // Audit B19 — ids whose PATCH has not come back yet. Not persisted.
  resolveInFlight: [],

  // Per-resource freshness (Error.md #22/#26): Promise.allSettled in
  // useGraphData.js updates each panel's data independently, so a panel can
  // silently go stale if only its own fetch keeps failing while others
  // succeed. This lets the UI show that panel is stale instead of pretending
  // null (last fetch OK) or an error message string.
  dataErrors: { graph: null, alerts: null, blocked: null, forensics: null, stats: null, timeline: null, health: null, enforcement: null, healing: null },
  setDataError: (resource, error) =>
    set((state) => ({ dataErrors: { ...state.dataErrors, [resource]: error } })),

  // ── Connection state machine ───────────────────────────────
  // 'connecting' | 'live' | 'offline' | 'mock' | 'simulating'
  //   mock    — the backend was never reached: panels are blanked, never faked
  //   offline — it was answering and has stopped (audit B21): the last data
  //             stays on screen, marked stale per panel by dataErrors
  // The mode follows whether REST polls are ANSWERED (useGraphData), not
  // whether the socket once connected.
  connectionMode: 'connecting',
  // What the socket is doing, separately: 'idle' | 'connected' | 'reconnecting' | 'lost'
  socketStatus: 'idle',
  // False until the first poll of the nine resources has come back, whatever
  // it brought: the pages show a skeleton until then, not an empty state that
  // would read as "nothing happened".
  initialLoadDone: false,
  setInitialLoadDone: () => set({ initialLoadDone: true }),
  // The server caps what it broadcasts and says when it did (`truncated` on the
  // graph_update payload). Kept so the graph pages can say so too.
  graphTruncated: false,
  // The operator dismissed the truncation banner; kept here, not in the
  // banner, so it survives the banner unmounting and remounting.
  graphTruncatedDismissed: false,
  dismissGraphTruncated: () => set({ graphTruncatedDismissed: true }),
  setSocketStatus: (socketStatus) => set({ socketStatus }),
  // The mode a simulation interrupted, restored when it ends.
  modeBeforeSimulation: null,

  // ── UI state ──────────────────────────────────────────────
  use3D: true,
  selectedNode: null,
  forensicsOpen: false,
  isConnected: false,

  // ── Derived booleans — backward-compat aliases ─────────────
  // Components that consumed isMockMode / isSimulating still work
  get isMockMode() {
    const mode = get().connectionMode
    return mode === 'mock' || mode === 'connecting'
  },
  get isSimulating() {
    return get().connectionMode === 'simulating'
  },

  // ── Connection mode setter ─────────────────────────────────
  // 'mock' means the backend is unreachable — show an explicit empty/offline
  // state (ConnectionModeBadge already renders this as "OFFLINE"), never
  // fabricated numbers. See Error.md #1.
  setConnectionMode: (mode) => {
    const current = get().connectionMode
    if (mode === 'simulating' && current !== 'simulating') set({ modeBeforeSimulation: current })
    set({ connectionMode: mode })
    // Blank the panels on ENTERING 'mock' only. It used to run on every call,
    // and a mock build calls this on every poll tick, so whatever was on screen
    // (a simulation's results included) was wiped every 10 s (FE-21).
    if (mode === 'mock' && current !== 'mock') {
      set(EMPTY_STATE)
    }
  },

  // Legacy setters — kept for backward compat, mapped to connectionMode
  setMockMode: (isMock) =>
    get().setConnectionMode(isMock ? 'mock' : get().connectionMode === 'mock' ? 'live' : get().connectionMode),
  
  setSimulating: (isSimulating) =>
    isSimulating ? get().setConnectionMode('simulating') : get().endSimulation(),

  // Leave the simulating state for the mode it interrupted. It used to guess
  // from the socket ('live' if connected, else 'mock'), which blanked every
  // panel after a simulation run with the socket down and REST answering.
  endSimulation: () => {
    if (get().connectionMode !== 'simulating') return
    const before = get().modeBeforeSimulation
    set({ connectionMode: before && before !== 'simulating' ? before : 'connecting', modeBeforeSimulation: null })
  },

  // ── Data setters ──────────────────────────────────────────
  setGraphData: (newData) =>
    set((state) => {
      // FE-10 — a full graph replaces the one on screen; a socket push the
      // server capped (truncated: true) is merged into it, so the newest scores
      // show at once and nothing the cap left out disappears (utils/graphMerge).
      // Node objects are kept so react-force-graph keeps their coordinates.
      return {
        graphData: mergeGraph(state.graphData, newData),
        // Only a payload that says so changes the flag: the REST graph has no
        // `truncated` field, and resetting it on every poll made the banner
        // vanish and come back (with its dismissal forgotten) every 10 s.
        graphTruncated: newData.truncated === undefined ? state.graphTruncated : Boolean(newData.truncated),
        lastDataAt: Date.now(),
      }
    }),

  // Audit B34 — a socket alert whose id is already in the list (the REST poll
  // delivered it first, or the server re-emitted it) is not inserted again.
  addAlert: (alert) =>
    set((state) => {
      if (alert?.id != null && state.alerts.some((a) => a.id === alert.id)) return {}
      return { alerts: [alert, ...state.alerts].slice(0, 50) }
    }),

  // Audit B18 — after a triage PATCH succeeds, the alert in the store takes the
  // new status at once. Without this the row fell back to the server's OLD
  // status when the optimistic entry was cleared, until the next poll.
  applyAlertStatus: (rawAlertId, status, acknowledgedAt) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.id === rawAlertId
          ? { ...a, alert_status: status, acknowledged_at: acknowledgedAt ?? a.acknowledged_at ?? null }
          : a),
    })),

  // Audit B34 — one highlight timer. A second healing event used to leave the
  // first event's timer running, so it cleared the second highlight early.
  setHealingNode: (ip) => {
    clearTimeout(healingTimer)
    healingTimer = null
    set({ healingNodeId: ip })
    if (ip) {
      healingTimer = setTimeout(() => {
        healingTimer = null
        set({ healingNodeId: null })
      }, 3500)
    }
  },

  addHealingEvent: (event) =>
    set((state) => ({
      healingEvents: [event, ...state.healingEvents].slice(0, 10),
    })),

  addTimelinePoint: (point) =>
    set((state) => ({
      timeline: [...state.timeline, point].slice(-20),
    })),

  updateStats: (partial) =>
    set((state) => ({
      stats: {
        ...state.stats,
        ...partial,
        // § 4.6 Defensive: always clamp system_health to 0–100
        system_health:
          partial.system_health !== undefined
            ? Math.max(0, Math.min(100, partial.system_health))
            : state.stats.system_health,
      },
    })),

  updateNodeStatus: (nodeId, status) =>
    set((state) => ({
      graphData: {
        ...state.graphData,
        nodes: state.graphData.nodes.map((n) =>
          n.id === nodeId || n.ip === nodeId ? { ...n, status } : n
        ),
      },
      selectedNode:
        state.selectedNode && (state.selectedNode.id === nodeId || state.selectedNode.ip === nodeId)
          ? { ...state.selectedNode, status }
          : state.selectedNode,
      nodeOverrides: {
        ...state.nodeOverrides,
        [nodeId]: status,
      }
    })),

  // The run started with the Simulate button (pages/AttackSimulation): the
  // real scripts in mininet/demo/attacks on the live topology, followed over
  // the socket (`simulation_update`) and GET /api/v1/simulations. Nothing here
  // builds a flow: what the run produces arrives the usual way, from the switch.
  simulationRun: null,
  setSimulationRun: (run) => set((state) => ({ simulationRun: mergeRun(state.simulationRun, run) })),

  resolveIncident: (incidentId) =>
    set((state) => {
      const next = state.resolvedIncidentIds.includes(incidentId)
        ? state.resolvedIncidentIds
        : [...state.resolvedIncidentIds, incidentId]
      saveResolvedIncidentIds(next)
      const inFlight = state.resolveInFlight.includes(incidentId)
        ? state.resolveInFlight
        : [...state.resolveInFlight, incidentId]
      return { resolvedIncidentIds: next, resolveInFlight: inFlight }
    }),
  // The PATCH for this incident came back, either way.
  settleResolve: (incidentId) =>
    set((state) => ({ resolveInFlight: state.resolveInFlight.filter((id) => id !== incidentId) })),
  // Audit B19 — the server wins. Called after every successful fetch of
  // incidents or alerts: the server's status is now known, so the local
  // overlay keeps only what is still in flight. It used to be permanent, and
  // hid an incident the server had reopened.
  reconcileResolvedWithServer: () =>
    set((state) => {
      const next = overlayAfterFetch(state.resolvedIncidentIds, state.resolveInFlight)
      if (next.length === state.resolvedIncidentIds.length) return {}
      saveResolvedIncidentIds(next)
      return { resolvedIncidentIds: next }
    }),

  // ── UI setters ────────────────────────────────────────────
  toggleView: () => set((state) => ({ use3D: !state.use3D })),
  setSelectedNode: (node) => set({ selectedNode: node }),
  // Audit B21 — the socket connecting or dropping no longer sets the mode. A
  // handshake said "live" while REST was failing, and a drop said "mock" and
  // blanked the panels while REST was answering. The caller re-polls instead.
  setConnected: (connected) =>
    set({ isConnected: connected, socketStatus: connected ? 'connected' : 'reconnecting' }),
  setForensicsOpen: (open) => set({ forensicsOpen: open }),

  setAlerts: (alerts) => set({ alerts }),
  setBlockedIPs: (ips) => set({ blockedIPs: ips }),
  setChainTxs: (txs) => set({ chainTxs: txs }),
  setChainId: (id) => set({ chainId: id }),
  setTimeline: (data) => set({ timeline: data }),
  setEnforcementActions: (actions) => set({ enforcementActions: actions }),
  setHealingEvents: (events) => set({ healingEvents: events }),
}))

export default useGraphStore
