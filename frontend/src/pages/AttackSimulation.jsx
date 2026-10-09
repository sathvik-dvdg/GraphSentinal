// [Windows] GraphSentinel
// AttackSimulation -- the Simulate console. A run starts one of the real scripts
// in mininet/demo/attacks on the live topology through the backend
// (POST /api/v1/simulations); nothing here builds or sends a flow. What the
// dashboard shows afterwards is what the switch saw and v1 scored.
//
// The page reads in three steps: is the network ready, what do you send, what
// came of it. The state and the calls live here; the steps are components.
import { useCallback, useEffect, useState } from 'react'
import useGraphStore from '../store/useGraphStore'
import useSessionUser from '../hooks/useSessionUser'
import ReadinessCard from '../components/simulation/ReadinessCard'
import AttackPicker, { Notice } from '../components/simulation/AttackPicker'
import ResultPanel from '../components/simulation/ResultPanel'
import { getSimulations, startSimulation, stopSimulation, getSettings } from '../services/api'
import { simulationBlockedReason } from '../utils/connection'
import { stepStates, scoringSecondsLeft } from '../utils/simulation'
import { GS } from '../constants/colors'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

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
  // v1's threshold, for the score meter. Null until the backend answers, and the
  // meter then draws the score without a threshold rather than guessing one.
  const [threshold, setThreshold] = useState(null)

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

  useEffect(() => {
    getSettings()
      .then((res) => setThreshold(typeof res?.threat_threshold === 'number' ? res.threat_threshold : null))
      .catch(() => setThreshold(null))
  }, [])

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
  const thresholdText = typeof threshold === 'number' ? threshold : 'the threshold'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 1440 }}>
      <header className="gs-rise" style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 820 }}>
        <h1 style={{ fontSize: 34, lineHeight: '40px', textWrap: 'balance' }}>
          Send a test attack and see whether the detector catches it.
        </h1>
        <p style={{ fontSize: 15, lineHeight: '23px', color: GS.textMuted, maxWidth: '68ch' }}>
          This runs a real script from <code style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>mininet/demo/attacks</code> on
          the live network. Nothing is faked: an incident appears only if switch s1 carried the traffic and v1 scored it
          over {thresholdText}.
        </p>
      </header>

      {loadError && <Notice color={GS.danger}>{String(loadError)}</Notice>}

      <div className="gs-sim-layout">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0 }}>
          <div className="gs-rise" style={{ '--i': 1 }}><ReadinessCard preflight={preflight} /></div>
          <div className="gs-rise" style={{ '--i': 2 }}>
            <AttackPicker
              attacks={attacks}
              picked={picked}
              onPick={setPicked}
              blockers={blockers}
              onControl={setControl}
              selected={selected}
              controlAvailable={controlAvailable}
              useControl={useControl}
              threshold={threshold}
              active={active}
              sending={sending}
              startDisabled={startDisabled}
              onStart={start}
              onStop={stop}
              canStop={active && role === 'admin'}
              blockedReason={blocked}
              failedChecks={failedChecks}
              heldBy={heldBy}
              startError={startError}
            />
          </div>
        </div>

        <div className="gs-rise" style={{ '--i': 3, minWidth: 0 }}>
          <ResultPanel run={run} steps={steps} attacks={attacks} threshold={threshold} secondsLeft={secondsLeft} />
        </div>
      </div>
    </div>
  )
}
