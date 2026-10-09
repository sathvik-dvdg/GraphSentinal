// [Windows] GraphSentinel — Susheep
// ui/ConnectionModeBadge — LIVE / OFFLINE / CONNECTING, and the
// socket's reconnection states. What it says is decided in utils/connection.
// Safety-critical: operator must always know which mode they're looking at
import StatusPill from './StatusPill'
import { connectionDisplay } from '../../utils/connection'
import { GS } from '../../constants/colors'

const TONE = { 'badge-live': 'live', 'badge-sim': 'warn', 'badge-mock': 'muted', 'badge-connecting': 'neutral' }

const MODES = {
  live: {
    label: 'Live',
    dot: GS.success,
    cls: 'badge-live',
    icon: '●',
    pulse: true,
  },
  mock: {
    label: 'Offline',
    dot: GS.textSubtle,
    cls: 'badge-mock',
    icon: '○',
    pulse: false,
  },
  connecting: {
    label: 'Connecting',
    dot: GS.primary,
    cls: 'badge-connecting',
    icon: '◌',
    pulse: true,
  },
  // Socket reconnecting, during the fast retries.
  reconnecting: {
    dot: GS.warn,
    cls: 'badge-sim',
    pulse: true,
  },
  // The backend was answering and has stopped; retrying on a backoff.
  lost: {
    dot: GS.textSubtle,
    cls: 'badge-mock',
    pulse: false,
  },
  // REST is answering and the socket is not: current, by polling.
  polling: {
    dot: GS.success,
    cls: 'badge-live',
    pulse: false,
  },
}

/**
 * ConnectionModeBadge — renders the current connection state with unambiguous visual cues.
 * Read directly from connectionMode store field — never inferred.
 * Safety-critical: operators must distinguish LIVE from OFFLINE, CONNECTING and a lost socket at a glance.
 */
export default function ConnectionModeBadge({ mode, socketStatus = 'idle', className = '' }) {
  const display = connectionDisplay(mode, socketStatus)
  const cfg = { ...(MODES[display.key] ?? MODES.connecting), label: display.label }

  return (
    <StatusPill
      tone={TONE[cfg.cls]}
      pulse={cfg.pulse}
      className={className}
      role="status"
      aria-label={`Data source: ${cfg.label}`}
      aria-live="polite"
    >
      {cfg.label}
    </StatusPill>
  )
}
