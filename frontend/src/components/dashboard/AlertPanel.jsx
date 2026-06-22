// [Windows] GraphSentinel — Susheep
// AlertPanel — redesigned with new token system
// ── All props and data bindings preserved verbatim ──
import { motion, AnimatePresence } from 'framer-motion'
import { SEVERITY_STYLES } from '../../constants/theme'
import { ShieldAlert } from 'lucide-react'
import SeverityBadge from '../ui/SeverityBadge'
import ThreatBar from '../ui/ThreatBar'

export default function AlertPanel({ alerts }) {
  return (
    <div className="gs-panel border-gs-threat/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-gs-border">
        <div className="flex items-center gap-2">
          <ShieldAlert size={13} className="text-gs-threat" aria-hidden="true" />
          <span className="text-gs-threat font-mono text-[11px] font-semibold tracking-widest uppercase">
            Threat Feed
          </span>
        </div>
        <span className="text-gs-muted text-[10px] font-mono tabular-nums">
          {alerts.length} event{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-auto p-2 space-y-1.5" role="log" aria-label="Threat alerts">
        <AnimatePresence initial={false}>
          {alerts.map((alert, i) => {
            // ── Original style mapping — untouched ──
            const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info
            const accentClass =
              alert.severity === 'critical' ? 'alert-card-critical' :
              alert.severity === 'warning'  ? 'alert-card-warning' : 'alert-card-info'

            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: 16, scale: 0.97 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.25, delay: i * 0.02 }}
                className={`relative ${accentClass} rounded-lg overflow-hidden cursor-default transition-all duration-150 hover:brightness-105`}
                style={{
                  background: '#1E1E1E',
                  border: '1px solid #262D3F',
                  borderLeftWidth: '2px',
                }}
              >
                <div className="p-2.5">
                  {/* Row 1: severity badge + attack type + time */}
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    {/* Color + icon + text — not color alone */}
                    <SeverityBadge severity={alert.severity} />
                    <span
                      className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
                      style={{
                        color: style.dot,
                        borderColor: `${style.dot}25`,
                        background: `${style.dot}08`,
                      }}
                    >
                      {alert.attack_type}
                    </span>
                    <span className="text-gs-muted text-[10px] ml-auto font-mono tabular-nums">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Source IP */}
                  <div className="text-gs-text text-[11px] font-mono font-semibold mb-2 tabular-nums">
                    {alert.source_ip}
                  </div>

                  {/* Threat score bar — accessible */}
                  <ThreatBar score={alert.threat_score} delay={i * 0.04} />

                  {/* Blockchain hash */}
                  {alert.blockchain_tx && (
                    <div className="mt-2 flex items-center gap-1.5 text-[10px] font-mono">
                      <span className="text-gs-chain" aria-hidden="true">⛓</span>
                      <span className="text-gs-chain font-mono tabular-nums">
                        {alert.blockchain_tx.slice(0, 10)}…
                      </span>
                      <span className="text-gs-heal ml-1">✓ on-chain</span>
                    </div>
                  )}

                  {/* Isolation tag */}
                  {alert.is_blocked && (
                    <div className="mt-1.5 flex items-center gap-1.5 text-[10px] font-mono">
                      <span className="text-gs-accent" aria-hidden="true">⬡</span>
                      <span className="text-gs-accent tracking-wider">NODE ISOLATED</span>
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>

        {/* Empty state */}
        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="w-10 h-10 rounded-xl bg-gs-heal-soft border border-gs-heal/20 flex items-center justify-center mb-3">
              <ShieldAlert size={18} className="text-gs-heal/60" aria-hidden="true" />
            </div>
            <p className="text-gs-muted text-[11px] font-mono">No threats detected.</p>
            <p className="text-gs-faint text-[10px] font-mono mt-1">Network perimeter secure.</p>
          </div>
        )}
      </div>
    </div>
  )
}
