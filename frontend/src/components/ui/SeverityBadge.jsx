// [Windows] GraphSentinel — Susheep
// ui/SeverityBadge — alert severity with color + icon + text label (accessibility)
import { SEVERITY_STYLES } from '../../constants/theme'

/**
 * SeverityBadge — renders severity with color + icon shape + text
 * Never relies on color alone (§6 accessibility requirement)
 */
export default function SeverityBadge({ severity, className = '' }) {
  const style = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.info

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border font-mono text-[10px] font-medium ${style.badge} ${className}`}
      role="status"
      aria-label={`Severity: ${style.label}`}
    >
      <span className="text-[9px]" aria-hidden="true">{style.icon}</span>
      {style.label}
    </span>
  )
}
