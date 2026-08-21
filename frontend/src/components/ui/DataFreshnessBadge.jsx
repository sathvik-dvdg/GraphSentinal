// [Windows] GraphSentinel — Susheep
// ui/DataFreshnessBadge — lights up when any panel's last fetch failed
// (Error.md #22/#26): distinguishes "no incidents" from "couldn't reach
// the incidents endpoint" instead of silently showing stale data as current.
const LABELS = {
  graph: 'graph',
  alerts: 'alerts',
  blocked: 'blocked IPs',
  forensics: 'forensics',
  stats: 'stats',
  timeline: 'timeline',
}

export default function DataFreshnessBadge({ dataErrors, className = '' }) {
  const staleResources = Object.entries(dataErrors || {}).filter(([, err]) => err)
  if (staleResources.length === 0) return null

  const label = staleResources.map(([name]) => LABELS[name] || name).join(', ')

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider badge-sim ${className}`}
      role="status"
      title={staleResources.map(([name, err]) => `${LABELS[name] || name}: ${err}`).join('\n')}
    >
      STALE: {label.toUpperCase()}
    </span>
  )
}
