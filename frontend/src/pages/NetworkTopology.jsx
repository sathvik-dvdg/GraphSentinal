// [Windows] GraphSentinel — Susheep
// NetworkTopology — 3D/2D graph + Pyramid hierarchy split view
import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import useGraphStore from '../store/useGraphStore'
import NetworkGraph3D from '../components/dashboard/NetworkGraph3D'
import NetworkGraph2D from '../components/dashboard/NetworkGraph2D'
import PyramidHierarchy from '../components/pyramid/PyramidHierarchy'
import ConnectionModeBadge from '../components/ui/ConnectionModeBadge'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { withTopologyScaffold } from '../utils/topologyScaffold'

const VIEW_MODES = [
  { id: 'split',   label: 'Split View' },
  { id: '3d',      label: '3D Graph' },
  { id: '2d',      label: '2D Graph' },
  { id: 'pyramid', label: 'Org Pyramid' },
]

export default function NetworkTopology() {
  const [viewMode, setViewMode] = useState('split')
  const { graphData, healingNodeId, connectionMode, setSelectedNode, dataErrors } = useGraphStore()

  // Overlay the configured star topology (c0 → s1 → h1..h10) so the graph is
  // never a disconnected scatter when the pipeline is idle. Real traffic
  // links from the backend are layered on top.
  const topologyData = useMemo(() => withTopologyScaffold(graphData), [graphData])
  const hasTopology = topologyData.nodes.length > 0

  // Scaffold nodes (the switch / controller) aren't hosts — don't open the
  // host detail panel for them.
  const handleNodeClick = (node) => {
    if (node?.kind) return
    setSelectedNode(node)
  }

  const show3D = viewMode === '3d' || viewMode === 'split'
  const show2D = viewMode === '2d'
  const showPyramid = viewMode === 'pyramid' || viewMode === 'split'
  const isSplit = viewMode === 'split'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 108px)' }}>
      {/* Header + controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Network Topology
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
              Live network graph · Org hierarchy · Threat vectors
            </p>
            <DataFreshnessBadge dataErrors={{ graph: dataErrors.graph }} />
          </div>
        </div>

        {/* View mode toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            background: '#f0f2f5',
            border: '1px solid rgba(17,20,26,0.10)',
            borderRadius: 8,
            padding: 3,
          }}
        >
          {VIEW_MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setViewMode(m.id)}
              style={{
                padding: '5px 14px',
                borderRadius: 6,
                border: 'none',
                background: viewMode === m.id ? 'rgba(79,110,247,0.2)' : 'transparent',
                color: viewMode === m.id ? '#3b56d9' : '#727a86',
                fontSize: 11,
                fontFamily: "'DM Mono', monospace",
                cursor: 'pointer',
                transition: 'all 150ms',
                fontWeight: viewMode === m.id ? 600 : 400,
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content panels */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: isSplit ? '1fr 1fr' : '1fr',
          gap: 16,
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        {/* Graph panel */}
        {(show3D || show2D) && (
          <motion.div
            key={viewMode === '2d' ? '2d' : '3d'}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="gs-panel"
            style={{ position: 'relative', overflow: 'hidden', minHeight: 0 }}
          >
            {/* Mode label */}
            <div
              style={{
                position: 'absolute',
                top: 12,
                left: 12,
                zIndex: 10,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: 'rgba(255,255,255,0.88)',
                border: '1px solid rgba(17,20,26,0.10)',
                borderRadius: 8,
                padding: '4px 10px',
              }}
            >
              <span style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                {show2D ? '2D Network Graph' : '3D Network Graph'}
              </span>
              <ConnectionModeBadge mode={connectionMode} />
            </div>

            {!hasTopology ? (
              <TopologyEmptyState connectionMode={connectionMode} />
            ) : show2D ? (
              <NetworkGraph2D
                graphData={topologyData}
                healingNodeId={healingNodeId}
                onNodeClick={handleNodeClick}
              />
            ) : (
              <NetworkGraph3D
                graphData={topologyData}
                healingNodeId={healingNodeId}
                onNodeClick={handleNodeClick}
              />
            )}
          </motion.div>
        )}

        {/* Pyramid panel */}
        {showPyramid && (
          <motion.div
            key="pyramid"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="gs-panel"
            style={{ position: 'relative', overflow: 'hidden', minHeight: 0 }}
          >
            {/* Header */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                zIndex: 5,
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.92)',
                borderBottom: '1px solid rgba(17,20,26,0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span style={{ color: '#1D9E75', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Org Hierarchy · Lateral Movement Detection
              </span>
            </div>
            <div style={{ paddingTop: 42, height: '100%', overflowY: 'auto' }}>
              {hasTopology ? <PyramidHierarchy /> : <TopologyEmptyState connectionMode={connectionMode} compact />}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

function TopologyEmptyState({ connectionMode, compact = false }) {
  const offline = connectionMode === 'mock' || connectionMode === 'connecting'
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        padding: 24,
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          border: '1px solid #e2e5ea',
          background: '#f4f6f8',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#9aa1ad',
          fontFamily: "'DM Mono', monospace",
          fontSize: 18,
        }}
      >
        ⬡
      </div>
      <div style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 600, fontSize: 14 }}>
        {offline ? 'Backend offline — no live topology' : 'Waiting for the first graph snapshot…'}
      </div>
      {!compact && (
        <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 11, lineHeight: 1.7, maxWidth: 320 }}>
          Start the FastAPI backend to load the configured 10-host topology.
          Run Mininet or press <strong style={{ color: '#3b56d9' }}>Simulate</strong> in the top bar to see live
          traffic and threat vectors overlaid on the star.
        </p>
      )}
    </div>
  )
}
