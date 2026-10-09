// Run from frontend/:  node --test tests/unit/hostState.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  stateOf, buildHosts, countStates, describeNetwork, describeReason, describeAction, latestEventFor,
} from '../../src/utils/hostState.js'

const host = (label, status, extra = {}) => ({
  id: `10.0.0.${label.slice(1)}`, label, status, state: stateOf(status),
  threatScore: null, attackType: null, isBlocked: false, ...extra,
})

test('seven statuses reduce to four states, and an unknown one is not "healthy"', () => {
  assert.equal(stateOf('normal'), 'healthy')
  assert.equal(stateOf('suspicious'), 'watching')
  assert.equal(stateOf('infected'), 'watching')
  assert.equal(stateOf('malicious'), 'threat')
  assert.equal(stateOf('attacking'), 'threat')
  assert.equal(stateOf('isolated'), 'contained')
  assert.equal(stateOf('blocked'), 'contained')
  assert.equal(stateOf('something-new'), 'watching')
})

test('buildHosts joins the hierarchy status with the live graph fields', () => {
  const children = [
    { ip: '10.0.0.2', label: 'h2', status: 'isolated' },
    { ip: '10.0.0.3', label: 'h3', status: 'normal' },
  ]
  const nodes = [{ id: '10.0.0.2', threat_score: 0.93, attack_type: 'DDoS', is_blocked: true, connections: 4 }]
  const hosts = buildHosts(children, nodes)
  assert.equal(hosts[0].state, 'contained')
  assert.equal(hosts[0].threatScore, 0.93)
  assert.equal(hosts[0].isBlocked, true)
  assert.equal(hosts[1].threatScore, null)
  assert.equal(hosts[1].isBlocked, false)
})

test('a host the hierarchy calls isolated counts as blocked even if the graph row is missing', () => {
  const [h] = buildHosts([{ ip: '10.0.0.9', label: 'h9', status: 'isolated' }], [])
  assert.equal(h.isBlocked, true)
})

test('counts add up to the number of hosts', () => {
  const hosts = [host('h1', 'normal'), host('h2', 'isolated'), host('h3', 'isolated'), host('h4', 'suspicious')]
  assert.deepEqual(countStates(hosts), { threat: 0, watching: 1, contained: 2, healthy: 1 })
})

test('headline: no threats, some isolated, one watched', () => {
  const hosts = [host('h1', 'normal'), host('h2', 'isolated'), host('h3', 'isolated'), host('h6', 'suspicious')]
  const { headline, detail } = describeNetwork(hosts)
  assert.equal(headline, 'No active threats. 2 of 4 hosts are isolated.')
  assert.equal(detail, 'h6 is being watched. Select a host to see why.')
})

test('headline: singular wording for one threat and one isolated host', () => {
  const hosts = [host('h1', 'normal'), host('h2', 'attacking'), host('h3', 'isolated')]
  const { headline, detail } = describeNetwork(hosts)
  assert.equal(headline, '1 active threat. 1 of 3 hosts is isolated.')
  assert.match(detail, /^h2 is attacking now/)
})

test('headline: quiet network and empty network', () => {
  assert.equal(describeNetwork([host('h1', 'normal'), host('h2', 'normal')]).headline, 'No active threats.')
  assert.equal(describeNetwork([]).headline, 'No hosts on the network yet.')
})

test('reason prefers the label and score, and says so when there is neither', () => {
  assert.equal(describeReason(host('h1', 'normal')), 'No unusual traffic.')
  assert.equal(describeReason(host('h2', 'isolated', { attackType: 'DDoS', threatScore: 0.934 })), 'DDoS scored 0.93 on the v1 detector.')
  assert.equal(describeReason(host('h6', 'suspicious', { threatScore: 0.5 })), 'Scored 0.50 on the v1 detector.')
  assert.equal(describeReason(host('h7', 'suspicious')), 'No detector score is on record for this host.')
})

test('the newest healing event for an address wins', () => {
  const events = [
    { ip: '10.0.0.2', timestamp: '2026-10-09T12:00:00Z', enforcement_status: 'simulated' },
    { ip: '10.0.0.2', timestamp: '2026-10-09T12:05:00Z', enforcement_status: 'enforced' },
    { ip: '10.0.0.3', timestamp: '2026-10-09T12:09:00Z', enforcement_status: 'enforced' },
  ]
  assert.equal(latestEventFor('10.0.0.2', events).enforcement_status, 'enforced')
  assert.equal(latestEventFor('10.0.0.8', events), null)
})

test('action text for isolated, watched, attacking and healthy hosts', () => {
  const events = [{ ip: '10.0.0.2', timestamp: 'T1', enforcement_status: 'simulated' }]
  const fmt = (iso) => `at(${iso})`
  assert.equal(describeAction(host('h2', 'isolated'), events, fmt), 'Isolated at at(T1). Enforcement: simulated.')
  assert.equal(describeAction(host('h4', 'isolated'), events, fmt), 'Isolated. The healing feed has no record of when.')
  assert.equal(describeAction(host('h5', 'attacking'), events, fmt), 'Not isolated yet.')
  assert.match(describeAction(host('h6', 'suspicious'), events, fmt), /kept under watch/)
  assert.equal(describeAction(host('h1', 'normal'), events, fmt), 'Nothing to do.')
})

test('formatClock gives a clock time for a date and passes other text through', async () => {
  const { formatClock } = await import('../../src/utils/hostState.js')
  assert.match(formatClock('2026-10-09T12:05:03Z'), /^\d{2}:\d{2}:\d{2}$/)
  assert.equal(formatClock('not a date'), 'not a date')
  assert.equal(formatClock(undefined), '')
})
