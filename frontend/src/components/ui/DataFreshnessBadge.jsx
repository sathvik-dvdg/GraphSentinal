// [Windows] GraphSentinel — Susheep
// ui/DataFreshnessBadge — lights up when any panel's last fetch failed
// (Error.md #22/#26): distinguishes "no incidents" from "couldn't reach
// the incidents endpoint" instead of silently showing stale data as current.
// The wording is utils/connection.staleBadgeText; the tooltip lists every
// resource with its reason.
import { staleBadgeText, STALE_RESOURCE_LABELS } from '../../utils/connection'

export default function DataFreshnessBadge({ dataErrors, className = '' }) {
  const text = staleBadgeText(dataErrors)
  if (!text) return null

  const staleResources = Object.entries(dataErrors || {}).filter(([, err]) => err)
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider whitespace-nowrap badge-sim ${className}`}
      role="status"
      title={staleResources.map(([name, err]) => `${STALE_RESOURCE_LABELS[name] || name}: ${err}`).join('\n')}
    >
      STALE: {text.toUpperCase()}
    </span>
  )
}
