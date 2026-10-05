// [Windows] GraphSentinel — Susheep
// Graph store — Zustand global state for dashboard
// § 4.5 Fix: connectionMode state machine replaces isMockMode + isSimulating booleans
// MOCK data is untangled from initial state.
import { create } from 'zustand'
import { analyzeFlows, getGraph, getAlerts, getBlocked, getForensics, getStats, getTimeline, getHealingEvents } from '../services/api'
import { loadResolvedIncidentIds, saveResolvedIncidentIds } from '../utils/alertStatus'
import { overlayAfterFetch } from '../utils/triage'

// connectionMode values:
//   'connecting'  — app just started, trying to reach backend
//   'live'        — WebSocket/REST returning real data from backend
//   'mock'        — backend unreachable; UI shows an explicit empty/offline state (never fabricated data)
//   'simulating'  — a real attack burst was sent to POST /api/v1/analyze and results are loading

const EMPTY_STATE = {
  graphData: { nodes: [], links: [] },
  alerts: [],
  blockedIPs: [],
  chainTxs: [],
  timeline: [],
  enforcementActions: [],
  lastDataAt: null,
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: true },
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
  healingEvents: [],
  healingNodeId: null,
  timeline: [],
  enforcementActions: [],
  // Error.md U4 — wall-clock of the last time real data landed (REST poll or
  // WebSocket push), so the UI can show "updated Ns ago" separately from the
  // connection badge.
  lastDataAt: null,
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: true },
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
    if (mode === 'mock') {
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
      // Preserve node object references so react-force-graph-3d doesn't lose
      // their x, y, z physics coordinates on every 10s polling tick.
      const existingNodes = new Map(state.graphData.nodes.map(n => [n.id, n]))
      const mergedNodes = newData.nodes.map(newNode => {
        const existing = existingNodes.get(newNode.id)
        if (existing) {
          // Update properties in place, preserving physics coords & object ref
          return Object.assign(existing, newNode)
        }
        return newNode
      })
      return {
        graphData: { nodes: mergedNodes, links: newData.links },
        graphTruncated: Boolean(newData.truncated),
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

  // Sends a real DDoS-shaped flow burst through the actual backend pipeline
  // (POST /api/v1/analyze — the same code path real OVS flows go through:
  // real GNN scoring, real incident creation, real self-healing/blocking,
  // real blockchain write). No fabricated hashes or optimistic local state —
  // see Error.md #3. `targetIp` is the attacker source; `victimIp` is who
  // it's attacking.
  simulateAttack: async ({ attackType, targetIp, victimIp, speedMultiplier = 1 } = {}) => {
    // Randomize defaults so each Simulate click hits different hosts/attacks
    const allHosts = Array.from({ length: 10 }, (_, i) => `10.0.0.${i + 1}`)
    const attackTypes = ['DDoS', 'PortScan', 'SSHBrute', 'Botnet']
    if (!attackType) attackType = attackTypes[Math.floor(Math.random() * attackTypes.length)]
    if (!targetIp) targetIp = allHosts[Math.floor(Math.random() * allHosts.length)]
    if (!victimIp) {
      const others = allHosts.filter((h) => h !== targetIp)
      victimIp = others[Math.floor(Math.random() * others.length)]
    }
    // Error.md H2/H3 — the Settings "Simulation Speed" (1x/5x/10x) is now a
    // real intensity multiplier on the synthetic flow volume, not dead state.
    const mult = Math.max(1, Number(speedMultiplier) || 1)
    const state = get()
    if (state.connectionMode === 'simulating') return

    state.setConnectionMode('simulating')

    const attackFlows = {
      // SYN flood: huge packet count, small packets, NON-HTTP ports. The old
      // template hit ports 80/443 with ~9 MB, which the backend's
      // infer_attack_type() correctly reads as an HTTP flood (DoSHulk, since
      // `http_bytes > 1_000_000` is checked before the DDoS rule) — so every
      // "DDoS" simulation came back labelled DoSHulk. High-numbered ports keep
      // http_bytes at 0, so `total_packets > 5000` classifies it as DDoS.
      DDoS: [
        { src_ip: targetIp, dst_ip: victimIp, src_port: 54321, dst_port: 8443, protocol: 'TCP', packet_count: 20000, byte_count: 1200000, duration_sec: 3.0, tcp_flags: 2 },
        { src_ip: targetIp, dst_ip: victimIp, src_port: 54322, dst_port: 9090, protocol: 'TCP', packet_count: 16000, byte_count: 960000, duration_sec: 3.0, tcp_flags: 2 },
      ],
      PortScan: Array.from({ length: 12 }, (_, i) => ({
        src_ip: targetIp, dst_ip: victimIp, src_port: 40000 + i, dst_port: 20 + i * 5,
        protocol: 'TCP', packet_count: 3, byte_count: 180, duration_sec: 0.05, tcp_flags: 2,
      })),
      SSHBrute: Array.from({ length: 8 }, (_, i) => ({
        src_ip: targetIp, dst_ip: victimIp, src_port: 50000 + i, dst_port: 22,
        protocol: 'TCP', packet_count: 40, byte_count: 6400, duration_sec: 1.2, tcp_flags: 2,
      })),
      Botnet: [
        { src_ip: targetIp, dst_ip: victimIp, src_port: 51234, dst_port: 6667, protocol: 'TCP', packet_count: 500, byte_count: 64000, duration_sec: 8.0, tcp_flags: 2 },
      ],
    }
    // Error.md #34 — tag every synthetic flow as simulation-sourced so it's
    // distinguishable from real OVS traffic everywhere downstream (graph
    // nodes, incidents, alerts, forensics) instead of blending in silently.
    // Error.md H2 — scale packet/byte volume by the chosen speed multiplier.
    const flows = (attackFlows[attackType] || attackFlows.DDoS).map((f) => ({
      ...f,
      packet_count: Math.round((f.packet_count || 0) * mult),
      byte_count: Math.round((f.byte_count || 0) * mult),
      data_source: 'simulation',
    }))

    try {
      const analyzeResult = await analyzeFlows(flows)
      if (analyzeResult?.ml_mode) {
        state.setMlHealth({ mode: analyzeResult.ml_mode, degraded_reason: analyzeResult.degraded_reason ?? null })
      }

      // Pull the real resulting state back via REST — same normalization
      // path as normal polling (useGraphData.js), just triggered immediately
      // instead of waiting for the next 10s tick.
      const [graphRes, alertsRes, blockedRes, forensicsRes, statsRes, timelineRes, healingRes] =
        await Promise.allSettled([
          getGraph(), getAlerts(), getBlocked(), getForensics(), getStats(), getTimeline(), getHealingEvents(),
        ])

      if (graphRes.status === 'fulfilled') state.setGraphData(graphRes.value)
      if (alertsRes.status === 'fulfilled') state.setAlerts(alertsRes.value.alerts)
      if (blockedRes.status === 'fulfilled') state.setBlockedIPs(blockedRes.value.blocked_ips)
      if (forensicsRes.status === 'fulfilled') {
        state.setChainTxs(forensicsRes.value.blockchain_records ?? [])
        state.setChainId(forensicsRes.value.chain_id ?? null)
      }
      if (statsRes.status === 'fulfilled') state.updateStats(statsRes.value)
      if (timelineRes.status === 'fulfilled') state.setTimeline(timelineRes.value.data_points)
      if (healingRes.status === 'fulfilled') {
        state.setHealingEvents(healingRes.value.events)
      } else if (analyzeResult?.healing_events?.length) {
        analyzeResult.healing_events.forEach((e) => state.addHealingEvent(e))
      }

      if (blockedRes.status === 'fulfilled' && blockedRes.value.blocked_ips?.some((b) => b.ip === targetIp)) {
        state.setHealingNode(targetIp)
      }
    } catch (err) {
      console.error('[simulateAttack] POST /api/v1/analyze failed — backend may be unreachable:', err)
    } finally {
      setTimeout(() => get().endSimulation(), 8000)
    }
  },

  // The Topbar's "Stop Sim" button previously called simulateAttack() again
  // while already simulating, which just hit simulateAttack's own re-entrancy
  // guard (`if connectionMode === 'simulating') return`) and did nothing —
  // clicking it looked like it should cancel, but was inert. This ends the
  // simulating UI state immediately; the in-flight /api/v1/analyze request
  // (if any) still completes server-side since it's a real backend action,
  // it just won't hold the UI in "simulating" waiting for it.
  stopSimulation: () => {
    get().endSimulation()
  },

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
