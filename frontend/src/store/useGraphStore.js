// [Windows] GraphSentinel — Susheep
// Graph store — Zustand global state for dashboard
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

const useGraphStore = create((set, get) => ({
  graphData: MOCK_GRAPH_DATA,
  alerts: MOCK_ALERTS,
  blockedIPs: MOCK_BLOCKED.blocked_ips,
  chainTxs: MOCK_BLOCKCHAIN_TXS,
  healingEvents: MOCK_HEALING_EVENTS,
  healingNodeId: null,
  timeline: MOCK_TIMELINE,
  stats: MOCK_STATS,
  isMockMode: true,
  isConnected: false,
  use3D: true,
  selectedNode: null,
  forensicsOpen: false,
  isSimulating: false,

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

  toggleView: () => set((state) => ({ use3D: !state.use3D })),

  setSelectedNode: (node) => set({ selectedNode: node }),

  setMockMode: (isMock) => set({ isMockMode: isMock }),

  setConnected: (connected) => set({ isConnected: connected }),

  updateStats: (partial) =>
    set((state) => ({ stats: { ...state.stats, ...partial } })),

  setForensicsOpen: (open) => set({ forensicsOpen: open }),

  setAlerts: (alerts) => set({ alerts }),
  setBlockedIPs: (ips) => set({ blockedIPs: ips }),
  setChainTxs: (txs) => set({ chainTxs: txs }),
  setTimeline: (data) => set({ timeline: data }),
  setSimulating: (isSimulating) => set({ isSimulating }),
}))

export default useGraphStore
