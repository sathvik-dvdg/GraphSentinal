// [Windows] GraphSentinel
// utils/simulation — the rules behind the attack console (pages/AttackSimulation),
// free of React and the store so they can be tested with `node --test`
// (frontend/tests/unit/simulation.test.js).
//
// A run is what GET /api/v1/simulations returns as `current` and the socket
// pushes as `simulation_update`: the backend runs mininet/demo/attacks and
// reports what the script printed and what v1 recorded afterwards.

export const MAX_LOG_LINES = 400

const logKey = (e) => `${e.t}|${e.line}`

/** The run to show after an update. A socket push carries only the last lines
 *  of the log, a GET the whole of it: for the same run the lines are merged, so
 *  neither one shortens what is on screen. A different run replaces it. */
export function mergeRun(prev, next) {
  if (!next) return prev ?? null
  if (!prev || prev.id !== next.id) return next
  const seen = new Set((prev.log || []).map(logKey))
  const added = (next.log || []).filter((e) => !seen.has(logKey(e)))
  const log = [...(prev.log || []), ...added].slice(-MAX_LOG_LINES)
  return { ...next, log }
}

export const PHASE_LABELS = {
  traffic: 'Sending traffic',
  scoring: 'Waiting for v1 to score',
}

/** One row per attack in the run: 'pending' | 'traffic' | 'scoring' | 'done' |
 *  'failed' | 'stopped', with its result once there is one. */
export function stepStates(run) {
  if (!run) return []
  const results = run.results || []
  const byKey = Object.fromEntries(results.map((r) => [r.attack, r]))
  const last = results.length ? results[results.length - 1].attack : null
  return (run.steps || []).map((key) => {
    const result = byKey[key] || null
    let state = 'pending'
    if (run.active && run.current === key) state = run.phase
    else if (result) {
      if (run.status === 'stopped' && key === last) state = 'stopped'
      else if (result.exit_code !== null && result.exit_code !== 0) state = 'failed'
      else state = 'done'
    }
    return { key, state, result }
  })
}

/** What a finished attack came to, in one sentence. */
export function describeResult(result) {
  if (!result) return ''
  if (result.exit_code !== null && result.exit_code !== 0) return `The script exited with code ${result.exit_code}.`
  const inc = result.incident
  if (inc) {
    const score = typeof inc.threat_score === 'number' ? inc.threat_score.toFixed(2) : inc.threat_score
    return `Incident #${inc.id}: ${result.source_ip} scored ${score}, ${inc.is_blocked ? 'blocked' : 'not blocked'} (${inc.enforcement_status}). Label ${inc.attack_type}*.`
  }
  if (result.exit_code === null) return 'Not finished.'
  return result.control
    ? `No incident for ${result.source_ip}, as expected for this control: v1 scores completed TCP conversations.`
    : `No incident for ${result.source_ip}: v1 did not score it over the threshold in the wait.`
}

/** Seconds left of the scoring wait, or null outside it. `now` in ms. */
export function scoringSecondsLeft(run, now) {
  if (!run || !run.active || run.phase !== 'scoring' || !run.phase_started_at) return null
  const elapsed = (now - Date.parse(run.phase_started_at)) / 1000
  return Math.max(0, Math.ceil((run.score_wait_seconds ?? 20) - elapsed))
}
