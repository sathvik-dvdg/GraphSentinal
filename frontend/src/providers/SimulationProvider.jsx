import { useCallback, useEffect } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useGraphData } from '../hooks/useGraphData'
import useGraphStore from '../store/useGraphStore'

export default function SimulationProvider({ children }) {
  const {
    connectionMode,
    setGraphData,
    addAlert,
    setHealingNode,
    addHealingEvent,
    addTimelinePoint,
    setConnected,
  } = useGraphStore()

  const { refresh: refreshData } = useGraphData()

  const handleGraphUpdate = useCallback((data) => {
    if (connectionMode === 'simulating') return
    useGraphStore.getState().setConnectionMode('live')
    setGraphData(data)
  }, [connectionMode, setGraphData])

  const handleAlert = useCallback((alert) => {
    if (connectionMode === 'simulating') return
    addAlert(alert)
    addTimelinePoint({
      time: new Date().toLocaleTimeString().slice(0, 5),
      threats: 1,
      blocked: 0,
    })
  }, [addAlert, addTimelinePoint, connectionMode])

  const handleHealingTriggered = useCallback((event) => {
    setHealingNode(event.ip)
    addHealingEvent(event)
    addTimelinePoint({
      time: new Date().toLocaleTimeString().slice(0, 5),
      threats: 0,
      blocked: 1,
    })
  }, [setHealingNode, addHealingEvent, addTimelinePoint])

  useWebSocket({
    onGraphUpdate: handleGraphUpdate,
    onAlert: handleAlert,
    onHealingTriggered: handleHealingTriggered,
    onConnect: () => setConnected(true),
    onDisconnect: () => setConnected(false),
    onReconnect: () => refreshData(),
  })

  return children
}
