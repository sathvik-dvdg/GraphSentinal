// [Windows] GraphSentinel — Susheep
// Shared event-timestamp formatter (Error.md #37): a bare HH:MM:SS is
// ambiguous once event history spans more than a day. Use this anywhere an
// event/incident/tx timestamp is displayed — NOT for live clocks or short
// rolling-window chart tick labels, which legitimately want time-only.

// Backend timestamps come from SQLite, which drops timezone info — several
// endpoints (alerts, healing, enforcement-actions, blocked) serialise
// `created_at` as a naive string like "2026-09-03T19:07:30.123456" with no
// Z / +00:00. `new Date()` then parses that as *local* time, so a UTC value
// gets shown ~hours off (e.g. an incident created "now" in IST shows as
// yesterday evening). These values are always UTC — tag them so before
// parsing. Strings that already carry an offset ("...Z", "...+00:00") or
// aren't in this shape are left untouched.
const NAIVE_DT = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/

export function parseTimestamp(timestamp) {
  if (timestamp == null || timestamp === '') return null
  let s = String(timestamp).trim()
  if (NAIVE_DT.test(s)) s = s.replace(' ', 'T') + 'Z'
  const date = new Date(s)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatEventTimestamp(timestamp) {
  const date = parseTimestamp(timestamp)
  if (!date) return '—'
  const datePart = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const timePart = date.toLocaleTimeString()
  return `${datePart} ${timePart}`
}

// Chart tick labels (timeline x-axis): the backend now returns ISO datetimes
// for every bucket (Error.md #16) instead of pre-formatted HH:MM strings —
// deliberately, so the UI decides the format. A short "MMM D HH:MM" keeps
// ticks compact while still resolving the day, since some timeline views
// span up to 7 days where bare HH:MM would repeat and be ambiguous.
export function formatTimelineTick(timestamp) {
  const date = parseTimestamp(timestamp)
  if (!date) return ''
  const datePart = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const timePart = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `${datePart} ${timePart}`
}
