// [Windows] GraphSentinel
// ui/DetectionPathBadge — which model produced what is on screen.
// Two models run in the backend (MODEL_BEHAVIOUR.md §1.1). Every incident,
// block and chain record on this dashboard comes from v1, the in-process
// two-class GraphSAGE. v2, the audited five-class GATv2 model, only generates
// rules, in dry-run: it blocks nothing. Static on purpose — this does not
// depend on configuration.

const TITLE =
  'Incidents, blocks and chain records shown here are produced by v1 (two-class GraphSAGE). ' +
  'v2 (five-class GATv2) generates rules in dry-run only and blocks nothing.'

export default function DetectionPathBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider badge-sim ${className}`}
      role="status"
      title={TITLE}
      aria-label={TITLE}
    >
      BLOCKS: v1 MODEL · v2: DRY-RUN
    </span>
  )
}
