// Run from frontend/:  node --test tests/unit/scene3d.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { layoutHosts, turn, SCENE } from '../../src/utils/scene3d.js'

const hosts = (n) => Array.from({ length: n }, (_, i) => ({ id: `10.0.0.${i + 1}`, label: `h${i + 1}` }))

test('every host gets a place, painted from the back of the floor to the front', () => {
  const placed = layoutHosts(hosts(10))
  assert.equal(placed.length, 10)
  for (let i = 1; i < placed.length; i += 1) assert.ok(placed[i].y >= placed[i - 1].y)
})

test('ten hosts: four behind the switch, six in front (the two level with it count as in front)', () => {
  const placed = layoutHosts(hosts(10))
  assert.equal(placed.filter((p) => p.back).length, 4)
  assert.equal(placed.filter((p) => !p.back).length, 6)
})

test('a full turn lands every host where it started', () => {
  const key = (placed) => placed.map((p) => `${p.host.id}:${p.x}:${p.y}`).sort().join('|')
  assert.equal(key(layoutHosts(hosts(10), 0)), key(layoutHosts(hosts(10), 360)))
})

test('turning by one step moves each host to its neighbour\'s place', () => {
  const at = (rot) => Object.fromEntries(layoutHosts(hosts(10), rot).map((p) => [p.host.id, [p.x, p.y]]))
  const a = at(0)
  const b = at(36)
  assert.deepEqual(b['10.0.0.2'], a['10.0.0.3'])
})

test('nearer hosts are drawn larger, and no host stands under the controller', () => {
  const placed = layoutHosts(hosts(10))
  const front = placed[placed.length - 1]
  const back = placed[0]
  assert.ok(front.size > back.size)
  for (const p of placed) assert.ok(Math.abs(p.x - SCENE.cx) > 20)
})

test('the marker stands one stem above its floor point, and the link points at it', () => {
  const [p] = layoutHosts(hosts(3))
  assert.equal(p.my, p.y - SCENE.stem)
  assert.ok(p.link.length > 0)
})

test('no hosts, no layout; and rotation wraps both ways', () => {
  assert.deepEqual(layoutHosts([]), [])
  assert.equal(turn(0, -36), 324)
  assert.equal(turn(324, 36), 0)
  assert.equal(turn(10, 360), 10)
})
