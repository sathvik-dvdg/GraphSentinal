// [Windows] GraphSentinel
// ResultPanel -- step 3 of the console: what the run came to. For each attack
// it gives a verdict in plain words, the v1 score against the threshold, and
// the four things that happened in order. The raw script output sits below,
// short by default.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, TriangleAlert, XCircle, Loader2, Circle } from 'lucide-react'
import ScoreMeter from './ScoreMeter'
import { StepNumber } from './ReadinessCard'
import { stagesFor, verdictFor, PHASE_LABELS } from '../../utils/simulation'
import { GS } from '../../constants/colors'

const TONE = {
  ok:      { bg: GS.successWash, edge: GS.success, fg: GS.successInk, Icon: CheckCircle2 },
  caught:  { bg: GS.successWash, edge: GS.success, fg: GS.successInk, Icon: CheckCircle2 },
  warn:    { bg: GS.warnWash, edge: GS.warn, fg: GS.warnInk, Icon: TriangleAlert },
  fail:    { bg: GS.dangerSolidWash, edge: GS.danger, fg: GS.dangerDeep, Icon: XCircle },
  pending: { bg: 'rgba(43,42,40,0.06)', edge: GS.textFaint, fg: GS.text, Icon: Loader2 },
}

const STAGE_WORD = { done: 'Done', active: 'In progress', pending: 'Not reached', warn: 'Check this', failed: 'Failed' }
const STAGE_INK = { done: GS.successDeep, active: GS.warnInk, pending: GS.textSubtle, warn: GS.warnInk, failed: GS.dangerInk }

export default function ResultPanel({ run, steps, attacks, threshold, secondsLeft }) {
  const [full, setFull] = useState(false)
  const nameOf = (key) => attacks.find((a) => a.key === key)?.name || key
  const log = run?.log || []
  const shown = full ? log : log.filter((e) => e.kind === 'result' || e.kind === 'error' || e.kind === 'info')

  return (
    <section className="gs-panel" style={{ overflow: 'hidden' }} aria-label="Result">
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StepNumber n={3} />
          <h2 style={{ fontSize: 16, fontWeight: 700 }}>Result</h2>
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: GS.textSubtle }}>
          {run ? `#${run.id} · ${nameOf(run.attack)}${run.control ? ' (control)' : ''} · ${run.status} · by ${run.started_by}` : 'No run yet'}
        </span>
      </div>

      {steps.length === 0 && (
        <div style={{ padding: '40px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, textAlign: 'center' }}>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 500 }}>Nothing has run yet</p>
          <p style={{ fontSize: 14, lineHeight: '21px', color: GS.textMuted, maxWidth: 400 }}>
            Pick an attack and press Run. The verdict, the v1 score and the script output appear here.
          </p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map((step, i) => {
          const verdict = verdictFor(step.result) || { tone: 'pending', tag: PHASE_LABELS[step.state] || 'Waiting', title: `${nameOf(step.key)} is ${step.state === 'pending' ? 'waiting' : 'running'}.`, body: '' }
          const tone = TONE[verdict.tone]
          const stages = stagesFor(step, threshold)
          const score = step.result?.score
          const incident = step.result?.incident
          return (
            <div key={step.key} style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 20, borderTop: i === 0 ? 0 : '1px solid var(--border-subtle)' }}>
              {steps.length > 1 && <h3 style={{ fontSize: 14, fontWeight: 700 }}>{nameOf(step.key)}</h3>}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '16px 18px', borderRadius: 10, background: tone.bg, border: `1px solid ${tone.edge}`, color: tone.fg }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700 }}>
                  <tone.Icon size={16} strokeWidth={2} aria-hidden="true" className={verdict.tone === 'pending' ? 'animate-spin' : undefined} />
                  {verdict.tag}
                  {step.state === 'scoring' && secondsLeft != null ? ` · up to ${secondsLeft}s` : ''}
                </span>
                <p style={{ fontFamily: 'var(--font-display)', fontSize: 26, lineHeight: '30px', fontWeight: 500 }}>{verdict.title}</p>
                {verdict.body && <p style={{ fontSize: 14, lineHeight: '21px' }}>{verdict.body}</p>}
                {incident && (
                  <p style={{ fontSize: 14 }}>
                    <Link to="/alerts" style={{ color: tone.fg, textDecoration: 'underline', fontWeight: 600 }}>Open in Alert Centre</Link>
                  </p>
                )}
              </div>

              {typeof score === 'number' && <ScoreMeter score={score} threshold={threshold} />}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span className="gs-kicker">What happened, in order</span>
                <ol style={{ listStyle: 'none', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(170px, 100%), 1fr))', gap: 10 }}>
                  {stages.map((s, n) => (
                    <li key={s.key} style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '10px 12px', borderRadius: 8, background: 'rgba(43,42,40,0.04)', border: '1px solid var(--border-subtle)' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: STAGE_INK[s.state] }}>
                        <StageIcon state={s.state} />
                        {n + 1}. {STAGE_WORD[s.state]}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{s.title}</span>
                      <span style={{ fontSize: 13, lineHeight: '18px', color: GS.textMuted }}>{s.text}</span>
                    </li>
                  ))}
                </ol>
              </div>

              {incident && (
                <p style={{ fontSize: 12, lineHeight: '18px', color: GS.textMuted }}>
                  The label {incident.attack_type} comes from a port and volume rule, not from the model. v1 itself only decides threat or not threat.
                </p>
              )}
            </div>
          )
        })}
      </div>

      {run?.error && <div role="alert" style={{ margin: '0 20px 16px', padding: '8px 12px', borderRadius: 8, border: `1px solid ${GS.danger}55`, background: `${GS.danger}12`, color: GS.danger, fontSize: 13 }}>{run.error}</div>}

      <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '8px 20px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: GS.textMuted }}>Script output</span>
          {log.length > 0 && (
            <button type="button" className="gs-btn gs-btn-ghost" style={{ height: 36 }} onClick={() => setFull((f) => !f)} aria-expanded={full}>
              {full ? 'Show key lines only' : 'Show full output'}
            </button>
          )}
        </div>
        <div
          aria-live="polite"
          style={{ padding: '10px 20px 16px', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: '20px', maxHeight: 340, minHeight: 80, overflow: 'auto', background: 'rgba(43,42,40,0.06)' }}
        >
          {shown.length === 0 && <div style={{ color: GS.textSubtle }}>Output appears here, line by line, as the script prints it.</div>}
          {shown.map((e, i) => (
            <div key={`${e.t}-${i}`} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: e.kind === 'error' ? GS.danger : e.kind === 'result' ? GS.text : e.kind === 'cmd' ? GS.textSubtle : GS.textBody, fontWeight: e.kind === 'result' ? 600 : 400 }}>
              {e.line}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function StageIcon({ state }) {
  const props = { size: 14, strokeWidth: 2, 'aria-hidden': true }
  if (state === 'done') return <CheckCircle2 {...props} />
  if (state === 'failed') return <XCircle {...props} />
  if (state === 'warn') return <TriangleAlert {...props} />
  if (state === 'active') return <Loader2 {...props} className="animate-spin" />
  return <Circle {...props} />
}
