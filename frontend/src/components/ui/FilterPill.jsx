// [Windows] GraphSentinel — Susheep
// ui/FilterPill — shared filter pill used by AlertCentre and ThreatFeed.
// `color` is kept for call sites that tint a filter (e.g. a severity); the
// active state is an ink-filled pill, otherwise a quiet outline.
import Button from './Button'

export default function FilterPill({ label, active, onClick, color }) {
  return (
    <Button
      size="sm"
      variant="secondary"
      active={active}
      onClick={onClick}
      style={active && color ? { color, boxShadow: `inset 0 0 0 1px ${color}` } : { textTransform: 'capitalize' }}
    >
      {label}
    </Button>
  )
}
