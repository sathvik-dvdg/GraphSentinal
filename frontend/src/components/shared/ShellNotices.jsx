// [Windows] GraphSentinel
// shared/ShellNotices — two notices every protected page gets from the shell,
// above its own content, so no page has to remember them:
//   * a skeleton while the first poll is still out (never a blocking spinner);
//   * on the graph pages, a dismissible banner when the server truncated the
//     graph it broadcast.
import { useState } from 'react'
import useGraphStore from '../../store/useGraphStore'

const GRAPH_ROUTES = ['/dashboard', '/network']

export function FirstLoadSkeleton() {
  return (
    <div role="status" aria-label="Loading live data" className="mb-4 space-y-2" style={{ position: 'relative', zIndex: 1 }}>
      {[72, 100, 88].map((width) => (
        <div
          key={width}
          className="h-3 rounded bg-gs-surface-raised animate-pulse"
          style={{ width: `${width}%` }}
        />
      ))}
      <span className="font-mono text-[10px] text-gs-muted">Loading live data from the backend…</span>
    </div>
  )
}

export function GraphTruncatedBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <div
      role="status"
      className="mb-4 flex items-center justify-between gap-3 rounded-md border border-gs-warn/30 bg-gs-warn-soft px-3 py-2 font-mono text-[11px] text-gs-warn"
      style={{ position: 'relative', zIndex: 1 }}
    >
      <span>Graph truncated to 50 nodes / 100 links. Full data available via API.</span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="rounded border border-gs-warn/30 px-2 py-0.5 text-[10px] uppercase tracking-wider"
      >
        Dismiss
      </button>
    </div>
  )
}

export default function ShellNotices({ pathname }) {
  const initialLoadDone = useGraphStore((s) => s.initialLoadDone)
  const graphTruncated = useGraphStore((s) => s.graphTruncated)
  const connectionMode = useGraphStore((s) => s.connectionMode)
  return (
    <>
      {!initialLoadDone && connectionMode === 'connecting' && <FirstLoadSkeleton />}
      {graphTruncated && GRAPH_ROUTES.includes(pathname) && <GraphTruncatedBanner />}
    </>
  )
}
