// [Windows] GraphSentinel — Susheep
// Error.md U7 / H5 / H7 — alert acknowledge/resolve and incident "Mark
// Resolved" have no backend, so they used to live in component-local React
// state and reset on every refresh. Until a real PATCH /api/v1/alerts/{id}/status
// endpoint exists, persist the operator's triage state in localStorage so it
// survives a reload and is shared between the Alert Centre, the Sidebar unread
// badge, the useAlerts MTTA stat, and the Forensics incident list. Still
// per-browser, not per-account — the UI says so ("saved on this device").
//
// Shape: { [alertId]: { status: 'acknowledged'|'resolved'|'open', at: <ms epoch> } }
// A bare string value is also tolerated (older writes) and read as { status }.

const ALERT_KEY = 'gs_alert_statuses'
const INCIDENT_KEY = 'gs_resolved_incident_ids'

function safeParse(raw, fallback) {
  try {
    const v = JSON.parse(raw)
    return v ?? fallback
  } catch {
    return fallback
  }
}

/** Returns { [id]: { status, at } } — normalises legacy bare-string entries. */
export function loadAlertStatuses() {
  if (typeof localStorage === 'undefined') return {}
  let raw
  try {
    raw = localStorage.getItem(ALERT_KEY)
  } catch {
    return {}
  }
  const parsed = safeParse(raw, {}) || {}
  const out = {}
  for (const [id, v] of Object.entries(parsed)) {
    out[id] = typeof v === 'string' ? { status: v, at: null } : { status: v?.status, at: v?.at ?? null }
  }
  return out
}

export function saveAlertStatuses(map) {
  try {
    localStorage.setItem(ALERT_KEY, JSON.stringify(map || {}))
  } catch {
    /* private mode / quota — non-fatal, just won't persist */
  }
}

/** Set one alert's status, stamping `at` when it moves to acknowledged. */
export function setAlertStatus(prev, id, status) {
  const next = { ...(prev || {}) }
  next[id] = { status, at: status === 'acknowledged' ? Date.now() : (next[id]?.at ?? null) }
  saveAlertStatuses(next)
  return next
}

/** Drop one alert's local entry — called once the server has accepted the
 *  change (Error.md H5), so localStorage only ever holds un-synced optimism. */
export function clearAlertStatus(prev, id) {
  if (!prev || !(id in prev)) return prev || {}
  const next = { ...prev }
  delete next[id]
  saveAlertStatuses(next)
  return next
}

export function loadResolvedIncidentIds() {
  if (typeof localStorage === 'undefined') return []
  try {
    const v = safeParse(localStorage.getItem(INCIDENT_KEY), [])
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export function saveResolvedIncidentIds(ids) {
  try {
    localStorage.setItem(INCIDENT_KEY, JSON.stringify(Array.isArray(ids) ? ids : []))
  } catch {
    /* non-fatal */
  }
}
