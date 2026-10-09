// [Windows] GraphSentinel
// AttackSimulation — the Simulate console. A run starts one of the real scripts
// in mininet/demo/attacks on the live topology through the backend
// (POST /api/v1/simulations); nothing here builds or sends a flow. What the
// dashboard shows afterwards is what the switch saw and v1 scored.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Crosshair, Play, Square, CheckCircle2, XCircle, Loader2, Circle } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import useSessionUser from '../hooks/useSessionUser'
import { getSimulations, startSimulation, stopSimulation } from '../services/api'
import { simulationBlockedReason } from '../utils/connection'
import { stepStates, describeResult, scoringSecondsLeft, PHASE_LABELS } from '../utils/simulation'
import { GS } from '../constants/colors'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const MONO = "'DM Mono', monospace"

const LOG_COLORS = { cmd: GS.textFaint, info: GS.textSubtle, result: GS.primary, error: GS.danger, out: GS.text }

export default function AttackSimulation() {
  const { connectionMode, simulationRun: run, setSimulationRun } = useGraphStore()
  const { role } = useSessionUser()

  const [attacks, setAttacks] = useState([])
  const [preflight, setPreflight] = useState(null)
  // Per attack: why a real (non-control) run could not record its incident.
  const [blockers, setBlockers] = useState({})
  const [loadError, setLoadError] = useState(null)
  const [picked, setPicked] = useState('flood')
  const [control, setControl] = useState(false)
  const [startError, setStartError] = useState(null)
  const [sending, setSending] = useState(false)
  const [now, setNow] = useState(() => Date.now())

  const active = Boolean(run?.active)

  const load = useCallback(() => {
    getSimulations()
      .then((res) => {
        setAttacks(res.attacks || [])
        setPreflight(res.preflight || null)
        setBlockers(res.blockers || {})
        if (res.current) setSimulationRun(res.current)
        setLoadError(null)
      })
      .catch((err) => setLoadError(err?.response?.data?.detail || 'The backend did not answer.'))
  }, [setSimulationRun])

  // The socket pushes each change of a run; this poll fills in the full log and
  // keeps preflight current (faster while a run is going).
  useEffect(() => {
    load()
    const id = setInterval(load, active ? 3000 : 10000)
    return () => clearInterval(id)
  }, [load, active])

  // A clock for the scoring countdown, only while something is running.
  useEffect(() => {
    if (!active) return undefined
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active])

  const blocked = simulationBlockedReason(USE_MOCK, connectionMode, role)
  const failedChecks = (preflight?.checks || []).filter((c) => !c.ok)
  const selected = attacks.find((a) => a.key === picked)
  const controlAvailable = Boolean(selected?.control_flag)
  const useControl = control && controlAvailable
  const heldBy = useControl ? [] : (blockers[picked] || [])
  const startDisabled = sending || active || Boolean(blocked) || failedChecks.length > 0 || heldBy.length > 0 || !selected

  const start = async () => {
    setStartError(null)
    setSending(true)
    try {
      setSimulationRun(await startSimulation(picked, useControl))
    } catch (err) {
      const detail = err?.response?.data?.detail
      setStartError(typeof detail === 'string' ? detail : detail?.message || 'The backend refused the run.')
      if (detail?.checks?.length) setPreflight({ ok: false, checks: detail.checks })
    } finally {
      setSending(false)
    }
  }

  const stop = async () => {
    try {
      setSimulationRun(await stopSimulation())
    } catch (err) {
      setStartError(err?.response?.data?.detail || 'Could not stop the run.')
    }
  }

  const steps = stepStates(run)
  const secondsLeft = scoringSecondsLeft(run, now)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ color: GS.text, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Attack Simulation
        </h1>
        <p style={{ color: GS.textSubtle, fontFamily: MONO, fontSize: 12, maxWidth: 820, lineHeight: 1.6 }}>
          Runs a script from <code>mininet/demo/attacks</code> on the live topology. Nothing synthetic is
          posted: an incident appears only if the switch carried the traffic and v1 scored it over the threshold.
        </p>
      </div>

      {loadError && <Notice color={GS.danger}>{String(loadError)}</Notice>}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        {/* ── Left: preflight + attack picker ── */}
        <div style={{ flex: '1 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <section className="gs-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <PanelTitle>Preflight</PanelTitle>
            {!preflight && <span style={{ color: GS.textFaint, fontFamily: MONO, fontSize: 11 }}>Checking…</span>}
            {(preflight?.checks || []).map((c) => (
              <div key={c.key} style={{ display: 'grid', gridTemplateColumns: '16px minmax(0, 1fr)', gap: 8, alignItems: 'start' }}>
                {c.ok
                  ? <CheckCircle2 size={14} style={{ color: GS.success, marginTop: 2 }} />
                  : <XCircle size={14} style={{ color: GS.danger, marginTop: 2 }} />}
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: GS.text, fontSize: 12 }}>{c.label}</div>
                  <div style={{ color: c.ok ? GS.textSubtle : GS.danger, fontFamily: MONO, fontSize: 11, overflowWrap: 'anywhere' }}>{c.detail}</div>
                </div>
              </div>
            ))}
          </section>

          <section className="gs-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <PanelTitle>Choose an attack</PanelTitle>
            <div role="radiogroup" aria-label="Attack" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {attacks.map((a) => {
                const on = a.key === picked
                return (
                  <button
                    key={a.key}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    disabled={active}
                    onClick={() => setPicked(a.key)}
                    style={{
                      textAlign: 'left', cursor: active ? 'not-allowed' : 'pointer', borderRadius: 10, padding: '12px 14px',
                      border: `1px solid ${on ? GS.primary : GS.border}`, background: on ? `${GS.primary}0d` : GS.surface,
                      display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '4px 12px', minHeight: 44,
                    }}
                  >
                    <span style={{ color: GS.text, fontWeight: 600, fontSize: 13 }}>{a.name}</span>
                    <span style={{ color: GS.warn, fontFamily: MONO, fontSize: 11, justifySelf: 'end' }}>
                      {on && useControl ? 'expect no incident' : a.expected_label}
                    </span>
                    <span style={{ color: GS.textMuted, fontFamily: MONO, fontSize: 11 }}>
                      {a.source_host} {a.source_ip} → {a.target}
                    </span>
                    <span style={{ color: GS.textFaint, fontFamily: MONO, fontSize: 10, justifySelf: 'end' }}>{a.script}</span>
                    <span style={{ color: GS.textSubtle, fontSize: 12, gridColumn: '1 / -1' }}>{a.sends}</span>
                  </button>
                )
              })}
            </div>

            <label style={{
              display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 12px', borderRadius: 10,
              border: `1px dashed ${GS.borderStrong}`, cursor: controlAvailable && !active ? 'pointer' : 'not-allowed',
              opacity: controlAvailable ? 1 : 0.6,
            }}>
              <input
                type="checkbox"
                checked={useControl}
                disabled={!controlAvailable || active}
                onChange={(e) => setControl(e.target.checked)}
                style={{ width: 16, height: 16, marginTop: 2 }}
              />
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ color: GS.text, fontSize: 12, fontWeight: 600 }}>
                  Negative control{controlAvailable ? ` (${selected.control_flag})` : ''}
                </span>
                <span style={{ color: GS.textSubtle, fontSize: 11 }}>
                  {controlAvailable ? selected.control_note : 'Pick a single attack to run its control.'}
                </span>
              </span>
            </label>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
              <button
                type="button"
                id="simulation-start"
                onClick={start}
                disabled={startDisabled}
                style={primaryBtn(GS.danger, startDisabled)}
              >
                {sending || active ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                {active ? 'Running…' : 'Simulate'}
              </button>
              <button type="button" onClick={stop} disabled={!active || role !== 'admin'} style={secondaryBtn(!active || role !== 'admin')}>
                <Square size={12} /> Stop run
              </button>
            </div>
            {(blocked || failedChecks.length > 0) && !active && (
              <div role="note" style={{ color: GS.textSubtle, fontFamily: MONO, fontSize: 11 }}>
                {blocked || 'Fix the failed preflight checks above to start a run.'}
              </div>
            )}
            {heldBy.length > 0 && !active && heldBy.map((msg) => <Notice key={msg} color={GS.warn}>{msg}</Notice>)}
            {startError && <Notice color={GS.danger}>{String(startError)}</Notice>}
          </section>
        </div>

        {/* ── Right: run progress, script output, results ── */}
        <div style={{ flex: '999 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <section className="gs-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
              <PanelTitle>Run</PanelTitle>
              <span style={{ color: GS.textFaint, fontFamily: MONO, fontSize: 11 }}>
                {run ? `#${run.id} · ${run.attack}${run.control ? ' (control)' : ''} · ${run.status} · by ${run.started_by}` : 'No run yet'}
              </span>
            </div>
            {steps.length === 0 && (
              <span style={{ color: GS.textSubtle, fontSize: 12 }}>Pick an attack and press Simulate. Progress appears here.</span>
            )}
            {steps.map((s) => (
              <div key={s.key} style={{ display: 'grid', gridTemplateColumns: '18px minmax(0, 1fr)', gap: 10, alignItems: 'start' }}>
                <StepIcon state={s.state} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: GS.text, fontSize: 13, fontWeight: 600 }}>
                    {attacks.find((a) => a.key === s.key)?.name || s.key}
                    <span style={{ color: GS.textSubtle, fontWeight: 400, fontFamily: MONO, fontSize: 11, marginLeft: 8 }}>
                      {PHASE_LABELS[s.state] || s.state}
                      {s.state === 'scoring' && secondsLeft !== null ? ` · up to ${secondsLeft}s` : ''}
                    </span>
                  </div>
                  {s.result && s.state !== 'traffic' && s.state !== 'scoring' && (
                    <div style={{ color: s.result.incident ? GS.text : GS.textMuted, fontSize: 12, marginTop: 2 }}>
                      {describeResult(s.result)}
                      {s.result.incident && <> <Link to="/alerts" style={{ color: GS.primary }}>Open in Alert Centre</Link></>}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {run?.error && <Notice color={GS.danger}>{run.error}</Notice>}
            {steps.some((s) => s.result?.incident) && (
              <div style={{ color: GS.textSubtle, fontSize: 11, fontFamily: MONO }}>
                * The label is a port and volume heuristic, not a model output: v1 decides only threat or not.
              </div>
            )}
          </section>

          <section className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid rgba(17,20,26,0.08)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Crosshair size={13} style={{ color: GS.textMuted }} />
              <span style={{ color: GS.textMuted, fontFamily: MONO, fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Script output
              </span>
            </div>
            <div
              aria-live="polite"
              style={{ padding: '10px 14px', fontFamily: MONO, fontSize: 12, lineHeight: 1.6, maxHeight: 360, minHeight: 160, overflow: 'auto', background: GS.surfaceRaised }}
            >
              {!run?.log?.length && <div style={{ color: GS.textFaint }}>Output appears here line by line as the script prints it.</div>}
              {(run?.log || []).map((e, i) => (
                <div key={`${e.t}-${i}`} style={{ color: LOG_COLORS[e.kind] || GS.text, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                  {e.line}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function PanelTitle({ children }) {
  return (
    <h2 style={{ margin: 0, color: GS.text, fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
      {children}
    </h2>
  )
}

function Notice({ color, children }) {
  return (
    <div role="alert" style={{ border: `1px solid ${color}40`, background: `${color}0d`, color, borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
      {children}
    </div>
  )
}

function StepIcon({ state }) {
  if (state === 'done') return <CheckCircle2 size={16} style={{ color: GS.success }} />
  if (state === 'failed' || state === 'stopped') return <XCircle size={16} style={{ color: GS.danger }} />
  if (state === 'traffic' || state === 'scoring') return <Loader2 size={16} className="animate-spin" style={{ color: GS.warn }} />
  return <Circle size={16} style={{ color: GS.borderStrong }} />
}

function primaryBtn(color, disabled) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 40, padding: '0 20px', borderRadius: 8,
    border: `1px solid ${color}60`, background: `${color}18`, color, fontFamily: MONO, fontSize: 12, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
  }
}

function secondaryBtn(disabled) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 40, padding: '0 16px', borderRadius: 8,
    border: `1px solid ${GS.borderStrong}`, background: 'transparent', color: GS.textMuted, fontFamily: MONO, fontSize: 12,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
  }
}
