// Run from frontend/:  node --test tests/unit
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  alertStatusOf, overlayAfterFetch, canEnforce, enforceFailureMessage, ENFORCE_DENIED_REASON,
  canTriage, triageFailureMessage, TRIAGE_DENIED_REASON,
} from '../../src/utils/triage.js'

test('B17: a blocked alert with no triage is open, not resolved', () => {
  assert.equal(alertStatusOf({ is_blocked: true }), 'open')
  assert.equal(alertStatusOf({ is_blocked: true, alert_status: 'open' }), 'open')
  assert.equal(alertStatusOf({ is_blocked: false }), 'open')
})

test('B17: the triage state a person set is kept, blocked or not', () => {
  assert.equal(alertStatusOf({ is_blocked: true, alert_status: 'acknowledged' }), 'acknowledged')
  assert.equal(alertStatusOf({ is_blocked: false, alert_status: 'resolved' }), 'resolved')
})

test('B19: after a successful fetch the overlay keeps only ids still in flight', () => {
  assert.deepEqual(overlayAfterFetch([1, 2, 3], [2]), [2])
  assert.deepEqual(overlayAfterFetch([1, 2, 3], []), [])
})

test('B19: an incident the server reopened is no longer hidden by this device', () => {
  const overlay = overlayAfterFetch([7], [])          // resolved here last week; PATCH long settled
  const server = { id: 7, alert_status: 'open' }      // reopened on the server
  const isResolved = server.alert_status === 'resolved' || overlay.includes(server.id)
  assert.equal(isResolved, false)
})

test('B20: only the admin role may block or unblock', () => {
  assert.equal(canEnforce('admin'), true)
  for (const role of ['readonly', 'operator', '', undefined, null]) assert.equal(canEnforce(role), false)
})

test('B20: a refused block says why, and that nothing changed', () => {
  assert.equal(enforceFailureMessage({ response: { status: 403 } }), ENFORCE_DENIED_REASON)
  assert.match(enforceFailureMessage({ response: { status: 500 } }), /HTTP 500.*Nothing was changed/)
  assert.match(enforceFailureMessage(new Error('Network Error')), /did not answer.*Nothing was changed/)
})

test('FE-24: triage is allowed for every role the backend accepts, not readonly', () => {
  assert.equal(canTriage('admin'), true)
  assert.equal(canTriage('operator'), true)
  assert.equal(canTriage('readonly'), false)
  assert.equal(canTriage(null), false)       // backend: "Role could not be determined"
  assert.equal(canTriage(undefined), false)
})

test('FE-24: a failed triage says why, in words', () => {
  assert.ok(triageFailureMessage({ response: { status: 403 } }).includes(TRIAGE_DENIED_REASON))
  assert.match(triageFailureMessage({ response: { status: 401 } }), /session has ended/)
  assert.match(triageFailureMessage({ response: { status: 500 } }), /HTTP 500/)
  assert.match(triageFailureMessage(new Error('Network Error')), /did not answer/)
})

