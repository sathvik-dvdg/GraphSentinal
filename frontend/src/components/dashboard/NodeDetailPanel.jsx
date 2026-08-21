// [Windows] GraphSentinel — Susheep
// NodeDetailPanel — redesigned with new token system + accessibility
// ── All props, data bindings, and handlers preserved verbatim ──
import { motion } from 'framer-motion'
import { X, Shield, ShieldOff } from 'lucide-react'
import StatusBadge from '../ui/StatusBadge'
import ThreatBar from '../ui/ThreatBar'

export default function NodeDetailPanel({ node, onClose, onBlock }) {
  if (!node) return null

  // ── Original helper — untouched ──
  const formatBytes = (b) => {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB'
    if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB'
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB'
    return b + ' B'
  }

  return (
    <>
      {/* Backdrop — onClick original handler preserved */}
      <div
        className="fixed inset-0 z-30 bg-black/50 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel — original spring animation preserved */}
      <motion.div
        initial={{ x: 300, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 300, opacity: 0 }}
        transition={{ type: 'spring', damping: 26, stiffness: 220 }}
        className="fixed top-0 right-0 w-72 h-full z-40 overflow-auto"
        style={{
          background: '#1E1E1E',
          borderLeft: '1px solid #262D3F',
          boxShadow: '-16px 0 48px rgba(0,0,0,0.6)',
        }}
        role="dialog"
        aria-label={`Node details: ${node.label}`}
        aria-modal="true"
      >
        {/* Top accent line */}
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, transparent, #4F6EF740, transparent)' }} />

        <div className="p-5">
          {/* Close button — onClick original handler preserved */}
          <button
            id="node-detail-close"
            onClick={onClose}
            className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-lg border border-gs-border text-gs-muted hover:text-gs-text hover:border-gs-muted transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-accent"
            aria-label="Close node detail panel"
          >
            <X size={14} aria-hidden="true" />
          </button>

          {/* Header */}
          <div className="mb-5 pr-8">
            <p className="text-[9px] text-gs-faint font-mono uppercase tracking-widest mb-1">
              Node Details
            </p>
            <h2 className="text-sm font-heading font-semibold text-gs-text mb-2">
              {node.label}
            </h2>
            {/* Status — color + icon + text (accessibility) */}
            <StatusBadge status={node.status} size="sm" />
          </div>

          {/* Fields */}
          <div className="space-y-3.5">
            <Field label="IP Address" value={node.id} mono />
            <ThreatBar score={node.threat_score} showLabel />
            <Field label="Connections" value={node.connections} mono />
            <Field label="Total Bytes"  value={formatBytes(node.bytes_total)} mono />
            {node.attack_type && (
              <div>
                <span className="text-[9px] text-gs-faint font-mono uppercase tracking-widest block mb-1.5">
                  Attack Type
                </span>
                <span
                  className="text-[11px] font-mono px-2 py-0.5 rounded-md border"
                  style={{ color: '#E03C3C', borderColor: '#E03C3C25', background: '#E03C3C08' }}
                >
                  {node.attack_type}
                </span>
              </div>
            )}
            <div>
              <span className="text-[9px] text-gs-faint font-mono uppercase tracking-widest block mb-1.5">
                Status
              </span>
              <span
                className="text-[11px] font-mono"
                style={{ color: node.is_blocked ? '#4F6EF7' : '#2ECC8A' }}
              >
                {node.is_blocked
                  ? '⬡ Isolated — blocked'
                  : '● Active — not blocked'}
              </span>
            </div>
            {/* Error.md #9: baseline-topology nodes vs. nodes that actually
                appeared in a flow are otherwise indistinguishable in the UI */}
            {node.source && (
              <div>
                <span className="text-[9px] text-gs-faint font-mono uppercase tracking-widest block mb-1.5">
                  Data Source
                </span>
                <span
                  className="text-[11px] font-mono"
                  style={{ color: node.source === 'observed' ? '#2ECC8A' : '#5A6480' }}
                  title={node.source === 'observed'
                    ? 'This host appeared in real captured traffic'
                    : 'Configured topology baseline — no traffic seen from this host yet'}
                >
                  {node.source === 'observed' ? '◆ Observed traffic' : '○ Configured (no traffic yet)'}
                </span>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="h-px bg-gs-border my-5" />

          {/* Action buttons — original onClick handlers preserved */}
          <div className="space-y-2">
            {!node.is_blocked ? (
              <button
                id="node-detail-block"
                onClick={() => onBlock && onBlock(node.id, 'block')}
                className="tac-btn w-full flex items-center justify-center gap-2 py-2.5 bg-gs-threat-soft text-gs-threat border border-gs-threat/25 rounded-lg font-mono text-[11px] uppercase tracking-wider hover:bg-gs-threat/15 hover:border-gs-threat/50 transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-threat"
              >
                <ShieldOff size={12} aria-hidden="true" />
                Block Node
              </button>
            ) : (
              <button
                id="node-detail-unblock"
                onClick={() => onBlock && onBlock(node.id, 'unblock')}
                className="tac-btn w-full flex items-center justify-center gap-2 py-2.5 bg-gs-heal-soft text-gs-heal border border-gs-heal/25 rounded-lg font-mono text-[11px] uppercase tracking-wider hover:bg-gs-heal/15 hover:border-gs-heal/50 transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-heal"
              >
                <Shield size={12} aria-hidden="true" />
                Unblock Node
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </>
  )
}

/* ── Field sub-component ── */
function Field({ label, value, mono = false }) {
  return (
    <div>
      <span className="text-[9px] text-gs-faint font-mono uppercase tracking-widest block mb-1">
        {label}
      </span>
      <span className={`text-[12px] text-gs-text ${mono ? 'font-mono tabular-nums' : 'font-body'}`}>
        {value}
      </span>
    </div>
  )
}
