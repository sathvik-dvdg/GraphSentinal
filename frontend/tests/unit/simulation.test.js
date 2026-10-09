// Run from frontend/:  node --test tests/unit/simulation.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { mergeRun, stepStates, describeResult, scoringSecondsLeft } from '../../src/utils/simulation.js'

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
