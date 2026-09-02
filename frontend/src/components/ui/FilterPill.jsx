// [Windows] GraphSentinel — Susheep
// ui/FilterPill — Error.md #39: shared filter pill button extracted from
// AlertCentre.jsx (line 284) and ThreatFeed.jsx (line 239), which had
// identical implementations that had drifted slightly apart (padding/fontWeight).
// This is the superset: ThreatFeed's fontWeight active state is preserved.
export default function FilterPill({ label, active, onClick, color = '#4F6EF7' }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 10px',
        borderRadius: 6,
        border: `1px solid ${active ? color : 'rgba(255,255,255,0.08)'}`,
        background: active ? `${color}18` : 'transparent',
        color: active ? color : '#5A6480',
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
