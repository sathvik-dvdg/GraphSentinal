// [Windows] GraphSentinel
// utils/hierarchyStatus -- which hosts the Org Hierarchy draws as isolated,
// attacking or infected. Free of React and the store so it can be tested with
// `node --test` (frontend/tests/unit/hierarchyStatus.test.js).
//
// The healing feed (GET /api/v1/healing) is HISTORY: one ISOLATED row for every
// block ever made, and unblocks are not in it. The hierarchy used to mark every
// host with such a row as isolated and let that override the live graph, so a
// host that had been unblocked (or whose block record was gone) stayed
// "ISOLATED" until its event scrolled out of the newest 50.

/** Hosts that are blocked NOW, from the live graph and the blocked list. */
export function currentlyBlocked(graphData, blockedIPs) {
  const set = new Set()
  for (const node of graphData?.nodes || []) {
    if (node.is_blocked || node.status === 'blocked') set.add(node.id)
  }
  for (const entry of blockedIPs || []) {
    if (entry?.ip) set.add(entry.ip)
  }
  return set
}

/** { ip -> status } overriding what the live graph says about a node. */
export function deriveStatusMap({ alerts = [], healingEvents = [], nodeOverrides = {}, blockedNow = new Set() }) {
  const map = {}

  // A healing event isolates a host only while the host is still blocked.
  healingEvents.forEach((ev) => {
    if (ev.action === 'ISOLATED' && blockedNow.has(ev.ip)) map[ev.ip] = 'isolated'
  })

  // Critical non-isolated alerts -> attacking; warnings -> infected.
  alerts.forEach((alert) => {
    const ip = alert.source_ip
    if (map[ip] === 'isolated') return
    if (alert.severity === 'critical' && !alert.is_blocked) {
      map[ip] = 'attacking'
    } else if (alert.severity === 'warning' && !map[ip]) {
      map[ip] = 'infected'
    }
  })

  // Manual overrides win; 'normal' falls back to the node's own status.
  Object.entries(nodeOverrides).forEach(([ip, status]) => {
    if (status === 'normal') delete map[ip]
    else if (status) map[ip] = status
  })

  return map
}
