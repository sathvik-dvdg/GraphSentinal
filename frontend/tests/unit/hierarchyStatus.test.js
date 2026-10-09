// Run from frontend/:  node --test tests/unit/hierarchyStatus.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { currentlyBlocked, deriveStatusMap } from '../../src/utils/hierarchyStatus.js'

const isolatedEvent = (ip) => ({ id: `heal-${ip}`, ip, action: 'ISOLATED' })

test('a host with an old ISOLATED event that is no longer blocked is not drawn isolated', () => {
  const blockedNow = currentlyBlocked({ nodes: [{ id: '10.0.0.2', status: 'normal', is_blocked: false }] }, [])
  const map = deriveStatusMap({ healingEvents: [isolatedEvent('10.0.0.2')], blockedNow })
  assert.equal(map['10.0.0.2'], undefined)
})

test('a host that is blocked now is isolated, whether the graph or the blocked list says so', () => {
  const graph = { nodes: [{ id: '10.0.0.3', status: 'blocked', is_blocked: true }, { id: '10.0.0.4', status: 'normal', is_blocked: false }] }
  const blockedNow = currentlyBlocked(graph, [{ ip: '10.0.0.4' }])
  assert.deepEqual([...blockedNow].sort(), ['10.0.0.3', '10.0.0.4'])
  const map = deriveStatusMap({ healingEvents: [isolatedEvent('10.0.0.3'), isolatedEvent('10.0.0.4')], blockedNow })
  assert.equal(map['10.0.0.3'], 'isolated')
  assert.equal(map['10.0.0.4'], 'isolated')
})

test('only ISOLATED events isolate, and a host with no event is left to the live graph', () => {
  const blockedNow = new Set(['10.0.0.5'])
  const map = deriveStatusMap({ healingEvents: [{ ip: '10.0.0.5', action: 'RESTORED' }], blockedNow })
  assert.equal(map['10.0.0.5'], undefined)
})

test('alerts and manual overrides still apply', () => {
  const map = deriveStatusMap({
    alerts: [
      { source_ip: '10.0.0.6', severity: 'critical', is_blocked: false },
      { source_ip: '10.0.0.7', severity: 'warning', is_blocked: false },
    ],
    nodeOverrides: { '10.0.0.7': 'normal', '10.0.0.8': 'suspicious' },
    blockedNow: new Set(),
  })
  assert.equal(map['10.0.0.6'], 'attacking')
  assert.equal(map['10.0.0.7'], undefined)
  assert.equal(map['10.0.0.8'], 'suspicious')
})

test('missing data is handled', () => {
  assert.equal(currentlyBlocked(undefined, undefined).size, 0)
  assert.deepEqual(deriveStatusMap({}), {})
})
