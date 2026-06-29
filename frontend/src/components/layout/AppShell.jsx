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
import { blockIP } from '../../services/api'
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
  } = useGraphStore()

  // ── Initial loading splash ─────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setShowLoading(false), 1800)
    return () => clearTimeout(t)
  }, [])

  // ── handleBlock (verbatim) ─────────────────────────────────────────
  const handleBlock = async (ip, action) => {
    try {
      await blockIP(ip, action)
    } catch {
      console.warn('[AppShell] Block API unavailable in mock mode')
    }
    setSelectedNode(null)
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
        background: '#0A0A0A',
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
