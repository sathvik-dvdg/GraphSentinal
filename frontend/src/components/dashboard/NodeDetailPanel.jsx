// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { STATUS_COLORS } from '../../constants/theme'

export default function NodeDetailPanel({ node, onClose, onBlock }) {
  if (!node) return null

  const formatBytes = (b) => {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB'
    if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB'
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB'
    return b + ' B'
  }

  return (
    <>
      {/* Backdrop — clicking outside closes the panel */}
      <div
        className="fixed inset-0 z-30 bg-black/40"
        onClick={onClose}
      />
      <motion.div
        initial={{ x: 320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 320, opacity: 0 }}
        transition={{ type: 'spring', damping: 25 }}
        className="fixed top-0 right-0 w-72 h-full bg-gs-card border-l border-gs-border z-40 p-4 overflow-auto"
      >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
      >
        <X size={16} />
      </button>

      {/* Header */}
      <h3 className="text-xs text-gray-500 font-mono uppercase tracking-wider mb-1">
        Node Details
      </h3>
      <h2 className="text-lg font-bold text-white font-mono mb-4">{node.label}</h2>

      {/* Fields */}
      <div className="space-y-3">
        <Field label="IP Address" value={node.id} />
        <Field
          label="Status"
          value={node.status.toUpperCase()}
          color={STATUS_COLORS[node.status]}
        />
        <div>
          <span className="text-xs text-gray-500 font-mono block mb-1">Threat Score</span>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-800 rounded-full h-2">
              <motion.div
                className="h-2 rounded-full"
                style={{
                  backgroundColor:
                    node.threat_score >= 0.75 ? '#ff4444' : node.threat_score >= 0.5 ? '#ffaa00' : '#00ff88',
                }}
                initial={{ width: 0 }}
                animate={{ width: `${node.threat_score * 100}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>
            <span className="text-sm font-bold font-mono text-white">
              {(node.threat_score * 100).toFixed(1)}%
            </span>
          </div>
        </div>
        <Field label="Connections" value={node.connections} />
        <Field label="Total Bytes" value={formatBytes(node.bytes_total)} />
        {node.attack_type && (
          <Field label="Attack Type" value={node.attack_type} color="#ff4444" />
        )}
        <Field label="Blocked" value={node.is_blocked ? 'Yes' : 'No'} color={node.is_blocked ? '#0066ff' : '#00ff88'} />
      </div>

      {/* Action buttons */}
      <div className="mt-6 space-y-2">
        {!node.is_blocked ? (
          <button
            onClick={() => onBlock && onBlock(node.id, 'block')}
            className="w-full py-2 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg font-mono text-xs
                       hover:bg-red-500/30 transition-all"
          >
            🔒 BLOCK NODE
          </button>
        ) : (
          <button
            onClick={() => onBlock && onBlock(node.id, 'unblock')}
            className="w-full py-2 bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg font-mono text-xs
                       hover:bg-green-500/30 transition-all"
          >
            🔓 UNBLOCK NODE
          </button>
        )}
      </div>
    </motion.div>
    </>
  )
}

function Field({ label, value, color }) {
  return (
    <div>
      <span className="text-xs text-gray-500 font-mono block mb-0.5">{label}</span>
      <span className="text-sm font-mono" style={{ color: color || '#e2e8f0' }}>
        {value}
      </span>
    </div>
  )
}
