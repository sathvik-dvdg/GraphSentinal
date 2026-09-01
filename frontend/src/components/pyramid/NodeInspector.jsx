// [Windows] GraphSentinel — Susheep
// NodeInspector — slide-in panel showing details for a clicked pyramid node
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, Shield, AlertTriangle, Zap, ExternalLink } from 'lucide-react'
import { LEVEL_LABELS, STATUS_COLORS } from './pyramidConfig'
import useGraphStore from '../../store/useGraphStore'
import { blockIP, getGraph, getBlocked, getStats } from '../../services/api'

export default function NodeInspector({ node, onClose }) {
  const navigate = useNavigate()
  const chainTxs = useGraphStore((s) => s.chainTxs)
  const graphData = useGraphStore((s) => s.graphData)
  const setGraphData = useGraphStore((s) => s.setGraphData)
  const setBlockedIPs = useGraphStore((s) => s.setBlockedIPs)
  const updateStats = useGraphStore((s) => s.updateStats)
  const [isToggling, setIsToggling] = useState(false)

  if (!node) return null

  // Last 5 blockchain records for this node IP
  const nodeChainEvents = chainTxs
    .filter((tx) => tx.source_ip === node.ip)
    .slice(0, 5)

  const realNode = graphData?.nodes?.find(n => n.id === node.ip || n.ip === node.ip)
  const anomalyScore = realNode?.threat_score !== undefined
    ? Math.floor(realNode.threat_score * 100)
    : node.anomalyScore ?? 0

  // `node` is a snapshot from whenever the panel was opened. Prefer the live
  // graphData status so isolate/deisolate (and any other backend-driven
  // change) is reflected immediately instead of looking reverted-but-not.
  const displayStatus = realNode?.status ?? node.status
  const colors = STATUS_COLORS[displayStatus] || STATUS_COLORS.normal
  const levelLabel = LEVEL_LABELS[node.level] ?? `L${node.level}`

  // realNode.is_blocked is the backend-authoritative flag. Fall back to the
  // UI-derived pyramid status only if this IP isn't in the live graph yet.
  const isIsolated = realNode ? realNode.is_blocked : node.status === 'isolated'

  // This used to call the store's local-only updateNodeStatus(), which never
  // touched the backend — it optimistically flipped graphData.node.status in
  // place, then the next 10s poll's setGraphData() silently overwrote it with
  // the (unchanged) real state, with no indication to the operator that
  // nothing was actually enforced. Now it calls the same real /api/v1/block
  // endpoint + immediate refresh that NodeDetailPanel's Block button uses
  // (see AppShell.jsx handleBlock, Error.md #23).
  const handleToggleIsolate = async () => {
    const ip = node.ip || node.id
    if (!ip || isToggling) return
    setIsToggling(true)
    try {
      await blockIP(ip, isIsolated ? 'unblock' : 'block')
      const [graphRes, blockedRes, statsRes] = await Promise.allSettled([
        getGraph(), getBlocked(), getStats(),
      ])
      if (graphRes.status === 'fulfilled') setGraphData(graphRes.value)
      if (blockedRes.status === 'fulfilled') setBlockedIPs(blockedRes.value.blocked_ips)
      if (statsRes.status === 'fulfilled') updateStats(statsRes.value)
    } catch (err) {
      console.error(`[NodeInspector] Failed to ${isIsolated ? 'unblock' : 'block'} ${ip} — backend rejected or is unreachable:`, err)
    } finally {
      setIsToggling(false)
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
        background: '#ffffff',
        borderLeft: '1px solid rgba(17,20,26,0.10)',
        boxShadow: '-12px 0 40px rgba(17,20,26,0.10)',
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
          borderBottom: '1px solid rgba(17,20,26,0.08)',
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
                color: '#1b1f27',
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {node.label}
            </span>
            {/* Status badge */}
            {displayStatus !== 'normal' && (
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
                {displayStatus}
              </span>
            )}
          </div>
          <div style={{ color: '#727a86', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
            {node.ip}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: '1px solid rgba(17,20,26,0.10)',
            color: '#727a86',
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
              color: '#3b56d9',
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
            {displayStatus}
          </span>
        </div>

        {/* Error.md #9: baseline-topology nodes vs. nodes that actually
            appeared in a flow are otherwise indistinguishable in the UI */}
        {realNode?.source && (
          <div style={{ marginBottom: 16 }}>
            <Label>Data Source</Label>
            <span
              style={{ color: realNode.source === 'observed' ? '#12a672' : '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}
              title={realNode.source === 'observed'
                ? 'This host appeared in real captured traffic'
                : 'Configured topology baseline — no traffic seen from this host yet'}
            >
              {realNode.source === 'observed' ? '◆ Observed traffic' : '○ Configured (no traffic yet)'}
            </span>
          </div>
        )}

        {/* Anomaly score */}
        <div style={{ marginBottom: 20 }}>
          <Label>Anomaly Score (GraphSAGE)</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                flex: 1,
                height: 6,
                background: 'rgba(17,20,26,0.08)',
                borderRadius: 99,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${anomalyScore}%`,
                  background: anomalyScore > 75 ? '#E03C3C' : anomalyScore > 50 ? '#b7791f' : '#3b56d9',
                  borderRadius: 99,
                  transition: 'width 600ms ease',
                }}
              />
            </div>
            <span style={{ color: '#5a616e', fontSize: 12, fontFamily: "'DM Mono', monospace", minWidth: 32 }}>
              {anomalyScore}%
            </span>
          </div>
        </div>

        {/* Blockchain events */}
        <div style={{ marginBottom: 20 }}>
          <Label>Blockchain Events ({nodeChainEvents.length})</Label>
          {nodeChainEvents.length === 0 ? (
            <span style={{ color: '#9aa1ad', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
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
                  <div style={{ color: '#7c3aed', fontSize: 10, fontFamily: "'DM Mono', monospace", marginBottom: 2 }}>
                    {tx.tx_hash?.slice(0, 14)}…
                  </div>
                  <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
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
          borderTop: '1px solid rgba(17,20,26,0.08)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <button
          onClick={handleToggleIsolate}
          disabled={isToggling}
          style={{ ...actionBtnStyle(isIsolated ? '#12a672' : '#E03C3C'), opacity: isToggling ? 0.6 : 1, cursor: isToggling ? 'default' : 'pointer' }}
        >
          <Shield size={12} />
          {isToggling ? 'Working…' : isIsolated ? 'Deisolate Node' : 'Isolate Node'}
        </button>
        <button
          onClick={() => navigate('/forensics')}
          style={actionBtnStyle('#3b56d9')}
        >
          <ExternalLink size={12} />
          Open Forensics
        </button>
        <button
          onClick={() => navigate('/network')}
          style={actionBtnStyle('#12a672')}
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
    <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
      {children}
    </div>
  )
}

function Value({ children }) {
  return (
    <div style={{ color: '#5a616e', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
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
