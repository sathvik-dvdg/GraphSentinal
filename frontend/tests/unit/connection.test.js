// Run from frontend/:  node --test tests/unit/connection.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  reconnectDelay, socketStatusFor, modeAfterPoll, connectionDisplay,
  simulationBlockedReason, SIMULATION_ROLE_REASON, SIMULATION_MOCK_REASON, SIMULATION_OFFLINE_REASON,
  staleBadgeText,
} from '../../src/utils/connection.js'

test('reconnection: five fast retries, then 5 s doubling to a 30 s ceiling, forever', () => {
  assert.deepEqual([1, 2, 3, 4, 5].map(reconnectDelay), [2000, 2000, 2000, 2000, 2000])
  assert.deepEqual([6, 7, 8, 9, 10].map(reconnectDelay), [5000, 10000, 20000, 30000, 30000])
  assert.equal(reconnectDelay(500), 30000)
})

test('reconnection: "reconnecting" during the fast retries, "lost" after them', () => {
  assert.equal(socketStatusFor(1), 'reconnecting')
  assert.equal(socketStatusFor(5), 'reconnecting')
  assert.equal(socketStatusFor(6), 'lost')
})

test('B21: a failed poll after the backend was answering is "offline", not "mock" and not "live"', () => {
  assert.equal(modeAfterPoll('live', false), 'offline')
  assert.equal(modeAfterPoll('offline', false), 'offline')
  assert.equal(modeAfterPoll('offline', true), 'live')
})

test('B21: a backend never reached is "mock"; any answer makes it live', () => {
  assert.equal(modeAfterPoll('connecting', false), 'mock')
  assert.equal(modeAfterPoll('mock', false), 'mock')
  assert.equal(modeAfterPoll('mock', true), 'live')
})

test('badge: the two reconnection labels', () => {
  assert.equal(connectionDisplay('live', 'reconnecting').label, 'RECONNECTING…')
  assert.equal(connectionDisplay('offline', 'reconnecting').label, 'RECONNECTING…')
  assert.equal(connectionDisplay('offline', 'lost').label, 'CONNECTION LOST — RETRYING')
})

test('badge: never LIVE while the backend is not answering', () => {
  for (const socket of ['idle', 'connected', 'reconnecting', 'lost']) {
    assert.notEqual(connectionDisplay('offline', socket).key, 'live')
    assert.notEqual(connectionDisplay('mock', socket).key, 'live')
  }
})

test('badge: REST answering with the socket down is polling, not lost', () => {
  assert.equal(connectionDisplay('live', 'lost').key, 'polling')
  assert.equal(connectionDisplay('live', 'connected').label, 'LIVE')
})

test('Simulate runs real attacks: admin only, and only on a backend that answers', () => {
  assert.equal(simulationBlockedReason(false, 'live', 'readonly'), SIMULATION_ROLE_REASON)
  assert.equal(simulationBlockedReason(false, 'live', 'operator'), SIMULATION_ROLE_REASON)
  assert.equal(simulationBlockedReason(false, 'live', null), SIMULATION_ROLE_REASON)
  assert.equal(simulationBlockedReason(false, 'live', 'admin'), null)
  assert.equal(simulationBlockedReason(true, 'mock', 'admin'), SIMULATION_MOCK_REASON)
  assert.equal(simulationBlockedReason(false, 'offline', 'admin'), SIMULATION_OFFLINE_REASON)
  assert.equal(simulationBlockedReason(false, 'connecting', 'admin'), SIMULATION_OFFLINE_REASON)
  // Without a role argument only the build and backend are checked.
  assert.equal(simulationBlockedReason(false, 'live'), null)
})

const NINE = { graph: null, alerts: null, blocked: null, forensics: null, stats: null, timeline: null, health: null, enforcement: null, healing: null }

test('FE-03: the stale badge names up to three resources with their reason', () => {
  assert.equal(staleBadgeText(NINE), null)
  assert.equal(staleBadgeText({ ...NINE, alerts: 'HTTP 500' }), 'alerts (HTTP 500)')
  assert.equal(staleBadgeText({ ...NINE, alerts: 'HTTP 500', blocked: 'timed out' }), 'alerts (HTTP 500), blocked IPs (timed out)')
})

test('FE-03: the backend down collapses to "all", not a 200-character list', () => {
  const allDown = Object.fromEntries(Object.keys(NINE).map((k) => [k, 'no answer']))
  assert.equal(staleBadgeText(allDown), 'all (no answer)')
  const five = { ...NINE, graph: 'no answer', alerts: 'no answer', blocked: 'no answer', stats: 'HTTP 502', health: 'no answer' }
  assert.equal(staleBadgeText(five), '5 of 9 feeds (no answer, HTTP 502)')
})

test('FE-03: a per-page badge with every one of its few resources stale still names them', () => {
  assert.equal(staleBadgeText({ alerts: 'no answer', timeline: 'no answer' }), 'alerts (no answer), timeline (no answer)')
})

