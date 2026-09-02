// [Windows] GraphSentinel — Susheep
// ui/EnforcementModeBadge — SIMULATED / OVS ENFORCEMENT
// Safety-critical: operator must know whether "blocked" means a real OVS rule
// was applied or just recorded in the DB/blockchain (see Error.md #5)

const MODES = {
  ovs: {
    label: 'OVS ENFORCEMENT',
    cls: 'badge-live',
  },
  simulated: {
    label: 'SIMULATED ENFORCEMENT',
    cls: 'badge-sim',
  },
}

export default function EnforcementModeBadge({ mode, className = '' }) {
  const cfg = MODES[mode] ?? MODES.simulated

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider ${cfg.cls} ${className}`}
      role="status"
      aria-label={`Enforcement mode: ${cfg.label}`}
    >
      {cfg.label}
    </span>
  )
}
