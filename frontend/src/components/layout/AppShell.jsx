// [Windows] GraphSentinel — Susheep
// AppShell — persistent layout: sidebar + topbar + page outlet
// WebSocket, simulateAttack, and NodeDetailPanel all live here so they
// survive navigation between routes without resetting.
import { useState, useCallback, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import NodeDetailPanel from '../dashboard/NodeDetailPanel'
import ForensicsModal from '../dashboard/ForensicsModal'
import LoadingScreen from '../shared/LoadingScreen'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useGraphData } from '../../hooks/useGraphData'
import { blockIP } from '../../services/api'
import useGraphStore from '../../store/useGraphStore'

export default function AppShell() {
  const [sidebarPinned, setSidebarPinned] = useState(false)
  const [sidebarHovered, setSidebarHovered] = useState(false)
  const [showLoading, setShowLoading] = useState(true)
  const sidebarOpen = sidebarPinned || sidebarHovered

  // ── Zustand store ──────────────────────────────────────────────────
  const {
    graphData,
    alerts,
    chainTxs,
    stats,
    connectionMode,
    selectedNode,
    forensicsOpen,
    setGraphData,
    addAlert,
    setHealingNode,
    addHealingEvent,
    addTimelinePoint,
    toggleView,
    setSelectedNode,
    setConnected,
    setForensicsOpen,
    setAlerts,
    setChainTxs,
    updateStats,
    setConnectionMode,
    isConnected,
  } = useGraphStore()

  // ── Initial loading splash ─────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setShowLoading(false), 1800)
    return () => clearTimeout(t)
  }, [])

  const { refresh: refreshData } = useGraphData()

  // ── WebSocket handlers (verbatim from old DashboardPage) ───────────
  const handleGraphUpdate = useCallback(
    (data) => {
      if (connectionMode === 'simulating') return
      setGraphData(data)
      setConnectionMode('live')
    },
    [setGraphData, setConnectionMode, connectionMode]
  )

  const handleAlert = useCallback(
    (alert, isLocal = false) => {
      if (connectionMode === 'simulating' && !isLocal) return
      addAlert(alert)
      addTimelinePoint({
        time: new Date().toLocaleTimeString().slice(0, 5),
        threats: 1,
        blocked: 0,
      })

      if (isLocal) {
        setGraphData({
          ...graphData,
          nodes: graphData.nodes.map((n) =>
            n.id === alert.source_ip
              ? {
                  ...n,
                  status: 'malicious',
                  threat_score: alert.threat_score,
                  attack_type: alert.attack_type,
                  connections: n.connections > 0 ? n.connections : 12,
                }
              : n
          ),
        })
        updateStats({
          active_threats: stats.active_threats + 1,
          system_health: Math.max(50, stats.system_health - 15),
        })
      }
    },
    [addAlert, addTimelinePoint, connectionMode, graphData, setGraphData, updateStats, stats]
  )

  const handleHealingTriggered = useCallback(
    (event, isLocal = false) => {
      if (connectionMode === 'simulating' && !isLocal) return
      setHealingNode(event.ip)
      addHealingEvent(event)
      addTimelinePoint({
        time: new Date().toLocaleTimeString().slice(0, 5),
        threats: 0,
        blocked: 1,
      })

      if (isLocal) {
        const txHash = '0x' + Array.from({ length: 40 }, () =>
          Math.floor(Math.random() * 16).toString(16)
        ).join('')

        const incidentHash = '0x' + Array.from({ length: 40 }, () =>
          Math.floor(Math.random() * 16).toString(16)
        ).join('')

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

        setGraphData({
          ...graphData,
          nodes: graphData.nodes.map((n) =>
            n.id === event.ip
              ? { ...n, status: 'blocked', connections: 0, is_blocked: true }
              : n
          ),
          links: graphData.links.filter((l) => {
            const srcId = typeof l.source === 'object' ? l.source.id : l.source
            const tgtId = typeof l.target === 'object' ? l.target.id : l.target
            return srcId !== event.ip && tgtId !== event.ip
          }),
        })

        const activeCount = Math.max(0, stats.active_threats)
        const blockedCount = stats.blocked_ips + 1
        const sysHealth = Math.min(100, Math.max(0, 100 - activeCount * 12 - blockedCount * 4))

        updateStats({
          active_threats: activeCount,
          blocked_ips: blockedCount,
          system_health: sysHealth,
        })

        setChainTxs([demoTx, ...chainTxs])

        const updatedAlerts = alerts.map((a) =>
          a.source_ip === event.ip
            ? { ...a, is_blocked: true, blockchain_tx: txHash }
            : a
        )
        setAlerts(updatedAlerts)
      }
    },
    [setHealingNode, addHealingEvent, addTimelinePoint, connectionMode, graphData, setGraphData, updateStats, stats, setChainTxs, chainTxs, alerts, setAlerts]
  )

  const { isConnected: wsConnected } = useWebSocket({
    onGraphUpdate: handleGraphUpdate,
    onAlert: handleAlert,
    onHealingTriggered: handleHealingTriggered,
    onConnect: () => setConnected(true),
    onDisconnect: () => setConnected(false),
    onReconnect: () => refreshData(),
  })

  // ── simulateAttack (verbatim from old DashboardPage) ─────────────
  const simulateAttack = useCallback(() => {
    if (connectionMode === 'simulating') return
    setConnectionMode('simulating')

    const resetGraph = {
      ...graphData,
      nodes: graphData.nodes.map((n) =>
        n.id === '10.0.0.2'
          ? { ...n, status: 'normal', threat_score: 0.05, is_blocked: false }
          : n
      ),
      links: graphData.links.some((l) => {
        const src = typeof l.source === 'object' ? l.source.id : l.source
        return src === '10.0.0.2'
      })
        ? graphData.links
        : [
            ...graphData.links,
            { source: '10.0.0.2', target: '10.0.0.1', value: 0.94, attack_type: 'DDoS', packet_count: 15000 },
            { source: '10.0.0.2', target: '10.0.0.3', value: 0.87, attack_type: 'DDoS', packet_count: 8200 },
          ],
    }
    setGraphData(resetGraph)

    const cleanedAlerts = alerts.filter((a) => a.source_ip !== '10.0.0.2')
    setAlerts(cleanedAlerts)

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
      handleAlert(demoAlert, true)

      setTimeout(() => {
        handleHealingTriggered(
          {
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
          },
          true
        )

        setTimeout(() => {
          setConnectionMode(wsConnected ? 'live' : 'mock')
        }, 30000)
      }, 3000)
    }, 1000)
  }, [
    connectionMode,
    graphData,
    setGraphData,
    alerts,
    setAlerts,
    setConnectionMode,
    handleAlert,
    handleHealingTriggered,
    wsConnected,
  ])

  // ── handleBlock (verbatim) ─────────────────────────────────────────
  const handleBlock = async (ip, action) => {
    try {
      await blockIP(ip, action)
    } catch {
      console.warn('[AppShell] Block API unavailable in mock mode')
    }
    setSelectedNode(null)
  }

  if (showLoading) return <LoadingScreen />

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `${sidebarOpen ? '220px' : '64px'} 1fr`,
        gridTemplateRows: '48px 1fr',
        height: '100vh',
        overflow: 'hidden',
        transition: 'grid-template-columns 200ms ease',
        background: '#0A0A0A',
      }}
    >
      {/* Sidebar spans both rows */}
      <div style={{ gridRow: '1 / 3', gridColumn: 1 }}>
        <Sidebar
          expanded={sidebarOpen}
          pinned={sidebarPinned}
          onPinToggle={() => setSidebarPinned((p) => !p)}
          onHoverChange={setSidebarHovered}
        />
      </div>

      {/* Topbar */}
      <div style={{ gridColumn: 2, gridRow: 1 }}>
        <Topbar
          onSimulate={simulateAttack}
          onForensicsClick={() => setForensicsOpen(true)}
        />
      </div>

      {/* Page content */}
      <main
        style={{
          gridColumn: 2,
          gridRow: 2,
          overflow: 'auto',
          padding: '20px',
          position: 'relative',
        }}
      >
        {/* Ambient radial glow */}
        <div
          className="fixed inset-0 pointer-events-none"
          style={{ zIndex: 0 }}
        >
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] rounded-full blur-[120px]"
            style={{ background: 'rgba(79,110,247,0.04)' }}
          />
        </div>

        <div style={{ position: 'relative', zIndex: 1 }}>
          <Outlet />
        </div>
      </main>

      {/* Node detail overlay — available on any page */}
      <AnimatePresence>
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onBlock={handleBlock}
          />
        )}
      </AnimatePresence>

      {/* Forensics modal — triggered from topbar */}
      <ForensicsModal isOpen={forensicsOpen} onClose={() => setForensicsOpen(false)} />
    </div>
  )
}
