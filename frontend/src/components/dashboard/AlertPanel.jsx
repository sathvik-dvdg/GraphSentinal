// [Windows] GraphSentinel — Susheep
// ── All props and data bindings preserved verbatim ──
import { motion, AnimatePresence } from 'framer-motion'
import { SEVERITY_STYLES } from '../../constants/theme'
import { ShieldAlert } from 'lucide-react'

export default function AlertPanel({ alerts }) {
  return (
    <div className="glass-card border-error/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-outline-variant/30">
        <div className="flex items-center gap-2">
          <ShieldAlert size={13} className="text-error" />
          <span className="text-error font-mono text-xs font-bold tracking-widest uppercase text-glow-error">
            Threat Feed
          </span>
        </div>
        <span className="text-on-surface-variant text-[10px] font-mono tabular-nums">
          {alerts.length} event{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-auto p-2.5 space-y-2">
        <AnimatePresence initial={false}>
          {alerts.map((alert, i) => {
            // ── Original style mapping — untouched ──
            const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info
            const accentClass =
              alert.severity === 'critical'
                ? 'alert-card-critical'
                : alert.severity === 'warning'
                ? 'alert-card-warning'
                : 'alert-card-info'

            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: 20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3, delay: i * 0.03 }}
                className={`relative ${accentClass} rounded-r-lg rounded-bl-sm overflow-hidden transition-all duration-200 hover:brightness-110 cursor-default`}
                style={{ background: 'rgba(5, 20, 36, 0.4)', border: '1px solid rgba(119, 141, 169, 0.2)', borderLeftWidth: '2px' }}
              >
                <div className="p-2.5">
                  {/* Row 1: dot + badge + time */}
                  <div className="flex items-center gap-2 mb-2">
                    <motion.div
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: style.dot }}
                      animate={
                        alert.severity === 'critical'
                          ? { scale: [1, 1.6, 1], opacity: [1, 0.3, 1] }
                          : {}
                      }
                      transition={{ duration: 1.2, repeat: Infinity }}
                    />
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold font-mono border ${
                      alert.severity === 'critical'
                        ? 'bg-error/15 text-error border-error/25'
                        : alert.severity === 'warning'
                        ? 'bg-primary-fixed/15 text-primary-fixed border-primary-fixed/25'
                        : 'bg-primary-container/15 text-primary-container border-primary-container/25'
                    }`}>
                      {alert.attack_type}
                    </span>
                    <span className="text-on-surface-variant text-[10px] ml-auto font-mono tabular-nums">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Source IP */}
                  <div className="text-on-surface text-xs font-mono font-bold mb-2">
                    {alert.source_ip}
                  </div>

                  {/* Threat score bar */}
                  <div className="flex items-center gap-2">
                    <span className="text-on-surface-variant text-[10px] font-mono uppercase tracking-wider shrink-0">Threat</span>
                    <div className="flex-1 bg-outline-variant/30 rounded-full h-1 overflow-hidden">
                      <motion.div
                        className="h-1 rounded-full"
                        style={{ backgroundColor: style.dot }}
                        initial={{ width: 0 }}
                        animate={{ width: `${alert.threat_score * 100}%` }}
                        transition={{ duration: 0.8, delay: i * 0.05 }}
                      />
                    </div>
                    <span className="text-[10px] font-mono tabular-nums shrink-0" style={{ color: style.dot }}>
                      {(alert.threat_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Blockchain hash */}
                  {alert.blockchain_tx && (
                    <div className="mt-2 flex items-center gap-1.5 text-[10px] font-mono">
                      <span className="text-purple-400">⛓</span>
                      <span className="text-purple-400 font-mono">{alert.blockchain_tx.slice(0, 10)}…</span>
                      <span className="text-primary-container ml-1">✓ on-chain</span>
                    </div>
                  )}

                  {/* Isolation tag */}
                  {alert.is_blocked && (
                    <div className="mt-1.5 flex items-center gap-1.5 text-[10px] font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-container shrink-0" />
                      <span className="text-primary-container tracking-wider">NODE ISOLATED</span>
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>

        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="w-10 h-10 rounded-xl bg-primary-container/5 border border-primary-container/20 flex items-center justify-center mb-3">
              <ShieldAlert size={18} className="text-primary-container/50" />
            </div>
            <p className="text-on-surface-variant text-xs font-mono">No threats detected.</p>
            <p className="text-on-surface-variant/70 text-[10px] font-mono mt-1">Network perimeter secure.</p>
          </div>
        )}
      </div>
    </div>
  )
}
