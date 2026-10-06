// Run from frontend/:  node --test tests/unit
import test from 'node:test'
import assert from 'node:assert/strict'

import { ATTACK_TYPES, attackTypeOptions } from '../../src/utils/attackTypes.js'

test('FE-11: every label the backend can send is known, DoSHulk and Manual included', () => {
  for (const t of ['DDoS', 'PortScan', 'SSHBrute', 'Botnet', 'DoSHulk', 'Manual', 'Heuristic', 'Unknown']) {
    assert.ok(ATTACK_TYPES.includes(t), t)
  }
})

test('FE-11: the common types are always offered, the rare ones only when present', () => {
  assert.deepEqual(attackTypeOptions([]), ['DDoS', 'PortScan', 'SSHBrute', 'DoSHulk', 'Botnet', 'Manual'])
  assert.ok(attackTypeOptions(['Heuristic']).includes('Heuristic'))
  assert.ok(!attackTypeOptions(['DDoS']).includes('Unknown'))
})

test('FE-11: a label this list does not know still gets a filter', () => {
  assert.deepEqual(attackTypeOptions(['NewThing', 'DDoS']).slice(-1), ['NewThing'])
})
