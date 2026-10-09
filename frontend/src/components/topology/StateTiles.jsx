// [Windows] GraphSentinel
// StateTiles -- how many hosts are in each state, and which. The tiles are the
// legend as well: a state with nobody in it stays quiet so only the ones that
// matter draw the eye.
import { STATE_ORDER, HOST_STATES } from '../../utils/hostState'
import HostStateIcon from './HostStateIcon'
import { GS } from '../../constants/colors'

export default function StateTiles({ hosts, counts }) {
  return (
    <section className="gs-tiles" aria-label="Hosts by state">
      {STATE_ORDER.map((key, i) => {
        const count = counts[key]
        const lit = key === 'healthy' || count > 0
        const names = hosts.filter((h) => h.state === key).map((h) => h.label)
        return (
          <div
            key={key}
            className="gs-state gs-rise"
            data-state={lit ? key : 'quiet'}
            style={{
              '--i': i,
              display: 'flex', flexDirection: 'column', gap: 6, padding: '14px 16px', borderRadius: 10,
              background: lit && key !== 'healthy' ? 'var(--st-fill)' : 'var(--bg-panel)',
              border: lit && key !== 'healthy' ? 'var(--st-edge)' : '1px solid var(--border-panel)',
              color: lit ? undefined : GS.textMuted,
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: lit ? 'var(--st-fg)' : GS.textMuted, fontSize: 13, fontWeight: 600 }}>
              <HostStateIcon state={key} />
              {HOST_STATES[key].tile}
            </span>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 10, minWidth: 0 }}>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 40, lineHeight: '40px', fontWeight: 500, color: GS.text, fontVariantNumeric: 'tabular-nums' }}>
                {count}
              </span>
              <span style={{ fontSize: 13, color: GS.textBody, minWidth: 0, overflowWrap: 'anywhere' }}>
                {key === 'healthy'
                  ? `of ${hosts.length} ${hosts.length === 1 ? 'host' : 'hosts'}`
                  : count === 0 ? 'None right now' : names.join(', ')}
              </span>
            </span>
          </div>
        )
      })}
    </section>
  )
}
