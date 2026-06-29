// [Windows] GraphSentinel — Susheep
// Graph store — Zustand global state for dashboard
// § 4.5 Fix: connectionMode state machine replaces isMockMode + isSimulating booleans
// MOCK data is untangled from initial state.
import { create } from 'zustand'
import {
  MOCK_GRAPH_DATA,
  MOCK_ALERTS,
  MOCK_BLOCKED,
  MOCK_BLOCKCHAIN_TXS,
  MOCK_HEALING_EVENTS,
  MOCK_TIMELINE,
  MOCK_STATS,
} from '../services/mockData'

// connectionMode values:
//   'connecting'  — app just started, trying to reach backend
//   'live'        — WebSocket/REST returning real data from backend
//   'mock'        — backend unreachable; displaying mock/offline data
//   'simulating'  — demo attack sequence is running

const useGraphStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────
  graphData: { nodes: [], links: [] },
  alerts: [],
  blockedIPs: [],
  chainTxs: [],
  healingEvents: [],
  healingNodeId: null,
  timeline: [],
  stats: { total_nodes: 0, active_threats: 0, blocked_ips: 0, system_health: 100, total_packets: 0, total_bytes: 0 },
  nodeOverrides: {},
  resolvedIncidentIds: [],

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
  setConnectionMode: (mode) => {
    set({ connectionMode: mode })
    if (mode === 'mock') {
      get().loadMockData()
    }
  },

  loadMockData: () => set({
    graphData: MOCK_GRAPH_DATA,
    alerts: MOCK_ALERTS,
    blockedIPs: MOCK_BLOCKED.blocked_ips,
    chainTxs: MOCK_BLOCKCHAIN_TXS,
    healingEvents: MOCK_HEALING_EVENTS,
    timeline: MOCK_TIMELINE,
    stats: MOCK_STATS,
  }),

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
  setTimeline: (data) => set({ timeline: data }),
}))

export default useGraphStore
