// [Windows] GraphSentinel — Susheep
// StatTile — Error.md #39: four near-identical label/value stat components
// (Forensics' StatCard, BlockchainLedger's MiniStat, AlertCentre's
// StatBadge, ThreatFeed's StatRow) collapsed into one, covering the two
// layouts actually used: a panel with the label above the value ('block'),
// and a row with the label and value side by side ('row').
import { GS } from '../../constants/colors'

export default function StatTile({ label, value, color, icon, layout = 'block', panel = true, valueFontSize }) {
  const wrapperStyle = panel ? { padding: layout === 'row' ? '12px 16px' : '14px 16px' } : {}
  const wrapperClass = panel ? 'gs-panel' : undefined

  if (layout === 'row') {
    return (
      <div
        className={wrapperClass}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: panel ? 0 : 8, ...wrapperStyle }}
      >
        <span style={{ color: GS.textSubtle, fontSize: 11, fontFamily: "var(--font-mono)" }}>{label}</span>
        <span
          style={{
            color,
            fontFamily: panel ? "var(--font-display)" : "var(--font-mono)",
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
    <div className={wrapperClass} style={{ position: 'relative', overflow: 'hidden', ...wrapperStyle }}>
      {/* Ambient glow from accent colour */}
      <div style={{
        position: 'absolute', top: 0, right: 0, width: 60, height: 60,
        background: `${color}08`, filter: 'blur(20px)', pointerEvents: 'none',
      }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ color: GS.textSubtle, fontSize: 10, fontFamily: "var(--font-mono)", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {label}
        </div>
        {icon && (
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: `${color}12`, border: `1px solid ${color}25`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {icon}
          </div>
        )}
      </div>
      <div style={{ color, fontFamily: "var(--font-display)", fontWeight: 700, fontSize: valueFontSize ?? 24 }}>
        {value}
      </div>
    </div>
  )
}
