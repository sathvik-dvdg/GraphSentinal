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
      setGraphData(data)
      setMockMode(false)
    },
    [setGraphData, setMockMode]
  )

  const handleAlert = useCallback(
    (alert) => {
      addAlert(alert)
      addTimelinePoint({
        time: new Date().toLocaleTimeString().slice(0, 5),
        threats: 1,
        blocked: 0,
      })
    },
    [addAlert, addTimelinePoint]
  )

  const handleHealingTriggered = useCallback(
    (event) => {
      setHealingNode(event.ip)
      addHealingEvent(event)
      addTimelinePoint({
        time: new Date().toLocaleTimeString().slice(0, 5),
        threats: 0,
        blocked: 1,
      })
    },
    [setHealingNode, addHealingEvent, addTimelinePoint]
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
    handleAlert(demoAlert)
    setTimeout(() => {
      handleHealingTriggered({
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
      })
    }, 2000)
  }, [handleAlert, handleHealingTriggered])

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
      <div className="flex flex-1 overflow-hidden gap-1 p-1">
        {/* Left: Graph Panel */}
        <div className="flex-1 relative rounded-lg overflow-hidden border border-gs-border">
          {/* Top-left label */}
          <div className="absolute top-3 left-3 z-10 text-xs font-mono text-gray-500 bg-gs-bg/80 px-2 py-1 rounded">
            {use3D ? '3D NETWORK GRAPH' : '2D NETWORK GRAPH'}
          </div>

          {/* Toggle button */}
          <button
            onClick={toggleView}
            className="absolute top-3 right-3 z-10 bg-gs-card border border-gs-border
                       text-xs text-gray-400 px-3 py-1 rounded hover:border-gs-accent
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
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-gs-bg/80 px-2 py-1 rounded">
            <div
              className="w-2 h-2 rounded-full accent-glow"
              style={{ backgroundColor: isConnected ? '#00ff88' : '#ffaa00' }}
            />
            <span className="text-xs font-mono text-gray-500">
              {isConnected ? '● LIVE' : '● SIM'} · Updates every 5s
            </span>
          </div>
        </div>

        {/* Right: Control Column */}
        <div className="w-80 flex flex-col gap-1 overflow-hidden">
          <div className="flex-1 overflow-auto">
            <AlertPanel alerts={alerts} />
          </div>
          <div className="flex-1 overflow-auto">
            <BlockchainPanel transactions={chainTxs} />
          </div>
          <div className="overflow-auto max-h-40">
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
