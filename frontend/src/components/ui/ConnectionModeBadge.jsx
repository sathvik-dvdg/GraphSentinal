// [Windows] GraphSentinel — Susheep
// ui/ConnectionModeBadge — LIVE / SIMULATION / OFFLINE / CONNECTING, and the
// socket's reconnection states. What it says is decided in utils/connection.
// Safety-critical: operator must always know which mode they're looking at
import { motion } from 'framer-motion'
import { connectionDisplay } from '../../utils/connection'

const MODES = {
  live: {
    label: 'LIVE',
    dot: '#12a672',
    cls: 'badge-live',
    icon: '●',
    pulse: true,
  },
  simulating: {
    label: 'SIMULATION',
    dot: '#b7791f',
    cls: 'badge-sim',
    icon: '◆',
    pulse: true,
  },
  mock: {
    label: 'OFFLINE',
    dot: '#727a86',
    cls: 'badge-mock',
    icon: '○',
    pulse: false,
  },
  connecting: {
    label: 'CONNECTING',
    dot: '#3b56d9',
    cls: 'badge-connecting',
    icon: '◌',
    pulse: true,
  },
  // Socket reconnecting, during the fast retries.
  reconnecting: {
    dot: '#b7791f',
    cls: 'badge-sim',
    pulse: true,
  },
  // The backend was answering and has stopped; retrying on a backoff.
  lost: {
    dot: '#727a86',
    cls: 'badge-mock',
    pulse: false,
  },
  // REST is answering and the socket is not: current, by polling.
  polling: {
    dot: '#12a672',
    cls: 'badge-live',
    pulse: false,
  },
}

/**
 * ConnectionModeBadge — renders the current connection state with unambiguous visual cues.
 * Read directly from connectionMode store field — never inferred.
 * Safety-critical: operators must distinguish LIVE from SIMULATION at a glance.
 */
export default function ConnectionModeBadge({ mode, socketStatus = 'idle', className = '' }) {
  const display = connectionDisplay(mode, socketStatus)
  const cfg = { ...(MODES[display.key] ?? MODES.connecting), label: display.label }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider whitespace-nowrap ${cfg.cls} ${className}`}
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
