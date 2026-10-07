// [Windows] GraphSentinel — Susheep
// ui/EnforcementModeBadge — SIMULATED / OVS ENFORCEMENT
// Safety-critical: operator must know whether "blocked" means a real OVS rule
// was applied or just recorded in the DB/blockchain (see Error.md #5)
import StatusPill from './StatusPill'

const MODES = {
  ovs: {
    label: 'OVS enforcement',
    cls: 'badge-live',
  },
  simulated: {
    label: 'Simulated enforcement',
    cls: 'badge-sim',
  },
}

export default function EnforcementModeBadge({ mode, className = '' }) {
  const cfg = MODES[mode] ?? MODES.simulated

  return (
    <StatusPill
      tone={mode === 'ovs' ? 'live' : 'warn'}
      className={className}
      role="status"
      aria-label={`Enforcement mode: ${cfg.label}`}
    >
      {cfg.label}
    </StatusPill>
  )
}
