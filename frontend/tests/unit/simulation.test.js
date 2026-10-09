// Run from frontend/:  node --test tests/unit/simulation.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { mergeRun, stepStates, describeResult, scoringSecondsLeft, verdictFor, stagesFor } from '../../src/utils/simulation.js'

const line = (t, text) => ({ t, kind: 'out', line: text })

test('a socket push (log tail) never shortens the log a GET loaded', () => {
  const full = { id: 3, status: 'running', log: [line('1', 'a'), line('2', 'b'), line('3', 'c')] }
  const push = { id: 3, status: 'running', phase: 'scoring', log: [line('3', 'c'), line('4', 'd')] }
  const merged = mergeRun(full, push)
  assert.deepEqual(merged.log.map((e) => e.line), ['a', 'b', 'c', 'd'])
  assert.equal(merged.phase, 'scoring')
})

test('a new run replaces the old one, and no update keeps what is there', () => {
  const old = { id: 1, log: [line('1', 'old')] }
  assert.equal(mergeRun(old, { id: 2, log: [] }).id, 2)
  assert.equal(mergeRun(old, null), old)
  assert.equal(mergeRun(null, null), null)
})

test('steps follow the run: current phase, then done or failed', () => {
  const run = {
    active: true, status: 'running', current: 'portscan', phase: 'traffic',
    steps: ['flood', 'portscan', 'bruteforce'],
    results: [
      { attack: 'flood', exit_code: 0, incident: { id: 1 } },
      { attack: 'portscan', exit_code: null, incident: null },
    ],
  }
  assert.deepEqual(stepStates(run).map((s) => s.state), ['done', 'traffic', 'pending'])
  const failed = { ...run, active: false, status: 'failed', current: null, results: [{ attack: 'flood', exit_code: 1 }] }
  assert.equal(stepStates(failed)[0].state, 'failed')
  const stopped = { ...run, active: false, status: 'stopped', current: null }
  assert.deepEqual(stepStates(stopped).map((s) => s.state), ['done', 'stopped', 'pending'])
})

test('a result says what happened, including the expected silence of a control', () => {
  const hit = { source_ip: '10.0.0.2', exit_code: 0, incident: { id: 7, threat_score: 0.861, is_blocked: true, enforcement_status: 'simulated', attack_type: 'DDoS' } }
  assert.match(describeResult(hit), /Incident #7: 10\.0\.0\.2 scored 0\.86, blocked \(simulated\)\. Label DDoS\*/)
  assert.match(describeResult({ source_ip: '10.0.0.2', exit_code: 0, control: true, incident: null, score: 0.021 }), /as expected.*Latest v1 score 0\.02/)
  assert.match(describeResult({ source_ip: '10.0.0.3', exit_code: 0, control: false, incident: null, score: 0.7 }), /Latest v1 score 0\.70.*below the threshold/)
  assert.match(describeResult({ source_ip: '10.0.0.3', exit_code: 0, control: false, incident: null, score: null }), /never appeared in a scored batch/)
  assert.match(describeResult({ exit_code: 2 }), /code 2/)
})

test('the scoring countdown runs only while scoring', () => {
  const run = { active: true, phase: 'scoring', phase_started_at: '2026-10-06T10:00:00Z', score_wait_seconds: 20 }
  assert.equal(scoringSecondsLeft(run, Date.parse('2026-10-06T10:00:05Z')), 15)
  assert.equal(scoringSecondsLeft(run, Date.parse('2026-10-06T10:01:00Z')), 0)
  assert.equal(scoringSecondsLeft({ ...run, phase: 'traffic' }, 0), null)
})

test('verdict: a control that stays quiet matches what was expected', () => {
  const v = verdictFor({ attack: 'portscan', source_ip: '10.0.0.3', control: true, exit_code: 0, incident: null, score: 0.04 })
  assert.equal(v.tone, 'ok')
  assert.equal(v.title, 'No incident, as expected.')
})

test('verdict: a control that raises an incident is flagged, not celebrated', () => {
  const v = verdictFor({ attack: 'portscan', source_ip: '10.0.0.3', control: true, exit_code: 0, incident: { id: 4, threat_score: 0.9 }, score: 0.9 })
  assert.equal(v.tone, 'warn')
})

test('verdict: an attack with an incident is detected, one without is not', () => {
  const caught = verdictFor({ attack: 'flood', source_ip: '10.0.0.2', control: false, exit_code: 0, incident: { id: 7, threat_score: 0.93, attack_type: 'DDoS', is_blocked: true, enforcement_status: 'simulated' }, score: 0.93 })
  assert.equal(caught.tone, 'caught')
  const low = verdictFor({ attack: 'flood', source_ip: '10.0.0.2', control: false, exit_code: 0, incident: null, score: 0.4 })
  assert.equal(low.tone, 'warn')
  assert.equal(low.title, 'Below the threshold so far.')
  const unseen = verdictFor({ attack: 'flood', source_ip: '10.0.0.2', control: false, exit_code: 0, incident: null, score: null })
  assert.equal(unseen.title, 'The switch did not show this traffic.')
})

test('verdict: a failed script, an unfinished one and no result', () => {
  assert.equal(verdictFor({ attack: 'flood', source_ip: '10.0.0.2', exit_code: 2 }).tone, 'fail')
  assert.equal(verdictFor({ attack: 'flood', source_ip: '10.0.0.2', exit_code: null }).tone, 'pending')
  assert.equal(verdictFor(null), null)
})

test('stages: a finished control walks all four stages to a quiet outcome', () => {
  const step = { key: 'portscan', state: 'done', result: { attack: 'portscan', source_ip: '10.0.0.3', control: true, exit_code: 0, incident: null, score: 0.04 } }
  const stages = stagesFor(step, 0.75)
  assert.deepEqual(stages.map((s) => s.state), ['done', 'done', 'done', 'done'])
  assert.equal(stages[2].text, 'Score 0.04 against a threshold of 0.75.')
  assert.equal(stages[3].text, 'No incident, as expected.')
})

test('stages: an attack the switch never showed stops at the switch', () => {
  const step = { key: 'flood', state: 'done', result: { attack: 'flood', source_ip: '10.0.0.2', control: false, exit_code: 0, incident: null, score: null } }
  const stages = stagesFor(step, 0.75)
  assert.equal(stages[0].state, 'done')
  assert.equal(stages[1].state, 'warn')
  assert.equal(stages[2].state, 'warn')
  assert.equal(stages[3].state, 'warn')
})

test('stages: while scoring, the first stage is done and the third is active', () => {
  const step = { key: 'flood', state: 'scoring', result: { attack: 'flood', source_ip: '10.0.0.2', exit_code: 0, incident: null, score: null } }
  const stages = stagesFor(step, null)
  assert.deepEqual(stages.map((s) => s.state), ['done', 'active', 'active', 'pending'])
})

test('stages: a failed script leaves the rest unreached', () => {
  const step = { key: 'flood', state: 'failed', result: { attack: 'flood', source_ip: '10.0.0.2', exit_code: 2, incident: null, score: null } }
  const stages = stagesFor(step, 0.75)
  assert.equal(stages[0].state, 'failed')
  assert.equal(stages[1].state, 'pending')
  assert.equal(stages[3].state, 'failed')
})

test('stages: a step not started has nothing yet', () => {
  assert.deepEqual(stagesFor({ key: 'x', state: 'pending', result: null }).map((s) => s.state), ['pending', 'pending', 'pending', 'pending'])
})
