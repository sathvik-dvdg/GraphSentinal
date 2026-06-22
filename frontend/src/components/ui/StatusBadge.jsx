// [Windows] GraphSentinel — Susheep
// ui/StatusBadge — node status with color + shape + text label (accessibility)
import { STATUS_ICONS, STATUS_LABELS } from '../../constants/theme'

const STATUS_STYLES = {
  normal:     'bg-gs-heal-soft border-gs-heal/25 text-gs-heal',
  suspicious: 'bg-gs-warn-soft border-gs-warn/25 text-gs-warn',
  malicious:  'bg-gs-threat-soft border-gs-threat/25 text-gs-threat',
  blocked:    'bg-gs-accent-soft border-gs-accent/25 text-gs-accent',
}

/**
 * StatusBadge — renders node status with color + icon shape + text
 * Never relies on color alone (§6 accessibility requirement)
 */
export default function StatusBadge({ status, size = 'sm', className = '' }) {
  const label = STATUS_LABELS[status] ?? status?.toUpperCase() ?? 'UNKNOWN'
  const icon  = STATUS_ICONS[status] ?? '●'
  const cls   = STATUS_STYLES[status] ?? 'bg-gs-faint/20 border-gs-border text-gs-muted'

  const textSize = size === 'xs' ? 'text-[9px]' : 'text-[10px]'
  const iconSize = size === 'xs' ? 'text-[8px]'  : 'text-[10px]'

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border font-mono font-medium ${textSize} ${cls} ${className}`}
      role="status"
      aria-label={`Node status: ${label}`}
    >
      <span className={iconSize} aria-hidden="true">{icon}</span>
      {label}
    </span>
  )
}
