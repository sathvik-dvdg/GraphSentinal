// [Windows] GraphSentinel — Susheep
// ui/MlModeBadge — warns when threat scores come from the heuristic
// fallback instead of the real GraphSAGE model (Error.md #4). The backend
// has always returned ml.mode/degraded_reason via /health; nothing in the
// frontend fetched or displayed it, so a missing/broken model could go
// unnoticed while the UI kept showing scores as if they were real GNN output.
// Hidden entirely in the normal case (mode === 'model') — like
// DataFreshnessBadge, only takes up space when there's something to flag.
export default function MlModeBadge({ mlHealth, className = '' }) {
  if (!mlHealth || mlHealth.mode === 'model') return null

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider badge-sim ${className}`}
      role="status"
      title={mlHealth.degraded_reason || 'GraphSAGE model unavailable — using rule-based heuristic scoring'}
    >
      HEURISTIC SCORING
    </span>
  )
}
