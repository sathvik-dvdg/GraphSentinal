// [Windows] GraphSentinel
// ReadinessCard -- step 1 of the console. One line says whether a run can start;
// the individual preflight checks sit under it for when it cannot.
import { CheckCircle2, XCircle } from 'lucide-react'
import { GS } from '../../constants/colors'

export default function ReadinessCard({ preflight }) {
  const checks = preflight?.checks || []
  const failed = checks.filter((c) => !c.ok)
  const loading = !preflight
  const ready = !loading && failed.length === 0

  const tone = loading
    ? { bg: 'rgba(43,42,40,0.05)', fg: GS.text, sub: GS.textMuted }
    : ready
      ? { bg: GS.successWash, fg: GS.successInk, sub: GS.successDeep }
      : { bg: GS.dangerSolidWash, fg: GS.dangerDeep, sub: GS.dangerInk }

  return (
    <section className="gs-panel" style={{ overflow: 'hidden' }} aria-label="Readiness">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', background: tone.bg }}>
        <StepNumber n={1} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: tone.fg }}>
            {loading ? 'Checking the network' : ready ? 'Ready to run' : 'Not ready to run'}
          </h2>
          <span style={{ fontSize: 13, color: tone.sub }}>
            {loading
              ? 'Asking the backend.'
              : ready
                ? `${checks.length} of ${checks.length} checks passed`
                : `${failed.length} of ${checks.length} ${failed.length === 1 ? 'check' : 'checks'} failed`}
          </span>
        </div>
      </div>
      {checks.length > 0 && (
        <ul style={{ listStyle: 'none', padding: '4px 20px 12px' }}>
          {checks.map((c, i) => (
            <li key={c.key} style={{ display: 'grid', gridTemplateColumns: '20px minmax(0, 1fr)', gap: 10, padding: '10px 0', borderTop: i === 0 ? 0 : '1px solid var(--border-subtle)' }}>
              {c.ok
                ? <CheckCircle2 size={16} strokeWidth={2} aria-hidden="true" style={{ color: GS.success, marginTop: 2 }} />
                : <XCircle size={16} strokeWidth={2} aria-hidden="true" style={{ color: GS.danger, marginTop: 2 }} />}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{c.label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: c.ok ? GS.textMuted : GS.danger, overflowWrap: 'anywhere' }}>
                  {c.detail}
                </div>
                {c.ok && String(c.detail).includes('ok_empty') && (
                  <div style={{ fontSize: 12, color: GS.textMuted, marginTop: 2 }}>No flows yet is normal before the first run.</div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function StepNumber({ n }) {
  return (
    <span
      aria-hidden="true"
      style={{ flexShrink: 0, width: 28, height: 28, borderRadius: 999, background: GS.text, color: GS.surface, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700 }}
    >
      {n}
    </span>
  )
}
