// [Windows] GraphSentinel
// SelectedHostPanel -- one host, answered in three parts: why it is in its
// state, what the system did about it, and what you can do now. It replaces the
// slide-over drawer on this page so the map stays in view while you read.
import { Link } from 'react-router-dom'
import { Lock, LockOpen } from 'lucide-react'
import Button from '../ui/Button'
import ThreatBar from '../ui/ThreatBar'
import HostStateIcon from './HostStateIcon'
import useBlockHost from '../../hooks/useBlockHost'
import { ENFORCE_DENIED_REASON } from '../../utils/triage'
import { HOST_STATES, describeReason, describeAction, formatClock } from '../../utils/hostState'
import { GS } from '../../constants/colors'

const formatBytes = (b) => {
  if (typeof b !== 'number') return null
  if (b >= 1073741824) return `${(b / 1073741824).toFixed(1)} GB`
  if (b >= 1048576) return `${(b / 1048576).toFixed(1)} MB`
  if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${b} B`
}

export default function SelectedHostPanel({ host, events }) {
  const block = useBlockHost()

  if (!host) {
    return (
      <section className="gs-panel" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="gs-kicker">Selected host</span>
        <p style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 500 }}>No host selected</p>
        <p style={{ fontSize: 14, lineHeight: '21px', color: GS.textMuted }}>
          Select a host on the map or in the list to see why it is in its state and what the system did.
        </p>
      </section>
    )
  }

  const meta = HOST_STATES[host.state]
  const traffic = [
    host.connections != null ? `${host.connections} ${host.connections === 1 ? 'connection' : 'connections'}` : null,
    formatBytes(host.bytesTotal),
  ].filter(Boolean).join(' · ')

  return (
    <section className="gs-panel" style={{ padding: 0, overflow: 'hidden', boxShadow: `var(--glass-edge), 0 0 0 2px ${GS.text}` }} aria-label={`Selected host ${host.label}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <span className="gs-kicker">Selected host</span>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 28, lineHeight: '32px', fontWeight: 500 }}>{host.label}</h2>
          <span className="gs-state gs-state-chip" data-state={host.state}>
            <HostStateIcon state={host.state} size={14} />
            {meta.label}
          </span>
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: GS.textMuted }}>{host.id}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '16px 20px 20px' }}>
        <Fact label="Why">
          {describeReason(host)}
          {host.threatScore != null && <div style={{ marginTop: 8 }}><ThreatBar score={host.threatScore} showLabel /></div>}
        </Fact>
        <Fact label="What the system did">{describeAction(host, events, formatClock)}</Fact>
        {traffic && <Fact label="Traffic" mono>{traffic}</Fact>}

        {host.isBlocked && (
          <p style={{ padding: '10px 12px', borderRadius: 8, background: 'rgba(43,42,40,0.06)', fontSize: 13, lineHeight: '19px', color: GS.textBody }}>
            While {host.label} is isolated, <Link to="/simulation" style={{ color: GS.text, textDecoration: 'underline' }}>Attack Simulation</Link> will not run attacks from it.
          </p>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {host.isBlocked ? (
            <Button variant="secondary" disabled={block.busy || !block.mayEnforce} onClick={() => block.run(host.id, 'unblock')}>
              <LockOpen size={14} aria-hidden="true" /> {block.busy ? 'Releasing…' : 'Release host'}
            </Button>
          ) : (
            <Button variant="danger" disabled={block.busy || !block.mayEnforce} onClick={() => block.run(host.id, 'block')}>
              <Lock size={14} aria-hidden="true" /> {block.busy ? 'Isolating…' : 'Isolate host'}
            </Button>
          )}
          <Link to="/alerts" className="gs-btn gs-btn-ghost">Open in Alert Centre</Link>
        </div>
        {!block.mayEnforce && <p role="note" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: GS.textMuted }}>{ENFORCE_DENIED_REASON}</p>}
        {block.error && <p role="alert" style={{ fontSize: 12, color: GS.danger }}>{block.error}</p>}
      </div>
    </section>
  )
}

function Fact({ label, mono = false, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span className="gs-kicker">{label}</span>
      <div style={{ fontSize: 15, lineHeight: '22px', fontFamily: mono ? 'var(--font-mono)' : undefined }}>{children}</div>
    </div>
  )
}
