// [Windows] GraphSentinel — Susheep
// useAlerts — aggregates threats + healing events into a unified alert feed
import { useMemo } from 'react'
import useGraphStore from '../store/useGraphStore'
import { loadAlertStatuses } from '../utils/alertStatus'
import { parseTimestamp } from '../utils/formatTimestamp'

const ms = (ts) => { const d = parseTimestamp(ts); return d ? d.getTime() : 0 }

const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2 }

// Error.md H5 — the incident id behind an alert. The /api/v1/alerts feed keys
// rows as "alert-<incidentId>"; that numeric id is what PATCH
// /api/v1/incidents/{id}/status needs.
function incidentIdOf(rawId) {
  const m = /(\d+)\s*$/.exec(String(rawId ?? ''))
  return m ? Number(m[1]) : null
}

function mapThreatToAlert(alert) {
  // Server-authoritative triage state (Error.md H5). A blocked host with no
  // explicit triage still reads as "resolved" — the threat was contained.
  const serverStatus = alert.alert_status && alert.alert_status !== 'open'
    ? alert.alert_status
    : (alert.is_blocked ? 'resolved' : 'open')
  return {
    id: `threat-${alert.id}`,
    incidentId: incidentIdOf(alert.id),
    title: `${alert.attack_type || 'Attack'} from ${alert.source_ip}`,
    severity: alert.severity === 'critical' ? 'critical' : alert.severity === 'warning' ? 'warning' : 'info',
    source: 'threat_feed',
    status: serverStatus,
    nodeIp: alert.source_ip,
    relatedRoute: '/threats',
    assignee: null,
    createdAt: ms(alert.timestamp),
    acknowledgedAt: alert.acknowledged_at ? ms(alert.acknowledged_at) : null,
    raw: alert,
  }
}

function mapHealingToAlert(event) {
  return {
    id: `heal-${event.id}`,
    incidentId: null, // healing notices aren't operator-resolvable rows
    title: `Node ${event.ip} auto-isolated (${event.action})`,
    severity: 'warning',
    source: 'self_healing',
    status: 'acknowledged',
    nodeIp: event.ip,
    relatedRoute: '/healing',
    assignee: null,
    createdAt: ms(event.timestamp),
    acknowledgedAt: ms(event.timestamp),
    raw: event,
  }
}

export function useAlerts() {
  const { alerts, healingEvents } = useGraphStore()

  const unified = useMemo(() => {
    const threatAlerts = alerts.map(mapThreatToAlert)
    const healingAlerts = healingEvents.map(mapHealingToAlert)

    // Deduplicate by id
    const seen = new Set()
    const merged = [...threatAlerts, ...healingAlerts].filter((a) => {
      if (seen.has(a.id)) return false
      seen.add(a.id)
      return true
    })

    // Error.md H5 — server `alert_status` (mapped above) is the base. Local
    // storage only holds *un-synced optimistic* writes (cleared once the PATCH
    // lands), so it wins only while a change is in flight or the backend was
    // unreachable.
    const persisted = loadAlertStatuses()
    const withTriage = merged.map((a) => {
      const p = persisted[a.id]
      if (!p?.status) return a
      return {
        ...a,
        status: p.status,
        acknowledgedAt: p.at ?? a.acknowledgedAt,
      }
    })

    // Sort by severity then time (newest first)
    return withTriage.sort((a, b) => {
      const sevDiff = (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
      if (sevDiff !== 0) return sevDiff
      return b.createdAt - a.createdAt
    })
  }, [alerts, healingEvents])

  const stats = useMemo(() => {
    const open = unified.filter((a) => a.status === 'open').length
    const acked = unified.filter((a) => a.status === 'acknowledged').length
    const resolved = unified.filter((a) => a.status === 'resolved').length

    // MTTA: mean time to acknowledge — only alerts an operator actually
    // acknowledged, with a recorded timestamp strictly after they were raised.
    const ackedAlerts = unified.filter(
      (a) => a.acknowledgedAt && a.status !== 'open' && a.acknowledgedAt > a.createdAt
    )
    const mttaMs = ackedAlerts.length > 0
      ? ackedAlerts.reduce((sum, a) => sum + (a.acknowledgedAt - a.createdAt), 0) / ackedAlerts.length
      : 0
    const mttaMin = Math.round(mttaMs / 60000)

    return { open, acked, resolved, total: unified.length, mttaMin, mttaSamples: ackedAlerts.length }
  }, [unified])

  return { alerts: unified, stats }
}
