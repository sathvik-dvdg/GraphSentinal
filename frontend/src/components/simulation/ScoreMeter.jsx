import { GS } from '../../constants/colors'
// [Windows] GraphSentinel
// ScoreMeter -- v1's score for a host against the threshold, on one 0 to 1 scale.
// The threshold is a labelled tick; the number and a sentence say which side the
// score fell on, so the answer never depends on reading the bar.
export default function ScoreMeter({ score, threshold }) {
  const known = typeof threshold === 'number'
  const over = known && score >= threshold
  const fill = over ? GS.danger : GS.success
  const pct = Math.max(0, Math.min(100, score * 100))
  const tick = known ? Math.max(0, Math.min(100, threshold * 100)) : null
  const verdict = !known ? '' : over ? 'Over the threshold: an incident.' : 'Under the threshold: no incident.'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span className="gs-kicker">v1 score</span>
        <span style={{ fontSize: 14, color: GS.textBody }}>
          <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 22, color: over ? GS.dangerInk : GS.successDeep }}>{score.toFixed(2)}</strong>
          {verdict && <span> &nbsp;{verdict}</span>}
        </span>
      </div>
      <div
        role="img"
        aria-label={`v1 score ${score.toFixed(2)} on a scale of 0 to 1${known ? `, threshold ${threshold}` : ''}`}
        style={{ position: 'relative', height: known ? 44 : 20, marginTop: known ? 4 : 0 }}
      >
        {known && (
          <span style={{ position: 'absolute', left: `${tick}%`, top: 0, transform: 'translateX(-50%)', fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap' }}>
            threshold {threshold}
          </span>
        )}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 4, height: 14, borderRadius: 7, background: 'rgba(43,42,40,0.12)' }} />
        <div style={{ position: 'absolute', left: 0, bottom: 4, height: 14, borderRadius: 7, width: `${pct}%`, background: fill, transition: 'width 600ms cubic-bezier(0.16, 1, 0.3, 1)' }} />
        {known && <div style={{ position: 'absolute', left: `${tick}%`, bottom: 0, width: 2, height: 26, background: GS.text }} />}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, color: GS.textMuted }}>
        <span>0</span><span>1</span>
      </div>
    </div>
  )
}
