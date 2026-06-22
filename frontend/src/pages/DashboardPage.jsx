// [Windows] GraphSentinel — Susheep
// ── ALL state, effects, callbacks, hooks, and handlers PRESERVED VERBATIM ──
// Updates: connectionMode wired into simulateAttack, onReconnect REST refresh
import { useEffect, useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import useAuthStore from '../store/useAuthStore'
import useGraphStore from '../store/useGraphStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { useGraphData } from '../hooks/useGraphData'
import { blockIP } from '../services/api'

import StatsBar from '../components/dashboard/StatsBar'
import NetworkGraph3D from '../components/dashboard/NetworkGraph3D'
import NetworkGraph2D from '../components/dashboard/NetworkGraph2D'
import AlertPanel from '../components/dashboard/AlertPanel'
import BlockchainPanel from '../components/dashboard/BlockchainPanel'
import SelfHealStatus from '../components/dashboard/SelfHealStatus'
import ThreatTimeline from '../components/dashboard/ThreatTimeline'
import NodeDetailPanel from '../components/dashboard/NodeDetailPanel'
import ForensicsModal from '../components/dashboard/ForensicsModal'
import LoadingScreen from '../components/shared/LoadingScreen'

export default function DashboardPage() {
  // ── Original state + store — untouched ──
  const navigate = useNavigate()
  const { logout } = useAuthStore()
  const [showLoading, setShowLoading] = useState(true)

  const {
    graphData,
    alerts,
    chainTxs,
    healingEvents,
    healingNodeId,
    timeline,
    stats,
    connectionMode,
    use3D,
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
  } = useGraphStore()

  // ── Original effects — untouched ──
  useEffect(() => {
    const t = setTimeout(() => setShowLoading(false), 2000)
    return () => clearTimeout(t)
  }, [])

  const { refresh: refreshData } = useGraphData()

  // ── Original WebSocket handlers — untouched ──
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

  const { isConnected } = useWebSocket({
    onGraphUpdate: handleGraphUpdate,
    onAlert: handleAlert,
    onHealingTriggered: handleHealingTriggered,
    onConnect: () => setConnected(true),
    onDisconnect: () => setConnected(false),
    // § 2 soft spot fix: re-fetch via REST on reconnect since socket doesn't re-emit graph_update
    onReconnect: () => refreshData(),
  })

  // ── simulateAttack — § 4.2 fix: connectionMode drives simulation state ──
  const simulateAttack = useCallback(() => {
    if (connectionMode === 'simulating') return
    setConnectionMode('simulating') // § 4.2: single source of truth

    // Purely client-side demo sequence to avoid backend state desync.

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
          // End simulation — return to appropriate mode
          setConnectionMode(isConnected ? 'live' : 'mock')
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
    isConnected,
  ])

  // ── Original handlers — untouched ──
  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const handleBlock = async (ip, action) => {
    try {
      await blockIP(ip, action)
    } catch {
      console.warn('[Dashboard] Block API unavailable in mock mode')
    }
    setSelectedNode(null)
  }

  if (showLoading) return <LoadingScreen />

  return (
    <div
      className="h-screen w-screen flex flex-col overflow-hidden"
      style={{ backgroundColor: '#0A0A0A' }}
    >
      {/* Subtle ambient radial */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] rounded-full blur-[120px]"
          style={{ background: 'rgba(79,110,247,0.04)' }}
        />
      </div>

      {/* ── Top Stats Bar ── */}
      <StatsBar
        stats={stats}
        onForensicsClick={() => setForensicsOpen(true)}
        onLogout={handleLogout}
        onSimulate={simulateAttack}
      />

      {/* ── Main content split ── */}
      <div className="flex flex-1 overflow-hidden gap-1.5 p-1.5 relative z-10">

        {/* ── Left: Graph Canvas Panel ── */}
        <div
          className="flex-1 relative rounded-xl overflow-hidden border border-gs-border"
          style={{ backgroundColor: '#141414' }}
        >
          {/* Graph mode label — top-left floating pill */}
          <div className="absolute top-3 left-3 z-10 flex items-center gap-2 bg-gs-surface border border-gs-border px-2.5 py-1.5 rounded-lg">
            <span className="text-[10px] font-mono text-gs-muted tracking-wider">
              {use3D ? '3D Network Graph' : '2D Network Graph'}
            </span>
          </div>

          {/* Toggle button — original onClick preserved */}
          <button
            id="graph-view-toggle"
            onClick={toggleView}
            className="absolute top-3 right-3 z-10 tac-btn bg-gs-surface border border-gs-border text-[10px] text-gs-muted px-2.5 py-1.5 rounded-lg hover:border-gs-accent/40 hover:text-gs-accent transition-all duration-200 font-mono"
          >
            {use3D ? 'Switch to 2D' : 'Switch to 3D'}
          </button>

          {/* Graph render — original components + all props preserved */}
          {use3D ? (
            <NetworkGraph3D
              graphData={graphData}
              healingNodeId={healingNodeId}
              onNodeClick={(node) => setSelectedNode(node)}
            />
          ) : (
            <NetworkGraph2D graphData={graphData} healingNodeId={healingNodeId} />
          )}

          {/* Bottom-left connection indicator */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-gs-surface border border-gs-border px-2.5 py-1.5 rounded-lg">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                backgroundColor: isConnected ? '#2ECC8A' : connectionMode === 'simulating' ? '#E8922A' : '#5A6480',
              }}
              aria-hidden="true"
            />
            <span className="text-[10px] font-mono text-gs-muted">
              {connectionMode === 'live' ? 'LIVE · Updates every 5s' :
               connectionMode === 'simulating' ? 'SIMULATION ACTIVE' :
               connectionMode === 'connecting' ? 'CONNECTING...' : 'OFFLINE · Mock data'}
            </span>
          </div>
        </div>

        {/* ── Right: Telemetry Sidebar ── */}
        <div className="w-[340px] flex flex-col gap-1.5 overflow-hidden shrink-0">
          <div className="flex-[2] overflow-auto min-h-0">
            <AlertPanel alerts={alerts} />
          </div>
          <div className="flex-[1.5] overflow-auto min-h-0">
            <BlockchainPanel transactions={chainTxs} />
          </div>
          <div className="flex-1 overflow-auto min-h-0">
            <SelfHealStatus events={healingEvents} />
          </div>
        </div>
      </div>

      {/* ── Bottom: Timeline bar ── */}
      <div
        className="h-28 shrink-0 px-2 pb-1 border-t border-gs-border"
        style={{ backgroundColor: '#141414' }}
      >
        <ThreatTimeline data={timeline} />
      </div>

      {/* ── Node Detail overlay — AnimatePresence + original bindings preserved ── */}
      <AnimatePresence>
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onBlock={handleBlock}
          />
        )}
      </AnimatePresence>

      {/* ── Forensics Modal — original bindings preserved ── */}
      <ForensicsModal isOpen={forensicsOpen} onClose={() => setForensicsOpen(false)} />
    </div>
  )
}
