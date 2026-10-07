// [Windows] GraphSentinel — Susheep
// Topbar — page title + telemetry stats + health + clock + simulate + account
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Zap, Activity, Database } from 'lucide-react'
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
        <span className="gs-tel gs-tel-1"><TelemetryBadge label="Threats" value={stats.active_threats}             icon="▲" color={GS.danger} pulse={stats.active_threats > 0} /></span>
        <span className="gs-tel gs-tel-2"><TelemetryDivider /><TelemetryBadge label="Blocked" value={stats.blocked_ips}                icon="⬡" color={GS.primary} /></span>
        <span className="gs-tel gs-tel-3"><TelemetryDivider /><TelemetryBadge label="Nodes"   value={stats.total_nodes}                icon="●" color={GS.textMuted} /></span>
        <span className="gs-tel gs-tel-4"><TelemetryDivider /><TelemetryBadge label="Packets" value={formatNumber(stats.total_packets)} icon="~" color={GS.textSubtle} /></span>
        <span className="gs-tel gs-tel-5"><TelemetryDivider /><TelemetryBadge label="Bytes"   value={formatBytes(stats.total_bytes)}   icon="↕" color={GS.textSubtle} /></span>
      </div>

      {/* ── Right: health + clock + actions ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {/* Health */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '4px 8px',
            borderRadius: 6,
            border: `1px solid ${healthColor}25`,
            background: `${healthColor}08`,
          }}
        >
          <Activity size={10} style={{ color: healthColor }} />
          <span style={{ color: GS.textSubtle, fontSize: 9, fontFamily: "var(--font-mono)", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Health
          </span>
          <motion.span
            style={{ color: healthColor, fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 11 }}
            animate={{ opacity: [1, 0.6, 1] }}
            transition={{ duration: 2.5, repeat: Infinity }}
          >
            {healthClamped}%
          </motion.span>
        </div>

        {/* Clock */}
        <div
          style={{
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid rgba(43,42,40,0.10)',
          }}
        >
          <span style={{ color: GS.textSubtle, fontSize: 11, fontFamily: "var(--font-mono)" }}>
            {time}
          </span>
        </div>

        {/* Forensics button */}
        <button
          id="topbar-forensics"
          onClick={onForensicsClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            borderRadius: 999,
            border: '1px solid color-mix(in srgb, var(--ink) 24%, transparent)',
            background: 'transparent',
            color: GS.text,
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            fontWeight: 500,
            cursor: 'pointer',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
          title="Open forensics report"
        >
          <Database size={10} />
          <span>Forensics</span>
        </button>

        {/* Simulate: opens the attack console */}
        {pathname !== '/simulation' && (
          <button
            id="topbar-simulate"
            onClick={() => navigate('/simulation')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              // The landing page's one call to action: crimson glass, a pill.
              borderRadius: 999,
              border: 'none',
              background: runActive ? GS.dangerDeep : 'color-mix(in srgb, var(--crimson) 90%, transparent)',
              boxShadow: 'inset 0 1px 0 color-mix(in srgb, var(--bone) 44%, transparent), inset 0 -1px 0 color-mix(in srgb, var(--ink) 26%, transparent)',
              color: GS.surface,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              fontWeight: 500,
              cursor: 'pointer',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              transition: 'all 200ms',
              whiteSpace: 'nowrap',
            }}
            title={runActive
              ? 'An attack is running on the topology: open the console to follow it'
              : simulateBlocked || 'Run a real attack script on the Mininet topology'}
          >
            <Zap size={10} />
            <span>{runActive ? 'Simulation running' : 'Simulate Attack'}</span>
          </button>
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

function TelemetryBadge({ label, value, icon, color, pulse = false }) {
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
      <span style={{ color: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 1 }}>
        {icon} {label}
      </span>
      <span
        style={{
          color,
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: 13,
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
