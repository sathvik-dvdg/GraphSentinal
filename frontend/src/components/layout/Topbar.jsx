// [Windows] GraphSentinel — Susheep
// Topbar — page title + telemetry stats + health + clock + simulate + account
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Button from '../ui/Button'
import { motion } from 'framer-motion'
import { UserButton } from '@clerk/react'
import useGraphStore from '../../store/useGraphStore'
import ConnectionModeBadge from '../ui/ConnectionModeBadge'
import DetectionPathBadge from '../ui/DetectionPathBadge'
import DataFreshnessBadge from '../ui/DataFreshnessBadge'
import MlModeBadge from '../ui/MlModeBadge'
import DemoModeBadge from '../ui/DemoModeBadge'
import { simulationBlockedReason } from '../../utils/connection'
import useSessionUser from '../../hooks/useSessionUser'
import { GS } from '../../constants/colors'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

const ROUTE_TITLES = {
  '/dashboard':  'Dashboard',
  '/network':    'Network Topology',
  '/threats':    'Threat Feed',
  '/forensics':  'Forensics',
  '/blockchain': 'Audit & Ledger',
  '/timeline':   'Timeline Analytics',
  '/healing':    'Self-Healing Engine',
  '/alerts':     'Alert Centre',
  '/audit':      'Audit Log',
  '/settings':   'Settings',
  '/simulation': 'Attack Simulation',
}

export default function Topbar({ onForensicsClick }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const {
    stats,
    connectionMode,
    socketStatus,
    dataErrors,
    mlHealth,
    mlV2Health,
    simulationRun,
  } = useGraphStore()

  const [time, setTime] = useState(new Date().toLocaleTimeString())

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(interval)
  }, [])

  const healthClamped = Math.max(0, Math.min(100, stats.system_health ?? 0))
  const healthColor =
    healthClamped >= 80 ? GS.success :
    healthClamped >= 50 ? GS.warn : GS.danger

  // Simulate opens the attack console (pages/AttackSimulation), which runs the
  // real scripts in mininet/demo/attacks. The button always opens it; the
  // console says why a run cannot start (utils/connection).
  const runActive = Boolean(simulationRun?.active)
  const { role } = useSessionUser()
  const simulateBlocked = simulationBlockedReason(USE_MOCK, connectionMode, role)

  return (
    <header
      style={{
        // The landing nav: a bone tint over a blur, a hairline and a soft shadow.
        background: 'color-mix(in srgb, var(--bone) 78%, transparent)',
        backdropFilter: 'var(--glass-filter)',
        WebkitBackdropFilter: 'var(--glass-filter)',
        borderBottom: '1px solid var(--border-panel)',
        boxShadow: '0 10px 24px -18px color-mix(in srgb, var(--ink) 34%, transparent)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 16,
        height: 48,
        overflow: 'hidden',
      }}
    >
      {/* ── Left: Page title + connection badges ──
          Error.md U9 — this row used to be flexShrink:0 with a hard
          `overflow:hidden` parent, so on laptop-width screens the trailing
          badges were simply clipped. It now shrinks (min-width:0) and scrolls
          its own overflow horizontally instead of losing badges. */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '0 1 auto', overflowX: 'auto' }}
        className="gs-no-scrollbar"
      >
        <span
          style={{
            color: GS.text,
            fontFamily: "var(--font-display)",
            fontWeight: 500,
            fontSize: 18,
            letterSpacing: '-0.01em',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {ROUTE_TITLES[pathname] || 'GraphSentinel'}
        </span>

        <ConnectionModeBadge mode={connectionMode} socketStatus={socketStatus} />
        <DetectionPathBadge mlV2={mlV2Health} />
        <MlModeBadge mlHealth={mlHealth} />
        <DataFreshnessBadge dataErrors={dataErrors} />
        <DemoModeBadge demoFallbackFlows={stats.demo_fallback_flows} />
      </div>

      {/* ── Centre: Telemetry stats ──
          Error.md U9 — hidden below 1280px (xl); it's a secondary read that's
          also on the Dashboard, so dropping it first keeps the badges and
          action buttons legible on laptop widths. */}
      <div
        className="gs-topbar-telemetry"
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          justifyContent: 'center',
          overflow: 'hidden',
          minWidth: 0,
        }}
      >
        {/* Each figure carries its own divider and drops out whole, last first, when the
            space runs short (container queries in globals.css), so none is ever clipped. */}
        <span className="gs-tel gs-tel-1"><TelemetryBadge label="Threats" value={stats.active_threats}             color={GS.danger} pulse={stats.active_threats > 0} /></span>
        <span className="gs-tel gs-tel-2"><TelemetryDivider /><TelemetryBadge label="Blocked" value={stats.blocked_ips}                color={GS.primary} /></span>
        <span className="gs-tel gs-tel-3"><TelemetryDivider /><TelemetryBadge label="Nodes"   value={stats.total_nodes}                color={GS.textMuted} /></span>
        <span className="gs-tel gs-tel-4"><TelemetryDivider /><TelemetryBadge label="Packets" value={formatNumber(stats.total_packets)} color={GS.textSubtle} /></span>
        <span className="gs-tel gs-tel-5"><TelemetryDivider /><TelemetryBadge label="Bytes"   value={formatBytes(stats.total_bytes)}   color={GS.textSubtle} /></span>
      </div>

      {/* ── Right: health + clock + actions ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {/* Health and clock: plain readings, no chrome */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, whiteSpace: 'nowrap' }}>
          <span style={{ color: GS.textSubtle, fontSize: 12 }}>Health</span>
          <motion.span
            style={{ color: healthColor, fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 13 }}
            animate={{ opacity: [1, 0.65, 1] }}
            transition={{ duration: 2.5, repeat: Infinity }}
          >
            {healthClamped}%
          </motion.span>
        </div>
        <span style={{ color: GS.textSubtle, fontSize: 12, fontFamily: "var(--font-mono)", fontVariantNumeric: 'tabular-nums' }}>
          {time}
        </span>

        <Button id="topbar-forensics" size="sm" variant="secondary" onClick={onForensicsClick} title="Open forensics report">
          Forensics
        </Button>

        {/* Simulate: opens the attack console */}
        {pathname !== '/simulation' && (
          <Button
            id="topbar-simulate"
            size="sm"
            variant="accent"
            onClick={() => navigate('/simulation')}
            style={runActive ? { background: GS.dangerDeep } : undefined}
            title={runActive
              ? 'An attack is running on the topology: open the console to follow it'
              : simulateBlocked || 'Run a real attack script on the Mininet topology'}
          >
            {runActive ? 'Simulation running' : 'Simulate attack'}
          </Button>
        )}

        {/* Clerk User Button */}
        <div style={{ marginLeft: 8 }}>
          <UserButton />
        </div>
      </div>
    </header>
  )
}

function TelemetryDivider() {
  return <div style={{ width: 1, height: 20, background: 'color-mix(in srgb, var(--ink) 12%, transparent)', margin: '0 4px', flexShrink: 0 }} />
}

function TelemetryBadge({ label, value, color, pulse = false }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '0 10px',
        minWidth: 44,
        flexShrink: 0,
      }}
    >
      <span style={{ color: GS.textSubtle, fontSize: 11, marginBottom: 1 }}>
        {label}
      </span>
      <span
        style={{
          color,
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          fontSize: 14,
        }}
        className={pulse ? 'pulse-threat' : ''}
      >
        {value ?? 0}
      </span>
    </div>
  )
}

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n ?? 0
}

function formatBytes(b) {
  if (b >= 1073741824) return (b / 1073741824).toFixed(1) + 'GB'
  if (b >= 1048576) return (b / 1048576).toFixed(1) + 'MB'
  if (b >= 1024) return (b / 1024).toFixed(1) + 'KB'
  return (b ?? 0) + 'B'
}
