// [Windows] GraphSentinel — Susheep
// REST polling hook — fallback when WebSocket is down
// § 4.5: Sets connectionMode instead of isMockMode
import { useEffect, useCallback } from 'react'
import { getGraph, getAlerts, getBlocked, getForensics, getStats, getTimeline, getHierarchy } from '../services/api'
import useGraphStore from '../store/useGraphStore'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export function useGraphData() {
  const {
    setGraphData,
    setAlerts,
    setBlockedIPs,
    setChainTxs,
    updateStats,
    setConnectionMode,
    setTimeline,
    setOrgHierarchy,
    connectionMode,
  } = useGraphStore()

  const fetchAll = useCallback(async () => {
    if (USE_MOCK) {
      setConnectionMode('mock')
      return
    }

    // Don't overwrite data during an active simulation
    if (connectionMode === 'simulating') return

    try {
      const [graphRes, alertsRes, blockedRes, forensicsRes, statsRes, timelineRes, hierarchyRes] =
        await Promise.allSettled([
          getGraph(),
          getAlerts(),
          getBlocked(),
          getForensics(),
          getStats(),
          getTimeline(),
          getHierarchy(),
        ])

      if (graphRes.status === 'fulfilled') {
        // At least one successful response — we're live
        if (connectionMode !== 'simulating') {
          setConnectionMode('live')
          setGraphData(graphRes.value)
        }
      } else {
        // Graph endpoint failed — switch to mock if not already live via socket
        if (connectionMode === 'connecting') {
          setConnectionMode('mock')
        }
      }

      // Only update remaining fields if not simulating
      if (connectionMode === 'simulating') return

      if (alertsRes.status === 'fulfilled') setAlerts(alertsRes.value.alerts)
      if (blockedRes.status === 'fulfilled') setBlockedIPs(blockedRes.value.blocked_ips)
      if (forensicsRes.status === 'fulfilled') {
        // § 4.6: blockchain_records is [] when Ganache is offline — not null
        setChainTxs(forensicsRes.value.blockchain_records ?? [])
      }
      if (statsRes.status === 'fulfilled') updateStats(statsRes.value)
      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value.data_points)
      if (hierarchyRes.status === 'fulfilled') setOrgHierarchy(hierarchyRes.value)
    } catch {
      console.warn('[useGraphData] Backend unavailable — switching to mock mode')
      if (connectionMode === 'connecting') {
        setConnectionMode('mock')
      }
    }
  }, [
    connectionMode,
    setGraphData,
    setAlerts,
    setBlockedIPs,
    setChainTxs,
    updateStats,
    setConnectionMode,
    setTimeline,
    setOrgHierarchy
  ])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  return { refresh: fetchAll }
}
