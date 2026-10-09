// [Windows] GraphSentinel
// useBlockHost -- isolate or release a host through the same /api/v1/block
// endpoint the node drawer uses, then refresh the views that show the result.
// A refusal is returned as text for the panel to show; nothing is faked.
import { useCallback, useState } from 'react'
import useGraphStore from '../store/useGraphStore'
import useSessionUser from './useSessionUser'
import { blockIP, getGraph, getBlocked, getStats, getHealingEvents } from '../services/api'
import { canEnforce, enforceFailureMessage } from '../utils/triage'

export default function useBlockHost() {
  const setGraphData = useGraphStore((s) => s.setGraphData)
  const setBlockedIPs = useGraphStore((s) => s.setBlockedIPs)
  const updateStats = useGraphStore((s) => s.updateStats)
  const setHealingEvents = useGraphStore((s) => s.setHealingEvents)
  const addHealingEvent = useGraphStore((s) => s.addHealingEvent)
  const mayEnforce = canEnforce(useSessionUser().role)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async (ip, action) => {
    if (!ip || busy || !mayEnforce) return
    setBusy(true)
    setError(null)
    try {
      const res = await blockIP(ip, action)
      if (res?.healing_event) addHealingEvent(res.healing_event)
      const [graphRes, blockedRes, statsRes, healingRes] = await Promise.allSettled([
        getGraph(), getBlocked(), getStats(), getHealingEvents(),
      ])
      if (graphRes.status === 'fulfilled') setGraphData(graphRes.value)
      if (blockedRes.status === 'fulfilled') setBlockedIPs(blockedRes.value.blocked_ips)
      if (statsRes.status === 'fulfilled') updateStats(statsRes.value)
      if (healingRes.status === 'fulfilled') setHealingEvents(healingRes.value.events)
    } catch (err) {
      setError(enforceFailureMessage(err))
    } finally {
      setBusy(false)
    }
  }, [busy, mayEnforce, addHealingEvent, setGraphData, setBlockedIPs, updateStats, setHealingEvents])

  return { run, busy, error, clearError: () => setError(null), mayEnforce }
}
