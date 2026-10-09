// [Windows] GraphSentinel
// ActivityLog -- the last few isolations the system made, newest first, from
// the healing feed. It answers "what just happened" without opening another page.
import { formatClock } from '../../utils/hostState'
import { GS } from '../../constants/colors'

export default function ActivityLog({ events, hosts }) {
  const nameOf = (ip) => hosts.find((h) => h.id === ip)?.label || ip
  const recent = [...(events || [])]
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, 5)

  return (
    <section className="gs-panel" style={{ overflow: 'hidden' }} aria-label="Recent isolations">
      <h2 style={{ padding: '14px 20px', fontSize: 16, fontWeight: 700, borderBottom: '1px solid var(--border-subtle)' }}>
        What just happened
      </h2>
      {recent.length === 0 ? (
        <p style={{ padding: '16px 20px', fontSize: 14, color: GS.textMuted }}>No host has been isolated yet.</p>
      ) : (
        <ol style={{ listStyle: 'none', padding: '4px 20px 12px' }}>
          {recent.map((ev, i) => (
            <li
              key={ev.id}
              style={{ display: 'grid', gridTemplateColumns: '64px minmax(0, 1fr)', gap: 12, padding: '10px 0', borderTop: i === 0 ? 0 : '1px solid var(--border-subtle)' }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: GS.textMuted, paddingTop: 2 }}>{formatClock(ev.timestamp)}</span>
              <span style={{ fontSize: 14, lineHeight: '20px' }}>
                <strong>{nameOf(ev.ip)} isolated.</strong>{' '}
                {ev.attack_type}, score {Number(ev.trigger_score).toFixed(2)}.
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
