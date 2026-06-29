// [Windows] GraphSentinel — Susheep
// NodeInspector — slide-in panel showing details for a clicked pyramid node
import { useNavigate } from 'react-router-dom'
import { X, Shield, AlertTriangle, Zap, ExternalLink } from 'lucide-react'
import { LEVEL_LABELS, STATUS_COLORS } from './pyramidConfig'
import useGraphStore from '../../store/useGraphStore'

export default function NodeInspector({ node, onClose }) {
  const navigate = useNavigate()
  const chainTxs = useGraphStore((s) => s.chainTxs)
  const updateNodeStatus = useGraphStore((s) => s.updateNodeStatus)
  const graphData = useGraphStore((s) => s.graphData)

  if (!node) return null

  const colors = STATUS_COLORS[node.status] || STATUS_COLORS.normal
  const levelLabel = LEVEL_LABELS[node.level] ?? `L${node.level}`

  // Last 5 blockchain records for this node IP
  const nodeChainEvents = chainTxs
    .filter((tx) => tx.source_ip === node.ip)
    .slice(0, 5)

  const realNode = graphData?.nodes?.find(n => n.id === node.ip || n.ip === node.ip)
  const anomalyScore = realNode?.threat_score !== undefined 
    ? Math.floor(realNode.threat_score * 100) 
    : node.anomalyScore ?? 0

  const isIsolated = node.status === 'isolated'

  const handleToggleIsolate = () => {
    if (isIsolated) {
      updateNodeStatus(node.id || node.ip, 'normal')
    } else {
      updateNodeStatus(node.id || node.ip, 'isolated')
    }
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        height: '100%',
        width: 300,
        background: '#141418',
        borderLeft: '1px solid rgba(255,255,255,0.08)',
        boxShadow: '-12px 0 40px rgba(0,0,0,0.5)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 20,
        animation: 'slideInRight 250ms ease',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span
              style={{
                color: '#E8EDF5',
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {node.label}
            </span>
            {/* Status badge */}
            {node.status !== 'normal' && (
              <span
                style={{
                  background: colors.border,
                  color: '#fff',
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontFamily: "'DM Mono', monospace",
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                }}
              >
                {node.status}
              </span>
            )}
          </div>
          <div style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
            {node.ip}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: '1px solid rgba(255,255,255,0.08)',
            color: '#5A6480',
            cursor: 'pointer',
            borderRadius: 6,
            padding: 5,
            display: 'flex',
          }}
        >
          <X size={14} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {/* Trust level badge */}
        <div style={{ marginBottom: 16 }}>
          <Label>Trust Level</Label>
          <span
            style={{
              display: 'inline-block',
              background: 'rgba(79,110,247,0.12)',
              border: '1px solid rgba(79,110,247,0.3)',
              color: '#4F6EF7',
              fontSize: 11,
              fontFamily: "'DM Mono', monospace",
              fontWeight: 600,
              padding: '3px 10px',
              borderRadius: 6,
              letterSpacing: '0.06em',
            }}
          >
            {levelLabel}
          </span>
        </div>

        {/* Sublabel */}
        <div style={{ marginBottom: 16 }}>
          <Label>Department</Label>
          <Value>{node.sublabel}</Value>
        </div>

        {/* Status */}
        <div style={{ marginBottom: 16 }}>
          <Label>Status</Label>
          <span style={{ color: colors.text, fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {node.status}
          </span>
        </div>

        {/* Anomaly score */}
        <div style={{ marginBottom: 20 }}>
          <Label>Anomaly Score (GraphSAGE)</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                flex: 1,
                height: 6,
                background: 'rgba(255,255,255,0.06)',
                borderRadius: 99,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${anomalyScore}%`,
                  background: anomalyScore > 75 ? '#E03C3C' : anomalyScore > 50 ? '#E8922A' : '#4F6EF7',
                  borderRadius: 99,
                  transition: 'width 600ms ease',
                }}
              />
            </div>
            <span style={{ color: '#8A95B0', fontSize: 12, fontFamily: "'DM Mono', monospace", minWidth: 32 }}>
              {anomalyScore}%
            </span>
          </div>
        </div>

        {/* Blockchain events */}
        <div style={{ marginBottom: 20 }}>
          <Label>Blockchain Events ({nodeChainEvents.length})</Label>
          {nodeChainEvents.length === 0 ? (
            <span style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
              No on-chain records for this node
            </span>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {nodeChainEvents.map((tx) => (
                <div
                  key={tx.id}
                  style={{
                    background: 'rgba(139,92,246,0.08)',
                    border: '1px solid rgba(139,92,246,0.15)',
                    borderRadius: 6,
                    padding: '6px 10px',
                  }}
                >
                  <div style={{ color: '#8B5CF6', fontSize: 10, fontFamily: "'DM Mono', monospace", marginBottom: 2 }}>
                    {tx.tx_hash?.slice(0, 14)}…
                  </div>
                  <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                    {tx.attack_type} · #{tx.block_number}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div
        style={{
          padding: 16,
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <button
          onClick={handleToggleIsolate}
          style={actionBtnStyle(isIsolated ? '#2ECC8A' : '#E03C3C')}
        >
          <Shield size={12} />
          {isIsolated ? 'Deisolate Node' : 'Isolate Node'}
        </button>
        <button
          onClick={() => navigate('/forensics')}
          style={actionBtnStyle('#4F6EF7')}
        >
          <ExternalLink size={12} />
          Open Forensics
        </button>
        <button
          onClick={() => navigate('/network')}
          style={actionBtnStyle('#2ECC8A')}
        >
          <Zap size={12} />
          View in 3D Graph
        </button>
      </div>
    </div>
  )
}

function Label({ children }) {
  return (
    <div style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
      {children}
    </div>
  )
}

function Value({ children }) {
  return (
    <div style={{ color: '#8A95B0', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
      {children}
    </div>
  )
}

function actionBtnStyle(color) {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    borderRadius: 6,
    border: `1px solid ${color}30`,
    background: `${color}10`,
    color,
    fontSize: 12,
    fontFamily: "'DM Mono', monospace",
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 150ms',
    letterSpacing: '0.04em',
  }
}
