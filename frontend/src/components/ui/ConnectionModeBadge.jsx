// [Windows] GraphSentinel — Susheep
// ui/ConnectionModeBadge — LIVE / SIMULATING / MOCK / CONNECTING
// Safety-critical: operator must always know which mode they're looking at
import { motion } from 'framer-motion'

const MODES = {
  live: {
    label: 'LIVE',
    dot: '#2ECC8A',
    cls: 'badge-live',
    icon: '●',
    pulse: true,
  },
  simulating: {
    label: 'SIMULATION',
    dot: '#E8922A',
    cls: 'badge-sim',
    icon: '◆',
    pulse: true,
  },
  mock: {
    label: 'OFFLINE',
    dot: '#5A6480',
    cls: 'badge-mock',
    icon: '○',
    pulse: false,
  },
  connecting: {
    label: 'CONNECTING',
    dot: '#4F6EF7',
    cls: 'badge-connecting',
    icon: '◌',
    pulse: true,
  },
}

/**
 * ConnectionModeBadge — renders the current connection state with unambiguous visual cues.
 * Read directly from connectionMode store field — never inferred.
 * Safety-critical: operators must distinguish LIVE from SIMULATION at a glance.
 */
export default function ConnectionModeBadge({ mode, className = '' }) {
  const cfg = MODES[mode] ?? MODES.connecting

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider ${cfg.cls} ${className}`}
      role="status"
      aria-label={`Data source: ${cfg.label}`}
      aria-live="polite"
    >
      {cfg.pulse ? (
        <motion.span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: cfg.dot }}
          animate={{ opacity: [1, 0.3, 1], scale: [1, 1.3, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      ) : (
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-gs-muted"
          aria-hidden="true"
        />
      )}
      {cfg.label}
    </span>
  )
}
