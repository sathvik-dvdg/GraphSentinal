// Run from frontend/:  node --test tests/unit
import test from 'node:test'
import assert from 'node:assert/strict'

import { mergeGraph } from '../../src/utils/graphMerge.js'

const full = () => ({
  nodes: [{ id: 'a', threat_score: 0.1, x: 5 }, { id: 'b', threat_score: 0.2 }, { id: 'c', threat_score: 0.3 }],
  links: [{ source: 'a', target: 'b', value: 1 }, { source: 'b', target: 'c', value: 1 }],
})

test('FE-10: a full graph replaces what is on screen, keeping node objects', () => {
  const cur = full()
  const a = cur.nodes[0]
  const next = mergeGraph(cur, { nodes: [{ id: 'a', threat_score: 0.9 }], links: [] })
  assert.equal(next.nodes.length, 1)
  assert.equal(next.nodes[0], a)                 // same object: layout kept
  assert.equal(next.nodes[0].threat_score, 0.9)
  assert.equal(next.nodes[0].x, 5)
})

test('FE-10: a capped push updates the hosts it carries and keeps the rest', () => {
  const cur = full()
  const next = mergeGraph(cur, {
    truncated: true,
    nodes: [{ id: 'c', threat_score: 0.97, status: 'malicious' }, { id: 'd', threat_score: 0.8 }],
    links: [{ source: 'c', target: 'd', value: 0.97 }],
  })
  assert.deepEqual(next.nodes.map((n) => n.id), ['a', 'b', 'c', 'd'])
  assert.equal(next.nodes.find((n) => n.id === 'c').threat_score, 0.97)   // newest score shown
  assert.equal(next.links.length, 3)                                       // nothing dropped
})

test('FE-10: a capped push updates a link whose ends the renderer replaced with objects', () => {
  const cur = full()
  cur.links[1] = { source: cur.nodes[1], target: cur.nodes[2], value: 1 }  // as react-force-graph leaves it
  const next = mergeGraph(cur, { truncated: true, nodes: [], links: [{ source: 'b', target: 'c', value: 0.9 }] })
  assert.equal(next.links.length, 2)
  const bc = next.links.find((l) => (l.source.id || l.source) === 'b')
  assert.equal(bc.value, 0.9)
  assert.equal(bc.source, cur.nodes[1])          // object kept for the renderer
})
