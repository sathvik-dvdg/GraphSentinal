// Run from frontend/:  node --test tests/unit/connection.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { reconnectDelay, socketStatusFor, modeAfterPoll, connectionDisplay } from '../../src/utils/connection.js'

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

test('B21: a backend never reached is "mock"; any answer makes it live; a simulation is left alone', () => {
  assert.equal(modeAfterPoll('connecting', false), 'mock')
  assert.equal(modeAfterPoll('mock', false), 'mock')
  assert.equal(modeAfterPoll('mock', true), 'live')
  assert.equal(modeAfterPoll('simulating', false), 'simulating')
  assert.equal(modeAfterPoll('simulating', true), 'simulating')
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
  assert.equal(connectionDisplay('simulating', 'lost').label, 'SIMULATION')
})
