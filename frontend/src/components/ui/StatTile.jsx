// [Windows] GraphSentinel — Susheep
// StatTile — Error.md #39: four near-identical label/value stat components
// (Forensics' StatCard, BlockchainLedger's MiniStat, AlertCentre's
// StatBadge, ThreatFeed's StatRow) collapsed into one, covering the two
// layouts actually used: a panel with the label above the value ('block'),
// and a row with the label and value side by side ('row').
export default function StatTile({ label, value, color, layout = 'block', panel = true, valueFontSize }) {
  const wrapperStyle = panel ? { padding: layout === 'row' ? '12px 16px' : '14px 16px' } : {}
  const wrapperClass = panel ? 'gs-panel' : undefined

  if (layout === 'row') {
    return (
      <div
        className={wrapperClass}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: panel ? 0 : 8, ...wrapperStyle }}
      >
        <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{label}</span>
        <span
          style={{
            color,
            fontFamily: panel ? "'Plus Jakarta Sans', sans-serif" : "'DM Mono', monospace",
            fontWeight: 700,
            fontSize: valueFontSize ?? (panel ? 22 : 13),
          }}
        >
          {value}
        </span>
      </div>
    )
  }

  return (
    <div className={wrapperClass} style={wrapperStyle}>
      <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ color, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: valueFontSize ?? 24 }}>
        {value}
      </div>
    </div>
  )
}
