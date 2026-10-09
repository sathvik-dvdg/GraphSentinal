// Run from frontend/:  node --test tests/unit
import test from 'node:test'
import assert from 'node:assert/strict'

import { escapeHtml } from '../../src/utils/escapeHtml.js'

test('the graph tooltip cannot be given markup', () => {
  assert.equal(escapeHtml('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;')
  assert.equal(escapeHtml(`a"b'c&d`), 'a&quot;b&#39;c&amp;d')
  assert.equal(escapeHtml('10.0.0.1'), '10.0.0.1')
  assert.equal(escapeHtml(null), '')
  assert.equal(escapeHtml(undefined), '')
})
