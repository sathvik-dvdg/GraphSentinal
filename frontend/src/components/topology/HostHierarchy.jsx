// [Windows] GraphSentinel
// HostHierarchy -- the network as a tree: the network, its switch s1, then the
// hosts grouped by state. The backend holds no roles or departments (see
// useNodeHierarchy), so the only grouping that is true of every host is what
// state it is in. Each group heading carries that state's cues.
import { STATE_ORDER, HOST_STATES, describeReason } from '../../utils/hostState'
import HostStateIcon from './HostStateIcon'
import { GS } from '../../constants/colors'

const RAIL = GS.rail

export default function HostHierarchy({ hosts, selectedId, onSelect }) {
  const groups = STATE_ORDER
    .map((key) => ({ key, hosts: hosts.filter((h) => h.state === key) }))
    .filter((g) => g.hosts.length > 0)

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ minWidth: Math.max(groups.length, 2) * 230, padding: '24px 16px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={nodeCard}>
          <strong style={{ fontSize: 14 }}>Network</strong>
          <span style={{ fontSize: 12, color: GS.textMuted }}>{hosts.length} {hosts.length === 1 ? 'host' : 'hosts'}</span>
        </div>
        <div style={{ width: 2, height: 20, background: RAIL }} />
        <div style={{ ...nodeCard, background: GS.text, color: GS.surface, border: 0 }}>
          <strong style={{ fontSize: 14 }}>s1</strong>
          <span style={{ fontSize: 12, color: GS.border }}>Every host connects here</span>
        </div>
        <div style={{ width: 2, height: 18, background: RAIL }} />

        <div style={{ width: '100%', display: 'grid', gridTemplateColumns: `repeat(${groups.length}, minmax(0, 1fr))` }}>
          {groups.map((g, i) => (
            <div key={g.key} style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ position: 'relative', height: 22 }} aria-hidden="true">
                {i > 0 && <div style={{ position: 'absolute', top: 0, left: 0, width: '50%', height: 2, background: RAIL }} />}
                {i < groups.length - 1 && <div style={{ position: 'absolute', top: 0, right: 0, width: '50%', height: 2, background: RAIL }} />}
                <div style={{ position: 'absolute', top: 0, left: 'calc(50% - 1px)', width: 2, height: 22, background: RAIL }} />
              </div>
              <div style={{ padding: '0 8px', display: 'flex', flex: 1 }}>
                <Group group={g} selectedId={selectedId} onSelect={onSelect} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const nodeCard = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, minWidth: 220, padding: '10px 16px',
  borderRadius: 10, background: GS.surfaceLift, border: '1px solid rgba(43,42,40,0.28)',
}

function Group({ group, selectedId, onSelect }) {
  const meta = HOST_STATES[group.key]
  const quiet = group.key === 'healthy'
  return (
    <div
      className="gs-state"
      data-state={group.key}
      style={{
        flex: 1, minWidth: 0, borderRadius: 12, overflow: 'hidden', background: GS.surfaceLift,
        border: quiet ? '1px solid rgba(43,42,40,0.2)' : 'var(--st-edge)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: quiet ? 'transparent' : 'var(--st-fill)', color: 'var(--st-fg)', borderBottom: '1px solid rgba(43,42,40,0.1)' }}>
        <HostStateIcon state={group.key} />
        <span style={{ fontSize: 14, fontWeight: 700 }}>{meta.label}</span>
        <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{group.hosts.length}</span>
      </div>
      <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4, padding: 8 }}>
        {group.hosts.map((h) => (
          <li key={h.id}>
            <button
              type="button"
              className="gs-host-row"
              aria-pressed={selectedId === h.id}
              onClick={() => onSelect(h.id)}
              style={{ gap: 2, padding: '8px 10px', borderRadius: 8 }}
            >
              <span style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <strong style={{ fontSize: 13 }}>{h.label}</strong>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: GS.textMuted }}>{h.id}</span>
              </span>
              {!quiet && <span style={{ fontSize: 12, lineHeight: '17px', color: GS.textBody }}>{describeReason(h)}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
