// [Windows] GraphSentinel — Susheep
// Graph store — Zustand global state for dashboard
// § 4.5 Fix: connectionMode state machine replaces isMockMode + isSimulating booleans
// MOCK data is untangled from initial state.
import { create } from 'zustand'
import { analyzeFlows, getGraph, getAlerts, getBlocked, getForensics, getStats, getTimeline } from '../services/api'

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
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: true },
  dataErrors: { graph: null, alerts: null, blocked: null, forensics: null, stats: null, timeline: null, health: null, enforcement: null },
}

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
  healingEvents: [],
  healingNodeId: null,
  timeline: [],
  enforcementActions: [],
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0, enforcement_mode: 'simulated', demo_fallback_flows: true },
  nodeOverrides: {},
  resolvedIncidentIds: [],

  // Per-resource freshness (Error.md #22/#26): Promise.allSettled in
  // useGraphData.js updates each panel's data independently, so a panel can
  // silently go stale if only its own fetch keeps failing while others
  // succeed. This lets the UI show that panel is stale instead of pretending
  // null (last fetch OK) or an error message string.
  dataErrors: { graph: null, alerts: null, blocked: null, forensics: null, stats: null, timeline: null, health: null, enforcement: null },
  setDataError: (resource, error) =>
    set((state) => ({ dataErrors: { ...state.dataErrors, [resource]: error } })),

  // ── Connection state machine ───────────────────────────────
  connectionMode: 'connecting', // 'connecting' | 'live' | 'mock' | 'simulating'

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
    set({ connectionMode: mode })
    if (mode === 'mock') {
      set(EMPTY_STATE)
    }
  },

  // Legacy setters — kept for backward compat, mapped to connectionMode
  setMockMode: (isMock) =>
    get().setConnectionMode(isMock ? 'mock' : get().connectionMode === 'mock' ? 'live' : get().connectionMode),
  
  setSimulating: (isSimulating) =>
    get().setConnectionMode(isSimulating
      ? 'simulating'
      : get().connectionMode === 'simulating'
        ? (get().isConnected ? 'live' : 'mock')
        : get().connectionMode),

  // ── Data setters ──────────────────────────────────────────
  setGraphData: (data) => set({ graphData: data }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50),
    })),

  setHealingNode: (ip) => {
    set({ healingNodeId: ip })
    if (ip) {
      setTimeout(() => set({ healingNodeId: null }), 3500)
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
  simulateAttack: async ({ attackType = 'DDoS', targetIp = '10.0.0.2', victimIp = '10.0.0.1' } = {}) => {
    const state = get()
    if (state.connectionMode === 'simulating') return

    state.setConnectionMode('simulating')

    const attackFlows = {
      DDoS: [
        { src_ip: targetIp, dst_ip: victimIp, src_port: 54321, dst_port: 80, protocol: 'TCP', packet_count: 15000, byte_count: 5120000, duration_sec: 3.5, tcp_flags: 2 },
        { src_ip: targetIp, dst_ip: victimIp, src_port: 54322, dst_port: 443, protocol: 'TCP', packet_count: 12000, byte_count: 4300000, duration_sec: 3.5, tcp_flags: 2 },
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
    const flows = (attackFlows[attackType] || attackFlows.DDoS).map((f) => ({ ...f, data_source: 'simulation' }))

    try {
      const analyzeResult = await analyzeFlows(flows)
      if (analyzeResult?.ml_mode) {
        state.setMlHealth({ mode: analyzeResult.ml_mode, degraded_reason: analyzeResult.degraded_reason ?? null })
      }

      // Pull the real resulting state back via REST — same normalization
      // path as normal polling (useGraphData.js), just triggered immediately
      // instead of waiting for the next 10s tick.
      const [graphRes, alertsRes, blockedRes, forensicsRes, statsRes, timelineRes] =
        await Promise.allSettled([
          getGraph(), getAlerts(), getBlocked(), getForensics(), getStats(), getTimeline(),
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

      if (blockedRes.status === 'fulfilled' && blockedRes.value.blocked_ips?.some((b) => b.ip === targetIp)) {
        state.setHealingNode(targetIp)
      }
    } catch (err) {
      console.error('[simulateAttack] POST /api/v1/analyze failed — backend may be unreachable:', err)
    } finally {
      setTimeout(() => {
        if (get().connectionMode === 'simulating') {
          get().setConnectionMode(get().isConnected ? 'live' : 'mock')
        }
      }, 8000)
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
    const state = get()
    if (state.connectionMode !== 'simulating') return
    state.setConnectionMode(state.isConnected ? 'live' : 'mock')
  },

  resolveIncident: (incidentId) =>
    set((state) => ({
      resolvedIncidentIds: [...state.resolvedIncidentIds, incidentId],
    })),

  // ── UI setters ────────────────────────────────────────────
  toggleView: () => set((state) => ({ use3D: !state.use3D })),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setConnected: (connected) =>
    set((state) => ({
      isConnected: connected,
      connectionMode:
        state.connectionMode === 'simulating'
          ? 'simulating' // don't interrupt simulation
          : connected
            ? 'live'
            : 'mock',
    })),
  setForensicsOpen: (open) => set({ forensicsOpen: open }),

  setAlerts: (alerts) => set({ alerts }),
  setBlockedIPs: (ips) => set({ blockedIPs: ips }),
  setChainTxs: (txs) => set({ chainTxs: txs }),
  setChainId: (id) => set({ chainId: id }),
  setTimeline: (data) => set({ timeline: data }),
  setEnforcementActions: (actions) => set({ enforcementActions: actions }),
}))

export default useGraphStore
