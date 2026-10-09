// [Windows] GraphSentinel
// ui/DetectionPathBadge — which model produced what is on screen.
// Two models run in the backend (MODEL_BEHAVIOUR.md §1.1). Every incident,
// block and chain record on this dashboard comes from v1, the in-process
// two-class GraphSAGE; that half is static. v2, the audited five-class GATv2
// model, only generates rules, in dry-run — when it runs at all: under
// docker-compose.v1.yml it is off, so its half is read from /health (ml_v2).
// The text has to stand alone: a tooltip is invisible on a projector.
import StatusPill from './StatusPill'

const V1 = 'Incidents, blocks and chain records shown here are produced by v1 (two-class GraphSAGE). '

// mlV2 is /health's ml_v2 object, or null until /health has answered.
export function v2State(mlV2) {
  if (!mlV2) return { label: 'v2 unknown', title: 'The backend has not reported whether v2 is running.' }
  if (!mlV2.enabled) return { label: 'v2 off', title: 'v2 (five-class GATv2) is not running on this stack.' }
  if (mlV2.client && mlV2.client.reachable === false) {
    return { label: 'v2 not answering', title: 'v2 is enabled but its inference service is not answering: it is producing no scores.' }
  }
  return { label: 'v2 dry-run', title: 'v2 (five-class GATv2) generates rules in dry-run only and blocks nothing.' }
}

export default function DetectionPathBadge({ mlV2 = null, className = '' }) {
  const v2 = v2State(mlV2)
  const title = V1 + v2.title
  return (
    <StatusPill
      tone="warn"
      className={className}
      role="status"
      title={title}
      aria-label={title}
    >
      Blocks: v1 · {v2.label}
    </StatusPill>
  )
}
