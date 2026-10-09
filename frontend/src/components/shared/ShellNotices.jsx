// [Windows] GraphSentinel
// shared/ShellNotices — two notices every protected page gets from the shell,
// above its own content, so no page has to remember them:
//   * a skeleton while the first poll is still out (never a blocking spinner);
//   * on the graph pages, a dismissible banner when the server caps the
//     graph it pushes over the socket.
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

export function GraphTruncatedBanner({ onDismiss }) {
  return (
    <div
      role="status"
      className="mb-4 flex items-center justify-between gap-3 rounded-md border border-gs-warn/30 bg-gs-warn-soft px-3 py-2 font-mono text-[11px] text-gs-warn"
      style={{ position: 'relative', zIndex: 1 }}
    >
      <span>Live pushes are capped at 50 nodes / 100 links. The full graph is shown and refreshed every 10 s.</span>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="rounded border border-gs-warn/30 px-2 py-0.5 text-xs"
      >
        Dismiss
      </button>
    </div>
  )
}

export default function ShellNotices({ pathname }) {
  const initialLoadDone = useGraphStore((s) => s.initialLoadDone)
  const graphTruncated = useGraphStore((s) => s.graphTruncated)
  const dismissed = useGraphStore((s) => s.graphTruncatedDismissed)
  const dismiss = useGraphStore((s) => s.dismissGraphTruncated)
  const connectionMode = useGraphStore((s) => s.connectionMode)
  return (
    <>
      {!initialLoadDone && connectionMode === 'connecting' && <FirstLoadSkeleton />}
      {graphTruncated && !dismissed && GRAPH_ROUTES.includes(pathname) && <GraphTruncatedBanner onDismiss={dismiss} />}
    </>
  )
}
