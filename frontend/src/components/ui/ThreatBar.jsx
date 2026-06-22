// [Windows] GraphSentinel — Susheep
// ui/ThreatBar — reusable threat score progress bar
import { motion } from 'framer-motion'

function getThreatColor(score) {
  if (score >= 0.75) return '#E03C3C' // gs-threat
  if (score >= 0.5)  return '#E8922A' // gs-warn
  return '#2ECC8A'                    // gs-heal
}

/**
 * ThreatBar — threat score as a labeled progress bar
 * Used in AlertPanel and NodeDetailPanel
 */
export default function ThreatBar({ score, delay = 0, showLabel = true, className = '' }) {
  const color = getThreatColor(score)
  const pct = Math.max(0, Math.min(100, score * 100))

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLabel && (
        <span className="text-[10px] text-gs-muted font-mono uppercase tracking-wider shrink-0 w-10">
          Threat
        </span>
      )}
      <div
        className="flex-1 bg-gs-border rounded-full overflow-hidden"
        style={{ height: 4 }}
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Threat score ${Math.round(pct)}%`}
      >
        <motion.div
          className="h-full rounded-full motion-functional"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, delay, ease: 'easeOut' }}
        />
      </div>
      <span
        className="text-[10px] font-mono tabular-nums shrink-0 w-9 text-right"
        style={{ color }}
      >
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}
