// [Windows] GraphSentinel — Susheep
// AppShell — persistent layout: sidebar + topbar + page outlet
// WebSocket, simulateAttack, and NodeDetailPanel all live here so they
// survive navigation between routes without resetting.
import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import NodeDetailPanel from '../dashboard/NodeDetailPanel'
import ForensicsModal from '../dashboard/ForensicsModal'
import LoadingScreen from '../shared/LoadingScreen'
import { blockIP, getGraph, getBlocked, getStats, getHealingEvents } from '../../services/api'
import useGraphStore from '../../store/useGraphStore'

export default function AppShell() {
  const [sidebarPinned, setSidebarPinned] = useState(false)
  const [sidebarHovered, setSidebarHovered] = useState(false)
  const [showLoading, setShowLoading] = useState(true)
  const sidebarOpen = sidebarPinned || sidebarHovered

  // ── Zustand store ──────────────────────────────────────────────────
  const {
    selectedNode,
    forensicsOpen,
    setSelectedNode,
    setForensicsOpen,
    simulateAttack,
    stopSimulation,
    setGraphData,
    setBlockedIPs,
    updateStats,
    setHealingEvents,
    addHealingEvent,
  } = useGraphStore()

  // ── Initial loading splash ─────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setShowLoading(false), 1800)
    return () => clearTimeout(t)
  }, [])

  // Error.md #23/#26: refresh affected views immediately instead of waiting
  // for the next poll, and surface real failures instead of silently
  // pretending the action succeeded (the panel used to close either way).
  const handleBlock = async (ip, action) => {
    try {
      const blockRes = await blockIP(ip, action)
      if (blockRes?.healing_event) {
        addHealingEvent(blockRes.healing_event)
      }
      // Error.md #9/N4 — also refresh the healing feed so the Self-Healing
      // page reflects a manual block/unblock immediately instead of waiting
      // for the next 10s poll (the other views were already refreshed here).
      const [graphRes, blockedRes, statsRes, healingRes] = await Promise.allSettled([
        getGraph(), getBlocked(), getStats(), getHealingEvents(),
      ])
      if (graphRes.status === 'fulfilled') setGraphData(graphRes.value)
      if (blockedRes.status === 'fulfilled') setBlockedIPs(blockedRes.value.blocked_ips)
      if (statsRes.status === 'fulfilled') updateStats(statsRes.value)
      if (healingRes.status === 'fulfilled') setHealingEvents(healingRes.value.events)
      setSelectedNode(null)
    } catch (err) {
      console.error(`[AppShell] Failed to ${action} ${ip} — backend rejected or is unreachable:`, err)
      // Keep the panel open: the action did not take effect, so closing it
      // as if it succeeded would misrepresent the node's real state.
    }
  }

  if (showLoading) return <LoadingScreen />

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `${sidebarOpen ? '220px' : '64px'} 1fr`,
        gridTemplateRows: '48px 1fr',
        height: '100vh',
        overflow: 'hidden',
        transition: 'grid-template-columns 200ms ease',
        background: '#f4f6f8',
      }}
    >
      {/* Sidebar spans both rows */}
      <div style={{ gridRow: '1 / 3', gridColumn: 1 }}>
        <Sidebar
          expanded={sidebarOpen}
          pinned={sidebarPinned}
          onPinToggle={() => setSidebarPinned((p) => !p)}
          onHoverChange={setSidebarHovered}
        />
      </div>

      {/* Topbar */}
      <div style={{ gridColumn: 2, gridRow: 1 }}>
        <Topbar
          onSimulate={simulateAttack}
          onStopSimulate={stopSimulation}
          onForensicsClick={() => setForensicsOpen(true)}
        />
      </div>

      {/* Page content */}
      <main
        style={{
          gridColumn: 2,
          gridRow: 2,
          overflow: 'auto',
          padding: '20px',
          position: 'relative',
        }}
      >
        {/* Ambient radial glow */}
        <div
          className="fixed inset-0 pointer-events-none"
          style={{ zIndex: 0 }}
        >
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] rounded-full blur-[120px]"
            style={{ background: 'rgba(79,110,247,0.04)' }}
          />
        </div>

        <div style={{ position: 'relative', zIndex: 1 }}>
          <Outlet />
        </div>
      </main>

      {/* Node detail overlay — available on any page */}
      <AnimatePresence>
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onBlock={handleBlock}
          />
        )}
      </AnimatePresence>

      {/* Forensics modal — triggered from topbar */}
      <ForensicsModal isOpen={forensicsOpen} onClose={() => setForensicsOpen(false)} />
    </div>
  )
}
