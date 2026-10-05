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
// screen marked stale. A running simulation is never interrupted.
export function modeAfterPoll(mode, graphOk) {
  if (mode === 'simulating') return mode
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
  if (mode === 'simulating') return { key: 'simulating', label: 'SIMULATION' }
  if (mode === 'connecting') return { key: 'connecting', label: 'CONNECTING' }
  if (mode === 'mock') return { key: 'mock', label: 'OFFLINE' }
  if (mode === 'offline') {
    if (socketStatus === 'reconnecting') return { key: 'reconnecting', label: 'RECONNECTING…' }
    return { key: 'lost', label: 'CONNECTION LOST — RETRYING' }
  }
  if (socketStatus === 'reconnecting') return { key: 'reconnecting', label: 'RECONNECTING…' }
  if (socketStatus === 'lost') return { key: 'polling', label: 'LIVE (POLLING) — SOCKET RETRYING' }
  return { key: 'live', label: 'LIVE' }
}

// ── The simulate control ─────────────────────────────────────────────────────
// A simulation posts SYNTHETIC flows to the real backend, which scores them and
// records what follows as real incidents. So:
//   * it is absent from the pages that show the historical record, which must
//     never be read alongside a button that adds synthetic events to it;
//   * on a live backend it is disabled unless the build was started for demo
//     use (VITE_USE_MOCK=true), with the reason said, not hidden.
export const SIMULATION_FREE_ROUTES = ['/forensics', '/blockchain', '/timeline']

export function simulationHiddenOn(pathname) {
  return SIMULATION_FREE_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`))
}

export const SIMULATION_BLOCKED_REASON =
  'Simulation is disabled on a live backend: it would add synthetic flows to the real incident record.'

/** null when a simulation may be started, otherwise why not. */
export function simulationBlockedReason(useMock, mode) {
  if (useMock) return null
  return mode === 'live' ? SIMULATION_BLOCKED_REASON : null
}

// ── Why a fetch failed, for the stale-data badge ─────────────────────────────
// "HTTP 500" when the server answered with an error, "no answer" when it did not.
export function fetchErrorLabel(err) {
  const status = err?.response?.status
  if (status) return `HTTP ${status}`
  if (err?.code === 'ECONNABORTED') return 'timed out'
  return 'no answer'
}
