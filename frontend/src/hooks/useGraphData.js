// [Windows] GraphSentinel — Susheep
// REST polling hook — fallback when WebSocket is down
import { useEffect, useCallback } from 'react'
import { getGraph, getAlerts, getBlocked, getForensics, getStats, getTimeline } from '../services/api'
import useGraphStore from '../store/useGraphStore'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export function useGraphData() {
  const {
    setGraphData,
    setAlerts,
    setBlockedIPs,
    setChainTxs,
    updateStats,
    setMockMode,
    setTimeline,
  } = useGraphStore()

  const fetchAll = useCallback(async () => {
    if (USE_MOCK) return

    try {
      const [graphRes, alertsRes, blockedRes, forensicsRes, statsRes, timelineRes] =
        await Promise.allSettled([
          getGraph(),
          getAlerts(),
          getBlocked(),
          getForensics(),
          getStats(),
          getTimeline(),
        ])

      if (graphRes.status === 'fulfilled') {
        setGraphData(graphRes.value)
        setMockMode(false)
      }
      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.alerts)
      }
      if (blockedRes.status === 'fulfilled') {
        setBlockedIPs(blockedRes.value.blocked_ips)
      }
      if (forensicsRes.status === 'fulfilled') {
        setChainTxs(forensicsRes.value.blockchain_records)
      }
      if (statsRes.status === 'fulfilled') {
        updateStats(statsRes.value)
      }
      if (timelineRes.status === 'fulfilled') {
        setTimeline(timelineRes.value.data_points)
      }
    } catch (e) {
      console.warn('[useGraphData] Backend unavailable — keeping mock data')
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  return { refresh: fetchAll }
}
