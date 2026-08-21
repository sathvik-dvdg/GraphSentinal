// [Windows] GraphSentinel — Susheep
// Shared event-timestamp formatter (Error.md #37): a bare HH:MM:SS is
// ambiguous once event history spans more than a day. Use this anywhere an
// event/incident/tx timestamp is displayed — NOT for live clocks or short
// rolling-window chart tick labels, which legitimately want time-only.
export function formatEventTimestamp(timestamp) {
  if (!timestamp) return '—'
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '—'
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
  if (!timestamp) return ''
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''
  const datePart = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const timePart = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `${datePart} ${timePart}`
}
