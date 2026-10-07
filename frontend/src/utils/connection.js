// [Windows] GraphSentinel
// utils/connection — the rules behind the connection badge and the socket's
// reconnection schedule, kept free of React, the store and socket.io so they can
// be tested with `node --test` (frontend/tests/unit/connection.test.js).

// ── Socket reconnection schedule ─────────────────────────────────────────────
// Five fast retries at the interval the app always used, then exponential
// backoff from 5 s doubling to a 30 s ceiling, with no limit on attempts. It
// used to stop for good after five (about ten seconds), and only a page reload
// brought the live feed back.
export const FAST_RETRIES = 5
export const FAST_RETRY_MS = 2000
export const BACKOFF_START_MS = 5000
export const BACKOFF_MAX_MS = 30000

/** Delay before reconnection attempt `attempt` (1-based). */
export function reconnectDelay(attempt) {
  if (attempt <= FAST_RETRIES) return FAST_RETRY_MS
  return Math.min(BACKOFF_START_MS * 2 ** (attempt - FAST_RETRIES - 1), BACKOFF_MAX_MS)
}

/** 'reconnecting' during the fast retries, 'lost' once they are exhausted. */
export function socketStatusFor(attempt) {
  return attempt <= FAST_RETRIES ? 'reconnecting' : 'lost'
}

// ── What a failed or successful poll means for the connection mode ───────────
// Audit B21: the mode follows whether the backend ANSWERS, not whether a socket
// once shook hands. 'mock' is the never-reached state and blanks the panels;
// 'offline' is "it was answering and has stopped", and keeps the last data on
// screen marked stale.
export function modeAfterPoll(mode, graphOk) {
  if (graphOk) return 'live'
  if (mode === 'connecting') return 'mock'
  if (mode === 'live') return 'offline'
  return mode
}

// ── What the badge says ──────────────────────────────────────────────────────
// One label from two facts: whether REST is answering (mode) and what the
// socket is doing (socketStatus). With REST answering and the socket down the
// data is still current, by polling, so the badge says that and not "lost".
export function connectionDisplay(mode, socketStatus = 'idle') {
  if (mode === 'connecting') return { key: 'connecting', label: 'Connecting' }
  if (mode === 'mock') return { key: 'mock', label: 'Offline' }
  if (mode === 'offline') {
    if (socketStatus === 'reconnecting') return { key: 'reconnecting', label: 'Reconnecting…' }
    return { key: 'lost', label: 'Connection lost, retrying' }
  }
  if (socketStatus === 'reconnecting') return { key: 'reconnecting', label: 'Reconnecting…' }
  if (socketStatus === 'lost') return { key: 'polling', label: 'Live (polling), socket retrying' }
  return { key: 'live', label: 'Live' }
}

// ── The simulate control ─────────────────────────────────────────────────────
// Simulate runs the real attack scripts (mininet/demo/attacks) on the live
// topology, through the backend: no synthetic flows are sent from here. So:
//   * only an admin may start one (the backend enforces it as well);
//   * it needs a backend that is answering: a build with no backend
//     (VITE_USE_MOCK=true) or one that has gone quiet has nothing to run on.
export const SIMULATION_ROLE_REASON =
  'Only an admin can start an attack simulation: it sends real traffic through the switch.'
export const SIMULATION_MOCK_REASON =
  'This build talks to no backend (VITE_USE_MOCK=true): simulations run on the live topology.'
export const SIMULATION_OFFLINE_REASON = 'The backend is not answering: there is nothing to run the attack on.'

/** null when a simulation may be started, otherwise why not. `role` is the
 *  signed-in user's role; leave it out to check only the build and backend. */
export function simulationBlockedReason(useMock, mode, role) {
  if (role !== undefined && role !== 'admin') return SIMULATION_ROLE_REASON
  if (useMock) return SIMULATION_MOCK_REASON
  return mode === 'live' ? null : SIMULATION_OFFLINE_REASON
}

// ── What the stale-data badge says ───────────────────────────────────────────
export const STALE_RESOURCE_LABELS = {
  graph: 'graph',
  alerts: 'alerts',
  blocked: 'blocked IPs',
  forensics: 'forensics',
  stats: 'stats',
  timeline: 'timeline',
  health: 'health',
  enforcement: 'enforcement log',
  healing: 'healing events',
}

/** The badge text for a set of per-resource fetch errors, or null when none is
 *  stale. Up to three are named with their reason. When the backend is down
 *  all nine fail together, and naming each one made a ~200-character badge in
 *  a 48 px header (FE-03): every slot stale reads "all (<reason>)", more than
 *  three reads "<n> of <total> feeds (<reasons>)". */
export function staleBadgeText(dataErrors) {
  const entries = Object.entries(dataErrors || {})
  const stale = entries.filter(([, err]) => err)
  if (stale.length === 0) return null
  const reasons = [...new Set(stale.map(([, err]) => err))].join(', ')
  if (stale.length === entries.length && entries.length > 3) return `all (${reasons})`
  if (stale.length > 3) return `${stale.length} of ${entries.length} feeds (${reasons})`
  return stale.map(([name, err]) => `${STALE_RESOURCE_LABELS[name] || name} (${err})`).join(', ')
}

// ── Why a fetch failed, for the stale-data badge ─────────────────────────────
// "HTTP 500" when the server answered with an error, "no answer" when it did not.
export function fetchErrorLabel(err) {
  const status = err?.response?.status
  if (status) return `HTTP ${status}`
  if (err?.code === 'ECONNABORTED') return 'timed out'
  return 'no answer'
}
