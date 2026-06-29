// [Windows] GraphSentinel — Susheep
// useAlerts — aggregates threats + healing events into a unified alert feed
import { useMemo } from 'react'
import useGraphStore from '../store/useGraphStore'

const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2 }

function mapThreatToAlert(alert) {
  return {
    id: `threat-${alert.id}`,
    title: `${alert.attack_type || 'Attack'} from ${alert.source_ip}`,
    severity: alert.severity === 'critical' ? 'critical' : alert.severity === 'warning' ? 'warning' : 'info',
    source: 'threat_feed',
    status: alert.is_blocked ? 'resolved' : 'open',
    nodeIp: alert.source_ip,
    relatedRoute: '/threats',
    assignee: null,
    createdAt: new Date(alert.timestamp).getTime(),
    acknowledgedAt: null,
    raw: alert,
  }
}

function mapHealingToAlert(event) {
  return {
    id: `heal-${event.id}`,
    title: `Node ${event.ip} auto-isolated (${event.action})`,
    severity: 'warning',
    source: 'self_healing',
    status: 'acknowledged',
    nodeIp: event.ip,
    relatedRoute: '/healing',
    assignee: null,
    createdAt: new Date(event.timestamp).getTime(),
    acknowledgedAt: new Date(event.timestamp).getTime(),
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

    // Sort by severity then time (newest first)
    return merged.sort((a, b) => {
      const sevDiff = (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
      if (sevDiff !== 0) return sevDiff
      return b.createdAt - a.createdAt
    })
  }, [alerts, healingEvents])

  const stats = useMemo(() => {
    const open = unified.filter((a) => a.status === 'open').length
    const acked = unified.filter((a) => a.status === 'acknowledged').length
    const resolved = unified.filter((a) => a.status === 'resolved').length

    // MTTA: mean time to acknowledge (open alerts excluded)
    const ackedAlerts = unified.filter((a) => a.acknowledgedAt && a.status !== 'open')
    const mttaMs = ackedAlerts.length > 0
      ? ackedAlerts.reduce((sum, a) => sum + (a.acknowledgedAt - a.createdAt), 0) / ackedAlerts.length
      : 0
    const mttaMin = Math.round(mttaMs / 60000)

    return { open, acked, resolved, total: unified.length, mttaMin }
  }, [unified])

  return { alerts: unified, stats }
}
