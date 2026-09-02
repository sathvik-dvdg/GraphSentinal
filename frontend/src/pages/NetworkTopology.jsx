// [Windows] GraphSentinel — Susheep
// NetworkTopology — 3D/2D graph + Pyramid hierarchy split view
import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import useGraphStore from '../store/useGraphStore'
import NetworkGraph3D from '../components/dashboard/NetworkGraph3D'
import NetworkGraph2D from '../components/dashboard/NetworkGraph2D'
import PyramidHierarchy from '../components/pyramid/PyramidHierarchy'
import ConnectionModeBadge from '../components/ui/ConnectionModeBadge'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'

const VIEW_MODES = [
  { id: 'split',   label: 'Split View' },
  { id: '3d',      label: '3D Graph' },
  { id: '2d',      label: '2D Graph' },
  { id: 'pyramid', label: 'Org Pyramid' },
]

export default function NetworkTopology() {
  const [viewMode, setViewMode] = useState('split')
  const { graphData, healingNodeId, connectionMode, setSelectedNode, dataErrors } = useGraphStore()

  const show3D = viewMode === '3d' || viewMode === 'split'
  const show2D = viewMode === '2d'
  const showPyramid = viewMode === 'pyramid' || viewMode === 'split'
  const isSplit = viewMode === 'split'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 108px)' }}>
      {/* Header + controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Network Topology
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <p style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
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
            background: '#1E1E1E',
            border: '1px solid rgba(255,255,255,0.08)',
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
                color: viewMode === m.id ? '#4F6EF7' : '#5A6480',
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
                background: 'rgba(20,20,20,0.8)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '4px 10px',
              }}
            >
              <span style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                {show2D ? '2D Network Graph' : '3D Network Graph'}
              </span>
              <ConnectionModeBadge mode={connectionMode} />
            </div>

            {show2D ? (
              <NetworkGraph2D
                graphData={graphData}
                healingNodeId={healingNodeId}
                onNodeClick={(node) => setSelectedNode(node)}
              />
            ) : (
              <NetworkGraph3D
                graphData={graphData}
                healingNodeId={healingNodeId}
                onNodeClick={(node) => setSelectedNode(node)}
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
                background: 'rgba(23,27,38,0.95)',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
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
              <PyramidHierarchy />
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
