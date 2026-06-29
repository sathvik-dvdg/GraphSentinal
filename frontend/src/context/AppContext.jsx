// [Windows] GraphSentinel — Susheep
// AppContext — thin bridge over useGraphStore so pages can use useApp()
// State lives in Zustand; this context re-exports it for convenience.
import { createContext, useContext } from 'react'
import useGraphStore from '../store/useGraphStore'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const {
    connectionMode,
    setConnectionMode,
    alerts,
    graphData,
    healingEvents,
    chainTxs,
    stats,
    healingNodeId,
    timeline,
    use3D,
    selectedNode,
    forensicsOpen,
    setForensicsOpen,
    addAlert,
    setAlerts,
    setGraphData,
    setHealingNode,
    addHealingEvent,
    addTimelinePoint,
    updateStats,
    setChainTxs,
    toggleView,
    setSelectedNode,
    setConnected,
    isConnected,
  } = useGraphStore()

  // Derive simulationActive from connectionMode
  const simulationActive = connectionMode === 'simulating'
  const setSimulationActive = (active) => {
    if (active) {
      setConnectionMode('simulating')
    } else {
      setConnectionMode(isConnected ? 'live' : 'mock')
    }
  }

  const networkHealth = Math.max(0, Math.min(100, stats.system_health ?? 100))

  return (
    <AppContext.Provider value={{
      // Simulation
      simulationActive,
      setSimulationActive,
      connectionMode,
      setConnectionMode,
      // Data
      threats: alerts,
      alerts,
      nodes: graphData.nodes,
      graphData,
      healingEvents,
      blockchainRecords: chainTxs,
      chainTxs,
      stats,
      timeline,
      networkHealth,
      healingNodeId,
      // UI state
      use3D,
      selectedNode,
      forensicsOpen,
      // Setters
      setForensicsOpen,
      addAlert,
      setAlerts,
      setGraphData,
      setHealingNode,
      addHealingEvent,
      addTimelinePoint,
      updateStats,
      setChainTxs,
      toggleView,
      setSelectedNode,
      setConnected,
      isConnected,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)
