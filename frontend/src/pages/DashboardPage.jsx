// [Windows] GraphSentinel — Susheep
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
    isMockMode,
    use3D,
    selectedNode,
    forensicsOpen,
    isSimulating,
    setGraphData,
    addAlert,
    setHealingNode,
    addHealingEvent,
    addTimelinePoint,
    toggleView,
    setSelectedNode,
    setMockMode,
    setConnected,
    setForensicsOpen,
    setSimulating,
    setAlerts,
    setChainTxs,
    updateStats,
  } = useGraphStore()

  // Initial loading screen
  useEffect(() => {
    const t = setTimeout(() => setShowLoading(false), 2000)
    return () => clearTimeout(t)
  }, [])

  // REST polling fallback
  useGraphData()

  // WebSocket handlers
  const handleGraphUpdate = useCallback(
    (data) => {
      if (isSimulating) return
      setGraphData(data)
      setMockMode(false)
    },
    [setGraphData, setMockMode, isSimulating]
  )

  const handleAlert = useCallback(
    (alert, isLocal = false) => {
      if (isSimulating && !isLocal) return
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
    [addAlert, addTimelinePoint, isSimulating, graphData, setGraphData, updateStats, stats]
  )

  const handleHealingTriggered = useCallback(
    (event, isLocal = false) => {
      if (isSimulating && !isLocal) return
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
    [setHealingNode, addHealingEvent, addTimelinePoint, isSimulating, graphData, setGraphData, updateStats, stats, setChainTxs, chainTxs, alerts, setAlerts]
  )

  const { isConnected } = useWebSocket({
    onGraphUpdate: handleGraphUpdate,
    onAlert: handleAlert,
    onHealingTriggered: handleHealingTriggered,
    onConnect: () => setConnected(true),
    onDisconnect: () => setConnected(false),
  })

  // Demo simulation — triggered by the SIMULATE button in StatsBar
  const simulateAttack = useCallback(() => {
    if (isSimulating) return
    setSimulating(true)

    // Reset 10.0.0.2 to normal at the start of simulation so we can see the full cycle
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

    // Clear previous simulation alerts for 10.0.0.2 to keep it clean
    const cleanedAlerts = alerts.filter((a) => a.source_ip !== '10.0.0.2')
    setAlerts(cleanedAlerts)

    // Trigger the threat detection in 1000ms
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

      // Trigger the self-healing isolation after another 3000ms
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

        // Reset simulating state in 12 seconds
        setTimeout(() => {
          setSimulating(false)
        }, 12000)
      }, 3000)
    }, 1000)
  }, [
    graphData,
    setGraphData,
    alerts,
    setAlerts,
    isSimulating,
    setSimulating,
    handleAlert,
    handleHealingTriggered,
  ])

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
    <div className="h-screen w-screen bg-gs-bg flex flex-col overflow-hidden">
      {/* Top Stats Bar */}
      <StatsBar
        stats={stats}
        isMockMode={isMockMode}
        isConnected={isConnected}
        onForensicsClick={() => setForensicsOpen(true)}
        onLogout={handleLogout}
        onSimulate={simulateAttack}
      />

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden gap-1.5 p-1.5">
        {/* Left: Graph Panel */}
        <div className="flex-1 relative rounded-lg overflow-hidden border border-gs-border">
          {/* Top-left label */}
          <div className="absolute top-3 left-3 z-10 text-xs font-mono text-gray-500 bg-gs-bg/80 px-2 py-1 rounded border border-gs-border/50">
            {use3D ? '🌐 3D NETWORK GRAPH' : '📊 2D NETWORK GRAPH'}
          </div>

          {/* Toggle button */}
          <button
            onClick={toggleView}
            className="absolute top-3 right-3 z-10 bg-gs-card border border-gs-border
                       text-xs text-gray-400 px-3 py-1.5 rounded hover:border-gs-accent
                       hover:text-gs-accent transition-colors font-mono"
          >
            {use3D ? '[ 2D MODE ]' : '[ 3D MODE ]'}
          </button>

          {/* Graph */}
          {use3D ? (
            <NetworkGraph3D
              graphData={graphData}
              healingNodeId={healingNodeId}
              onNodeClick={(node) => setSelectedNode(node)}
            />
          ) : (
            <NetworkGraph2D graphData={graphData} healingNodeId={healingNodeId} />
          )}

          {/* Bottom-left LIVE indicator */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-gs-bg/80 px-2.5 py-1.5 rounded border border-gs-border/50">
            <div
              className="w-2 h-2 rounded-full accent-glow"
              style={{ backgroundColor: isConnected ? '#00ff88' : '#ffaa00' }}
            />
            <span className="text-xs font-mono text-gray-500">
              {isConnected ? '● LIVE' : '● SIM'} · Updates every 5s
            </span>
          </div>
        </div>

        {/* Right: Control Column — wider for readability */}
        <div className="w-[360px] flex flex-col gap-1.5 overflow-hidden shrink-0">
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

      {/* Bottom: Timeline */}
      <div className="h-28 border-t border-gs-border px-2 pb-1 shrink-0">
        <ThreatTimeline data={timeline} />
      </div>

      {/* Node Detail Panel — fixed overlay so Three.js canvas cannot block it */}
      <AnimatePresence>
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onBlock={handleBlock}
          />
        )}
      </AnimatePresence>

      {/* Forensics Modal */}
      <ForensicsModal isOpen={forensicsOpen} onClose={() => setForensicsOpen(false)} />
    </div>
  )
}
