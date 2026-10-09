// [Windows] GraphSentinel
// AttentionTable -- only the hosts that are not healthy, with the reason in a
// sentence. Healthy hosts are left out on purpose: the tiles already count them.
import { describeReason, latestEventFor, formatClock } from '../../utils/hostState'
import HostStateIcon from './HostStateIcon'
import { HOST_STATES } from '../../utils/hostState'
import { GS } from '../../constants/colors'

export default function AttentionTable({ hosts, events, selectedId, onSelect }) {
  const rows = hosts.filter((h) => h.state !== 'healthy')
  const healthy = hosts.length - rows.length

  return (
    <section className="gs-panel" style={{ overflow: 'hidden' }} aria-label="Hosts that need attention">
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700 }}>
          {rows.length === 0 ? 'Nothing needs attention' : `Needs attention (${rows.length})`}
        </h2>
        <span style={{ fontSize: 13, color: GS.textMuted }}>
          {healthy} healthy {healthy === 1 ? 'host is' : 'hosts are'} not listed.
        </span>
      </div>

      {rows.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', minWidth: 620, borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: GS.textMuted, fontSize: 12 }}>
                <th scope="col" style={th}>Host</th>
                <th scope="col" style={th}>State</th>
                <th scope="col" style={th}>Why</th>
                <th scope="col" style={th}>Since</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => {
                const ev = latestEventFor(h.id, events)
                const picked = selectedId === h.id
                return (
                  <tr
                    key={h.id}
                    onClick={() => onSelect(h.id)}
                    style={{ borderTop: '1px solid var(--border-subtle)', cursor: 'pointer', background: picked ? 'rgba(43,42,40,0.07)' : undefined }}
                  >
                    <td style={td}>
                      <button
                        type="button"
                        aria-pressed={picked}
                        onClick={(e) => { e.stopPropagation(); onSelect(h.id) }}
                        style={{ all: 'unset', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2, minHeight: 44, justifyContent: 'center' }}
                      >
                        <strong>{h.label}</strong>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: GS.textMuted }}>{h.id}</span>
                      </button>
                    </td>
                    <td style={td}>
                      <span className="gs-state gs-state-chip" data-state={h.state}>
                        <HostStateIcon state={h.state} size={14} />
                        {HOST_STATES[h.state].label}
                      </span>
                    </td>
                    <td style={{ ...td, maxWidth: 320 }}>{describeReason(h)}</td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)', fontSize: 12 }}>{ev ? formatClock(ev.timestamp) : 'n/a'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

const th = { padding: '10px 20px', fontWeight: 600 }
const td = { padding: '6px 20px', verticalAlign: 'middle' }
