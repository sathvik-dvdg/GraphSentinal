// [Windows] GraphSentinel
// utils/hostState -- how a host's status reads on the Network Topology page.
// Free of React and the store so it can be tested with `node --test`
// (frontend/tests/unit/hostState.test.js).
//
// The app carries seven statuses (normal, suspicious, infected, malicious,
// attacking, isolated, blocked). The page reduces them to four states an
// operator can act on: nothing to do, keep an eye on it, it is attacking, and
// it has been cut off. An unknown status is shown as "watching" rather than
// "healthy": a status this file does not know must not read as all clear.

export const STATE_ORDER = ['threat', 'watching', 'contained', 'healthy']

export const HOST_STATES = {
  threat:    { key: 'threat',    label: 'Active threat', tile: 'Active threats', graphStatus: 'malicious' },
  watching:  { key: 'watching',  label: 'Watching',      tile: 'Being watched',  graphStatus: 'suspicious' },
  contained: { key: 'contained', label: 'Isolated',      tile: 'Isolated',       graphStatus: 'blocked' },
  healthy:   { key: 'healthy',   label: 'Healthy',       tile: 'Healthy',        graphStatus: 'normal' },
}

const STATE_OF_STATUS = {
  normal: 'healthy',
  suspicious: 'watching',
  infected: 'watching',
  malicious: 'threat',
  attacking: 'threat',
  isolated: 'contained',
  blocked: 'contained',
}

export function stateOf(status) {
  return STATE_OF_STATUS[status] || 'watching'
}

/** Hosts for the page: the hierarchy's merged status (alerts, healing feed and
 *  the live blocked set already applied) joined with the graph's own fields. */
export function buildHosts(hierarchyChildren, graphNodes) {
  const byId = new Map((graphNodes || []).map((n) => [n.id, n]))
  return (hierarchyChildren || []).map((child) => {
    const live = byId.get(child.ip) || {}
    return {
      id: child.ip,
      label: child.label || child.ip,
      status: child.status,
      state: stateOf(child.status),
      threatScore: typeof live.threat_score === 'number' ? live.threat_score : null,
      attackType: live.attack_type || null,
      isBlocked: Boolean(live.is_blocked) || stateOf(child.status) === 'contained',
      connections: live.connections ?? null,
      bytesTotal: live.bytes_total ?? null,
      source: live.source || child.source || null,
    }
  })
}

export function countStates(hosts) {
  const counts = { threat: 0, watching: 0, contained: 0, healthy: 0 }
  for (const h of hosts) counts[h.state] += 1
  return counts
}

const plural = (n, one, many) => (n === 1 ? one : many)

/** The sentence that opens the page, and the line under it. */
export function describeNetwork(hosts) {
  const total = hosts.length
  if (total === 0) {
    return { headline: 'No hosts on the network yet.', detail: 'Start the monitor and the hosts appear here.' }
  }
  const c = countStates(hosts)
  const parts = []
  parts.push(c.threat === 0 ? 'No active threats.' : `${c.threat} active ${plural(c.threat, 'threat', 'threats')}.`)
  if (c.contained > 0) {
    parts.push(`${c.contained} of ${total} ${plural(total, 'host', 'hosts')} ${plural(c.contained, 'is', 'are')} isolated.`)
  }
  const watching = hosts.filter((h) => h.state === 'watching').map((h) => h.label)
  let detail
  if (c.threat > 0) {
    const names = hosts.filter((h) => h.state === 'threat').map((h) => h.label).join(', ')
    detail = `${names} ${plural(c.threat, 'is', 'are')} attacking now. Select a host to see why and what to do.`
  } else if (watching.length > 0) {
    detail = `${watching.join(', ')} ${plural(watching.length, 'is', 'are')} being watched. Select a host to see why.`
  } else {
    const rest = total - c.contained
    detail = c.contained > 0
      ? `The other ${rest} ${plural(rest, 'host is', 'hosts are')} behaving normally.`
      : `All ${total} ${plural(total, 'host is', 'hosts are')} behaving normally.`
  }
  return { headline: parts.join(' '), detail }
}

/** Why a host is in its state, in one sentence. */
export function describeReason(host) {
  if (host.state === 'healthy') return 'No unusual traffic.'
  const score = typeof host.threatScore === 'number' ? host.threatScore.toFixed(2) : null
  if (host.attackType && score) return `${host.attackType} scored ${score} on the v1 detector.`
  if (host.attackType) return `Flagged as ${host.attackType}.`
  if (score) return `Scored ${score} on the v1 detector.`
  return 'No detector score is on record for this host.'
}

/** The newest healing event for an address, or null. */
export function latestEventFor(ip, events) {
  let best = null
  for (const ev of events || []) {
    if (ev.ip !== ip) continue
    if (!best || String(ev.timestamp) > String(best.timestamp)) best = ev
  }
  return best
}

/** What the system did about a host, in one sentence. */
export function describeAction(host, events, formatTime = (iso) => iso) {
  const ev = latestEventFor(host.id, events)
  if (host.state === 'contained') {
    return ev
      ? `Isolated at ${formatTime(ev.timestamp)}. Enforcement: ${ev.enforcement_status}.`
      : 'Isolated. The healing feed has no record of when.'
  }
  if (host.state === 'threat') return 'Not isolated yet.'
  if (host.state === 'watching') return 'No action taken. The host is kept under watch.'
  return 'Nothing to do.'
}

/** A timestamp as a clock time, or the text itself when it is not a date. */
export function formatClock(iso) {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return String(iso ?? '')
  return new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}
