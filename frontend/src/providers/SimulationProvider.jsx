import { useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useGraphData } from '../hooks/useGraphData'
import useGraphStore from '../store/useGraphStore'

export default function SimulationProvider({ children }) {
  const {
    setGraphData,
    addAlert,
    setHealingNode,
    addHealingEvent,
    addTimelinePoint,
    setConnected,
    setSocketStatus,
  } = useGraphStore()

  const { refresh: refreshData } = useGraphData()

  // Error.md #1 — read connectionMode from getState() at call time rather than
  // closing over it via a dep array. The "don't clobber during a simulation"
  // guard no longer depends on the useCallback deps being kept in sync.
  const isSimulating = () => useGraphStore.getState().connectionMode === 'simulating'

  // Error.md #8 — realtime timeline points must use the same full ISO shape
  // the REST timeline endpoint returns (Error.md #16), otherwise
  // formatTimelineTick() gets `new Date("14:32")` → Invalid Date → blank tick.
  const nowIso = () => new Date().toISOString()

  const handleGraphUpdate = useCallback((data) => {
    if (isSimulating()) return
    useGraphStore.getState().setConnectionMode('live')
    setGraphData(data)
  }, [setGraphData])

  const handleAlert = useCallback((alert) => {
    if (isSimulating()) return
    addAlert(alert)
    addTimelinePoint({ time: nowIso(), threats: 1, blocked: 0 })
  }, [addAlert, addTimelinePoint])

  const handleHealingTriggered = useCallback((event) => {
    setHealingNode(event.ip)
    addHealingEvent(event)
    addTimelinePoint({ time: nowIso(), threats: 0, blocked: 1 })
  }, [setHealingNode, addHealingEvent, addTimelinePoint])

  useWebSocket({
    onGraphUpdate: handleGraphUpdate,
    onAlert: handleAlert,
    onHealingTriggered: handleHealingTriggered,
    // The socket no longer decides the connection mode (audit B21): on either
    // edge, poll at once and let the answer say whether the backend is there.
    // (onConnect covers a reconnect too, so onReconnect is not passed: it would
    // fetch everything twice.)
    onConnect: () => { setConnected(true); refreshData() },
    onDisconnect: () => { setConnected(false); refreshData() },
    onStatus: setSocketStatus,
  })

  return children
}
