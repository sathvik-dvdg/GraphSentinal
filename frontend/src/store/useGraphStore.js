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
  orgHierarchy: null,
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
  setOrgHierarchy: (hierarchy) => set({ orgHierarchy: hierarchy }),

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

  simulateAttack: () => {
    const state = get()
    if (state.connectionMode === 'simulating') return
    
    state.setConnectionMode('simulating')

    const resetGraph = {
      ...state.graphData,
      nodes: state.graphData.nodes.map((n) =>
        n.id === '10.0.0.2'
          ? { ...n, status: 'normal', threat_score: 0.05, is_blocked: false }
          : n
      ),
      links: state.graphData.links.some((l) => {
        const src = typeof l.source === 'object' ? l.source.id : l.source
        return src === '10.0.0.2'
      })
        ? state.graphData.links
        : [
            ...state.graphData.links,
            { source: '10.0.0.2', target: '10.0.0.1', value: 0.94, attack_type: 'DDoS', packet_count: 15000 },
            { source: '10.0.0.2', target: '10.0.0.3', value: 0.87, attack_type: 'DDoS', packet_count: 8200 },
          ],
    }
    state.setGraphData(resetGraph)

    const cleanedAlerts = state.alerts.filter((a) => a.source_ip !== '10.0.0.2')
    state.setAlerts(cleanedAlerts)

    setTimeout(() => {
      const demoAlert = {
        id: `demo-${Date.now()}`,
        timestamp: new Date().toISOString(),
        source_ip: '10.0.0.2',
        attack_type: 'DDoS',
        severity: 'critical',
        threat_score: 0.94,
        description: 'DEMO: DDoS attack from 10.0.0.2',
        is_blocked: false,
        blockchain_tx: null,
      }
      
      // Manually apply the effects of handleAlert since it's local
      state.addAlert(demoAlert)
      state.addTimelinePoint({
        time: new Date().toLocaleTimeString().slice(0, 5),
        threats: 1,
        blocked: 0,
      })
      
      // Optimistically update the node graph representation
      state.setGraphData({
        ...state.graphData,
        nodes: state.graphData.nodes.map((n) =>
          n.id === demoAlert.source_ip
            ? {
                ...n,
                status: 'malicious',
                threat_score: demoAlert.threat_score,
                attack_type: demoAlert.attack_type,
                connections: n.connections > 0 ? n.connections : 12,
              }
            : n
        ),
      })
      state.updateStats({
        active_threats: state.stats.active_threats + 1,
        system_health: Math.max(50, state.stats.system_health - 15),
      })

      setTimeout(() => {
        const event = {
          id: `heal-${Date.now()}`,
          timestamp: new Date().toISOString(),
          ip: '10.0.0.2',
          action: 'ISOLATED',
          attack_type: 'DDoS',
          trigger_score: 0.94,
          edges_severed: 6,
          duration_ms: 312,
          network_stability_before: 76,
          network_stability_after: 94,
        }
        
        state.setHealingNode(event.ip)
        state.addHealingEvent(event)
        state.addTimelinePoint({
          time: new Date().toLocaleTimeString().slice(0, 5),
          threats: 0,
          blocked: 1,
        })
        
        // Optimistic UI for blocking
        const txHash = '0x' + Array.from({ length: 40 }, () => Math.floor(Math.random() * 16).toString(16)).join('')
        const incidentHash = '0x' + Array.from({ length: 40 }, () => Math.floor(Math.random() * 16).toString(16)).join('')

        const demoTx = {
          id: Date.now(),
          incident_hash: incidentHash,
          timestamp: new Date().toISOString(),
          source_ip: event.ip,
          attack_type: event.attack_type,
          severity: 9,
          is_blocked: true,
          forensics_uri: `local://incident/${event.id}`,
          tx_hash: txHash,
          block_number: Math.floor(Math.random() * 100) + 150,
          gas_used: 68000 + Math.floor(Math.random() * 5000),
          status: 'confirmed',
        }

        // Apply optimistic severed edges UI updates without relying on WS
        state.setGraphData({
          ...state.graphData,
          nodes: state.graphData.nodes.map((n) =>
            n.id === event.ip
              ? { ...n, status: 'blocked', connections: 0, is_blocked: true }
              : n
          ),
          links: state.graphData.links.filter((l) => {
            const srcId = typeof l.source === 'object' ? l.source.id : l.source
            const tgtId = typeof l.target === 'object' ? l.target.id : l.target
            return srcId !== event.ip && tgtId !== event.ip
          }),
        })

        const activeCount = Math.max(0, state.stats.active_threats)
        const blockedCount = state.stats.blocked_ips + 1
        const sysHealth = Math.min(100, Math.max(0, 100 - activeCount * 12 - blockedCount * 4))

        state.updateStats({
          active_threats: activeCount,
          blocked_ips: blockedCount,
          system_health: sysHealth,
        })

        state.setChainTxs([demoTx, ...state.chainTxs])
        const updatedAlerts = state.alerts.map((a) =>
          a.source_ip === event.ip ? { ...a, is_blocked: true, blockchain_tx: txHash } : a
        )
        state.setAlerts(updatedAlerts)

        setTimeout(() => {
          get().setConnectionMode(get().isConnected ? 'live' : 'mock')
        }, 30000)
      }, 3000)
    }, 1000)
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
  setTimeline: (data) => set({ timeline: data }),
}))

export default useGraphStore
