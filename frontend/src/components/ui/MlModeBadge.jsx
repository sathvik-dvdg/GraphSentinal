// [Windows] GraphSentinel — Susheep
// ui/MlModeBadge — warns when threat scores come from the heuristic
// fallback instead of the real GraphSAGE model (Error.md #4). The backend
// has always returned ml.mode/degraded_reason via /health; nothing in the
// frontend fetched or displayed it, so a missing/broken model could go
// unnoticed while the UI kept showing scores as if they were real GNN output.
// Hidden entirely in the normal case (mode === 'model') — like
// DataFreshnessBadge, only takes up space when there's something to flag.
import StatusPill from './StatusPill'
export default function MlModeBadge({ mlHealth, className = '' }) {
  if (!mlHealth || mlHealth.mode === 'model') return null

  return (
    <StatusPill
      tone="warn"
      className={className}
      role="status"
      title={mlHealth.degraded_reason || 'GraphSAGE model unavailable — using rule-based heuristic scoring'}
    >
      Heuristic scoring
    </StatusPill>
  )
}
