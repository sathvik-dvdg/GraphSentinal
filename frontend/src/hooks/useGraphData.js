// [Windows] GraphSentinel — Susheep
// REST polling hook — fallback when WebSocket is down
// § 4.5: Sets connectionMode instead of isMockMode
import { useEffect, useCallback } from 'react'
import { getGraph, getAlerts, getBlocked, getForensics, getStats, getTimeline } from '../services/api'
import useGraphStore from '../store/useGraphStore'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// Error.md #22/#26: each resource is tracked independently. A failed fetch
// deliberately leaves that resource's last-known data in place (blanking a
// security panel on a transient error would misleadingly read as "all
// clear") but records the failure in dataErrors so the UI can mark that
// specific panel stale instead of silently presenting old data as current.
const RESOURCE_FETCHERS = {
  graph: { fetch: getGraph, apply: (v, s) => s.setGraphData(v) },
  alerts: { fetch: getAlerts, apply: (v, s) => s.setAlerts(v.alerts) },
  blocked: { fetch: getBlocked, apply: (v, s) => s.setBlockedIPs(v.blocked_ips) },
  forensics: {
    fetch: getForensics,
    apply: (v, s) => {
      s.setChainTxs(v.blockchain_records ?? [])
      s.setChainId(v.chain_id ?? null)
    },
  },
  stats: { fetch: getStats, apply: (v, s) => s.updateStats(v) },
  timeline: { fetch: getTimeline, apply: (v, s) => s.setTimeline(v.data_points) },
}

export function useGraphData() {
  const { setConnectionMode, connectionMode } = useGraphStore()

  const fetchAll = useCallback(async () => {
    if (USE_MOCK) {
      setConnectionMode('mock')
      return
    }

    // Don't overwrite data during an active simulation
    if (connectionMode === 'simulating') return

    const entries = Object.entries(RESOURCE_FETCHERS)
    const results = await Promise.allSettled(entries.map(([, r]) => r.fetch()))

    const store = useGraphStore.getState()
    if (store.connectionMode === 'simulating') return // may have started mid-fetch

    const graphIndex = entries.findIndex(([name]) => name === 'graph')
    if (results[graphIndex].status === 'fulfilled') {
      setConnectionMode('live')
    } else if (connectionMode === 'connecting') {
      setConnectionMode('mock')
    }

    entries.forEach(([name, resource], i) => {
      const result = results[i]
      if (result.status === 'fulfilled') {
        resource.apply(result.value, store)
        store.setDataError(name, null)
      } else {
        store.setDataError(name, result.reason?.message || 'request failed')
      }
    })
  }, [connectionMode, setConnectionMode])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  return { refresh: fetchAll }
}
