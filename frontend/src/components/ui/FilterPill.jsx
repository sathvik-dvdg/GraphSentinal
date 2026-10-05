// [Windows] GraphSentinel — Susheep
// ui/FilterPill — Error.md #39: shared filter pill button extracted from
// AlertCentre.jsx (line 284) and ThreatFeed.jsx (line 239), which had
// identical implementations that had drifted slightly apart (padding/fontWeight).
// This is the superset: ThreatFeed's fontWeight active state is preserved.
import { GS } from '../../constants/colors'

export default function FilterPill({ label, active, onClick, color = GS.primary }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 10px',
        borderRadius: 6,
        border: `1px solid ${active ? color : 'rgba(17,20,26,0.10)'}`,
        background: active ? `${color}18` : 'transparent',
        color: active ? color : GS.textSubtle,
        fontSize: 10,
        fontFamily: "'DM Mono', monospace",
        fontWeight: active ? 600 : 400,
        cursor: 'pointer',
        transition: 'all 150ms',
        textTransform: 'capitalize',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}
