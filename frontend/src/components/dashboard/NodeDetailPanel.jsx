// [Windows] GraphSentinel — Susheep
// ── All props, data bindings, and handlers preserved verbatim ──
import { motion } from 'framer-motion'
import { X, Shield, ShieldOff, Wifi, WifiOff } from 'lucide-react'
import { STATUS_COLORS } from '../../constants/theme'

export default function NodeDetailPanel({ node, onClose, onBlock }) {
  if (!node) return null

  // ── Original helper — untouched ──
  const formatBytes = (b) => {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB'
    if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB'
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB'
    return b + ' B'
  }

  const threatColor =
    node.threat_score >= 0.75 ? '#f43f5e' : node.threat_score >= 0.5 ? '#fbbf24' : '#34d399'

  const statusRing = {
    normal:     'border-emerald-500/30 bg-emerald-500/5 text-emerald-400',
    suspicious: 'border-amber-500/30 bg-amber-500/5 text-amber-400',
    malicious:  'border-rose-500/30 bg-rose-500/5 text-rose-400',
    blocked:    'border-cyan-500/30 bg-cyan-500/5 text-cyan-400',
  }

  return (
    <>
      {/* Backdrop — onClick original handler preserved */}
      <div className="fixed inset-0 z-30 bg-black/60 backdrop-blur-[2px]" onClick={onClose} />

      {/* Panel — original spring animation preserved */}
      <motion.div
        initial={{ x: 320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 320, opacity: 0 }}
        transition={{ type: 'spring', damping: 25 }}
        className="fixed top-0 right-0 w-72 h-full z-40 overflow-auto"
        style={{
          background: 'rgba(9,14,31,0.97)',
          backdropFilter: 'blur(20px)',
          borderLeft: '1px solid rgba(30,41,59,0.8)',
          boxShadow: '-20px 0 60px rgba(0,0,0,0.7)',
        }}
      >
        {/* Top accent line */}
        <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

        <div className="p-5">
          {/* Close button — onClick original handler preserved */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-lg border border-slate-800 text-slate-500 hover:text-white hover:border-slate-600 transition-all duration-200"
          >
            <X size={14} />
          </button>

          {/* Header */}
          <div className="mb-5">
            <p className="text-[10px] text-slate-600 font-mono uppercase tracking-widest mb-1">
              Node Details
            </p>
            <h2 className="text-base font-bold text-white font-mono">{node.label}</h2>
          </div>

          {/* Status badge */}
          <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border mb-5 ${statusRing[node.status] || 'border-slate-700 bg-slate-800/30 text-slate-400'}`}>
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: STATUS_COLORS[node.status] }}
            />
            <span className="text-xs font-mono font-bold tracking-wider">
              {node.status?.toUpperCase()}
            </span>
          </div>

          {/* Fields */}
          <div className="space-y-3.5">
            <Field label="IP Address" value={node.id} color="#94a3b8" />

            {/* Threat score — original animate values preserved */}
            <div>
              <span className="text-[10px] text-slate-600 font-mono uppercase tracking-widest block mb-1.5">
                Threat Score
              </span>
              <div className="flex items-center gap-2.5">
                <div className="flex-1 bg-slate-800/60 rounded-full h-2 overflow-hidden">
                  <motion.div
                    className="h-2 rounded-full"
                    style={{
                      backgroundColor: threatColor,
                      boxShadow: `0 0 8px ${threatColor}60`,
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${node.threat_score * 100}%` }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
                <span className="text-sm font-bold font-mono tabular-nums" style={{ color: threatColor }}>
                  {(node.threat_score * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <Field label="Connections" value={node.connections} />
            <Field label="Total Bytes"  value={formatBytes(node.bytes_total)} />
            {node.attack_type && (
              <Field label="Attack Type" value={node.attack_type} color="#f43f5e" />
            )}
            <Field
              label="Blocked"
              value={node.is_blocked ? 'YES — Isolated' : 'NO — Active'}
              color={node.is_blocked ? '#06b6d4' : '#34d399'}
            />
          </div>

          {/* Divider */}
          <div className="h-px bg-slate-800/60 my-5" />

          {/* Action buttons — original onClick handlers preserved */}
          <div className="space-y-2.5">
            {!node.is_blocked ? (
              <button
                onClick={() => onBlock && onBlock(node.id, 'block')}
                className="tac-btn w-full flex items-center justify-center gap-2 py-2.5 bg-rose-500/10 text-rose-400 border border-rose-500/30 rounded-lg font-mono text-xs uppercase tracking-wider hover:bg-rose-500/20 hover:border-rose-500/50 hover:shadow-glow-rose transition-all duration-200"
              >
                <ShieldOff size={13} />
                BLOCK NODE
              </button>
            ) : (
              <button
                onClick={() => onBlock && onBlock(node.id, 'unblock')}
                className="tac-btn w-full flex items-center justify-center gap-2 py-2.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-lg font-mono text-xs uppercase tracking-wider hover:bg-emerald-500/20 hover:border-emerald-500/50 hover:shadow-glow-emerald transition-all duration-200"
              >
                <Shield size={13} />
                UNBLOCK NODE
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </>
  )
}

/* ── Field sub-component ── */
function Field({ label, value, color }) {
  return (
    <div>
      <span className="text-[10px] text-slate-600 font-mono uppercase tracking-widest block mb-0.5">
        {label}
      </span>
      <span className="text-sm font-mono" style={{ color: color || '#e2e8f0' }}>
        {value}
      </span>
    </div>
  )
}
