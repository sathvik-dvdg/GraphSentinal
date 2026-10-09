// [Windows] GraphSentinel
// utils/triage — the three rules behind audit items B17, B19 and B20, kept free
// of React and the store so they can be tested with `node --test`
// (frontend/tests/unit/triage.test.js).

// B17 — blocking is an enforcement state, not a triage state. An alert stays
// open until a person acknowledges or resolves it; `is_blocked` is shown
// beside it as its own indicator. Mapping a blocked alert to "resolved" made
// it impossible to acknowledge or reopen.
export function alertStatusOf(alert) {
  return alert?.alert_status || 'open'
}

// B19 — the server wins. The locally resolved ids are an optimistic overlay,
// not a second source of truth: after a successful fetch the server's status
// is known, so the overlay keeps only ids whose PATCH is still in flight.
export function overlayAfterFetch(overlayIds, inFlightIds) {
  const inFlight = new Set(inFlightIds || [])
  return (overlayIds || []).filter((id) => inFlight.has(id))
}

// B20 — block and unblock need the admin role (backend: require_admin_privilege).
// The control is shown disabled with this reason, never enabled-and-refused:
// an enabled button that returns 403 to the console leaves the operator
// believing the action was taken.
export const ENFORCE_DENIED_REASON = 'An admin is required to block or unblock a node.'

export function canEnforce(role) {
  return role === 'admin'
}

// Why a block/unblock request failed, in words an operator can act on.
export function enforceFailureMessage(err) {
  const status = err?.response?.status
  if (status === 403) return ENFORCE_DENIED_REASON
  if (status === 401) return 'Your session has ended. Sign in again.'
  if (status) return `The backend refused the request (HTTP ${status}). Nothing was changed.`
  return 'The backend did not answer. Nothing was changed.'
}

// Triage (acknowledge / resolve) is allowed for every signed-in role except
// readonly (backend: require_write_privilege). A missing role is refused by
// the backend too ("Role could not be determined"), so it is refused here.
export const TRIAGE_DENIED_REASON = 'Your role is read-only: you can view alerts but not change their status.'

export function canTriage(role) {
  return Boolean(role) && role !== 'readonly'
}

// Why a triage change did not save. The change is then dropped on screen, so
// the row shows the server's status again instead of a local one that would
// otherwise win for ever (handover FE-24).
export function triageFailureMessage(err) {
  const status = err?.response?.status
  if (status === 403) return `Not saved: ${TRIAGE_DENIED_REASON}`
  if (status === 401) return 'Not saved: your session has ended. Sign in again.'
  if (status) return `Not saved: the backend refused the change (HTTP ${status}).`
  return 'Not saved: the backend did not answer. Try again when it is back.'
}
