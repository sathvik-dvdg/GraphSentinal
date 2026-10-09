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
  const score = typeof result.score === 'number' ? result.score.toFixed(2) : null
  if (result.control) {
    return `No incident for ${result.source_ip}, as expected for this control: v1 scores completed TCP conversations.`
      + (score ? ` Latest v1 score ${score}.` : '')
  }
  if (score === null) {
    return `No incident for ${result.source_ip}, and it never appeared in a scored batch: the switch did not show this traffic.`
  }
  return `No incident for ${result.source_ip} in the wait. Latest v1 score ${score}: it is still below the threshold, and may cross a little later.`
}

/** Seconds left of the scoring wait, or null outside it. `now` in ms. */
export function scoringSecondsLeft(run, now) {
  if (!run || !run.active || run.phase !== 'scoring' || !run.phase_started_at) return null
  const elapsed = (now - Date.parse(run.phase_started_at)) / 1000
  return Math.max(0, Math.ceil((run.score_wait_seconds ?? 20) - elapsed))
}

/** What a finished attack means for the operator, as a tone, a short title and
 *  the sentence describeResult gives. Tones: ok (a control stayed quiet),
 *  caught (an attack raised an incident), warn (no incident yet, or an
 *  unexpected one) and fail (the script did not run), or null before a result. */
export function verdictFor(result) {
  if (!result) return null
  const body = describeResult(result)
  if (result.exit_code === null) return { tone: 'pending', tag: 'Running', title: 'Not finished.', body }
  if (result.exit_code !== 0) return { tone: 'fail', tag: 'Script failed', title: 'The script did not run.', body }
  const incident = Boolean(result.incident)
  if (result.control) {
    return incident
      ? { tone: 'warn', tag: 'Unexpected', title: `A control raised an incident for ${result.source_ip}.`, body }
      : { tone: 'ok', tag: 'Matches what was expected', title: 'No incident, as expected.', body }
  }
  if (incident) return { tone: 'caught', tag: 'Detected', title: `Incident raised for ${result.source_ip}.`, body }
  const seen = typeof result.score === 'number'
  return {
    tone: 'warn',
    tag: 'Not detected',
    title: seen ? 'Below the threshold so far.' : 'The switch did not show this traffic.',
    body,
  }
}

/** The four things that happen in a run, in order, for one attack: the script
 *  sends traffic, the switch carries it, v1 scores it, and an outcome follows.
 *  `step` is one entry of stepStates(); `threshold` is v1's threshold or null.
 *  Each stage is { key, title, state: pending | active | done | warn | failed,
 *  text }. */
export function stagesFor(step, threshold = null) {
  const result = step?.result || null
  const state = step?.state || 'pending'
  const scored = typeof result?.score === 'number'
  const incident = Boolean(result?.incident)
  const finished = state === 'done' || state === 'failed' || state === 'stopped'
  const scriptFailed = result && result.exit_code !== null && result.exit_code !== 0

  const send = (() => {
    if (state === 'pending') return { state: 'pending', text: 'Waiting to start.' }
    if (state === 'traffic') return { state: 'active', text: 'The script is sending traffic.' }
    if (scriptFailed) return { state: 'failed', text: `The script exited with code ${result.exit_code}.` }
    return { state: 'done', text: 'The script ran to the end.' }
  })()

  const carry = (() => {
    if (state === 'pending' || state === 'traffic' || scriptFailed) return { state: 'pending', text: 'Not reached.' }
    if (state === 'scoring' && !scored && !incident) return { state: 'active', text: 'Waiting for the monitor to read s1.' }
    if (scored || incident) return { state: 'done', text: 'The monitor read it from s1 in a polled batch.' }
    return { state: 'warn', text: 'The switch did not show this traffic.' }
  })()

  const score = (() => {
    if (state === 'pending' || state === 'traffic' || scriptFailed) return { state: 'pending', text: 'Not reached.' }
    if (scored) {
      const against = typeof threshold === 'number' ? ` against a threshold of ${threshold}` : ''
      return { state: finished ? 'done' : 'active', text: `Score ${result.score.toFixed(2)}${against}.` }
    }
    if (state === 'scoring') return { state: 'active', text: 'Waiting for v1 to score it.' }
    return { state: 'warn', text: 'No score was recorded.' }
  })()

  const verdict = verdictFor(result)
  const outcome = (() => {
    if (!finished || !verdict) return { state: 'pending', text: 'Not reached.' }
    const tone = { ok: 'done', caught: 'done', warn: 'warn', fail: 'failed', pending: 'pending' }[verdict.tone]
    return { state: tone, text: verdict.title }
  })()

  return [
    { key: 'send', title: 'Script sent traffic', ...send },
    { key: 'carry', title: 'Switch carried it', ...carry },
    { key: 'score', title: 'v1 scored it', ...score },
    { key: 'outcome', title: 'Outcome', ...outcome },
  ]
}
