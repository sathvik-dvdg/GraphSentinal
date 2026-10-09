// [Windows] GraphSentinel
// AttackPicker -- step 2 of the console: choose what to send, say whether it is
// the attack or its negative control, read what should happen, then run it.
// The page owns the state and the calls; this only draws and reports clicks.
import { Link } from 'react-router-dom'
import { Lock, Play, Loader2, CheckCircle2 } from 'lucide-react'
import Button from '../ui/Button'
import { StepNumber } from './ReadinessCard'
import { GS } from '../../constants/colors'

export default function AttackPicker({
  attacks, picked, onPick, blockers, onControl, selected, controlAvailable, useControl,
  threshold, active, sending, startDisabled, onStart, onStop, canStop, blockedReason, failedChecks, heldBy, startError,
}) {
  const thresholdText = typeof threshold === 'number' ? threshold : 'the threshold'

  return (
    <section className="gs-panel" aria-label="Choose an attack">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <StepNumber n={2} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700 }}>Choose what to send</h2>
          <span style={{ fontSize: 13, color: GS.textMuted }}>Each attack comes from a fixed host. An isolated host cannot be used.</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 20 }}>
        <div role="radiogroup" aria-label="Attack" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {attacks.map((a) => {
            const on = a.key === picked
            const held = (blockers[a.key] || [])[0]
            return (
              <button
                key={a.key}
                type="button"
                role="radio"
                aria-checked={on}
                disabled={active}
                onClick={() => onPick(a.key)}
                style={{
                  textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 6, padding: '12px 14px', minHeight: 44, borderRadius: 10,
                  cursor: active ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', color: GS.text,
                  background: on ? GS.surfaceLift : held ? 'rgba(43,42,40,0.05)' : 'transparent',
                  border: on ? `2px solid ${GS.text}` : held ? '1px dashed rgba(43,42,40,0.4)' : '1px solid var(--border-panel)',
                  transition: 'background-color 160ms, border-color 160ms',
                }}
              >
                <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 15, fontWeight: 700 }}>{a.name}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: GS.textMuted }}>{a.expected_label}</span>
                </span>
                <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  <Chip>{a.source_host} {a.source_ip}</Chip>
                  <span aria-hidden="true">to</span>
                  <Chip>{a.target}</Chip>
                  <span style={{ marginLeft: 'auto', color: GS.textSubtle }}>{a.script}</span>
                </span>
                <span style={{ fontSize: 13, color: GS.textBody }}>{a.sends}</span>
                {held ? (
                  <span style={{ display: 'inline-flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: GS.warnInk }}>
                    <Lock size={14} aria-hidden="true" />
                    Held: {held}
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: GS.success }}>
                    <CheckCircle2 size={14} aria-hidden="true" />
                    Available
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {(blockers[picked] || []).length > 0 && !useControl && (
          <p style={{ fontSize: 13, color: GS.textBody }}>
            Release the host on <Link to="/network" style={{ color: GS.text, textDecoration: 'underline' }}>Network Topology</Link> to run this attack.
            {controlAvailable ? ' Its control run does not need the host free.' : ''}
          </p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span id="sim-mode-label" className="gs-kicker">Run as</span>
          <div className="gs-seg" role="radiogroup" aria-labelledby="sim-mode-label" style={{ alignSelf: 'flex-start' }}>
            <button type="button" role="radio" aria-checked={!useControl} className="gs-seg-item" disabled={active} onClick={() => onControl(false)}>
              Attack
            </button>
            <button
              type="button" role="radio" aria-checked={useControl} className="gs-seg-item"
              disabled={active || !controlAvailable} onClick={() => onControl(true)}
              title={controlAvailable ? undefined : 'A control exists for a single attack, not the full sequence.'}
            >
              Control{controlAvailable ? ` (${selected.control_flag})` : ''}
            </button>
          </div>
        </div>

        {selected && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '12px 14px', borderRadius: 10, background: useControl ? 'rgba(43,42,40,0.05)' : GS.dangerSolidWash, border: useControl ? '1px solid var(--border-panel)' : `1px solid ${GS.danger}` }}>
            <span className="gs-kicker" style={{ color: useControl ? GS.textMuted : GS.dangerInk }}>What you should see</span>
            <span style={{ fontSize: 15, lineHeight: '22px' }}>
              {useControl
                ? sentence(selected.control_note)
                : selected.key === 'sequence'
                  ? `An incident for each of the three sources, once v1 scores each over ${thresholdText}.`
                  : `An incident for ${selected.source_ip}, labelled ${selected.expected_label}, once v1 scores it over ${thresholdText}.`}
            </span>
          </div>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <Button id="simulation-start" variant="accent" onClick={onStart} disabled={startDisabled} style={{ height: 40, padding: '0 22px', fontSize: 14 }}>
            {sending || active ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
            {active ? 'Running' : selected ? `Run ${selected.name}${useControl ? ' as a control' : ''}` : 'Run'}
          </Button>
          <Button variant="ghost" onClick={onStop} disabled={!canStop}>
            Stop run
          </Button>
        </div>

        {(blockedReason || failedChecks.length > 0) && !active && (
          <p role="note" style={{ fontSize: 13, color: GS.textMuted }}>
            {blockedReason || 'Fix the failed checks in step 1 to start a run.'}
          </p>
        )}
        {heldBy.slice(1).map((msg) => <Notice key={msg} color={GS.warn}>{msg}</Notice>)}
        {startError && <Notice color={GS.danger}>{String(startError)}</Notice>}
      </div>
    </section>
  )
}

// A control note is a lower-case fragment ("the ports are left closed: ...").
const sentence = (note) => {
  const t = String(note || "").trim()
  return t ? `${t[0].toUpperCase()}${t.slice(1)}.` : "Expect no incident."
}

function Chip({ children }) {
  return <span style={{ padding: '2px 8px', borderRadius: 6, background: 'rgba(43,42,40,0.07)' }}>{children}</span>
}

export function Notice({ color, children }) {
  return (
    <div role="alert" style={{ border: `1px solid ${color}55`, background: `${color}12`, color, borderRadius: 8, padding: '8px 12px', fontSize: 13 }}>
      {children}
    </div>
  )
}
