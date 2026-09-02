// [Windows] GraphSentinel — Susheep
// Topbar — page title + telemetry stats + health + clock + simulate + logout
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { LogOut, Zap, Activity, Database } from 'lucide-react'
import { motion } from 'framer-motion'
import useGraphStore from '../../store/useGraphStore'
import useAuthStore from '../../store/useAuthStore'
import ConnectionModeBadge from '../ui/ConnectionModeBadge'
import EnforcementModeBadge from '../ui/EnforcementModeBadge'
import DataFreshnessBadge from '../ui/DataFreshnessBadge'
import MlModeBadge from '../ui/MlModeBadge'
import DemoModeBadge from '../ui/DemoModeBadge'

const ROUTE_TITLES = {
  '/dashboard':  'Dashboard',
  '/network':    'Network Topology',
  '/threats':    'Threat Feed',
  '/forensics':  'Forensics',
  '/blockchain': 'Audit & Ledger',
  '/timeline':   'Timeline Analytics',
  '/healing':    'Self-Healing Engine',
  '/alerts':     'Alert Centre',
  '/settings':   'Settings',
}

export default function Topbar({ onSimulate, onStopSimulate, onForensicsClick }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { logout } = useAuthStore()

  const {
    stats,
    connectionMode,
    dataErrors,
    mlHealth,
  } = useGraphStore()

  const [time, setTime] = useState(new Date().toLocaleTimeString())

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(interval)
  }, [])

  const healthClamped = Math.max(0, Math.min(100, stats.system_health ?? 0))
  const healthColor =
    healthClamped >= 80 ? '#2ECC8A' :
    healthClamped >= 50 ? '#E8922A' : '#E03C3C'

  const isSimulating = connectionMode === 'simulating'

  const handleLogout = async () => {
    // logout() calls POST /api/v1/auth/logout to invalidate the session
    // server-side too, not just forget the token client-side.
    await logout()
    navigate('/')
  }

  return (
    <header
      style={{
        background: '#141414',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 16,
        height: 48,
        overflow: 'hidden',
      }}
    >
      {/* ── Left: Page title + connection badge ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 200, flexShrink: 0 }}>
        <span
          style={{
            color: '#E8EDF5',
            fontFamily: "'Plus Jakarta Sans', Inter, sans-serif",
            fontWeight: 600,
            fontSize: 13,
            letterSpacing: '0.02em',
            whiteSpace: 'nowrap',
          }}
        >
          {ROUTE_TITLES[pathname] || 'GraphSentinel'}
        </span>

        <ConnectionModeBadge mode={connectionMode} />
        <EnforcementModeBadge mode={stats.enforcement_mode} />
        <MlModeBadge mlHealth={mlHealth} />
        <DataFreshnessBadge dataErrors={dataErrors} />
        <DemoModeBadge demoFallbackFlows={stats.demo_fallback_flows} />


        {isSimulating && (
          <span
            style={{
              background: 'rgba(232,146,42,0.15)',
              border: '1px solid rgba(232,146,42,0.4)',
              color: '#E8922A',
              fontSize: 9,
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: 4,
              fontFamily: "'DM Mono', monospace",
              letterSpacing: '0.08em',
            }}
          >
            SIMULATION
          </span>
        )}
      </div>

      {/* ── Centre: Telemetry stats ── */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        <TelemetryBadge label="Nodes"   value={stats.total_nodes}                icon="●" color="#8A95B0" />
        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />
        <TelemetryBadge label="Threats" value={stats.active_threats}             icon="▲" color="#E03C3C" pulse={stats.active_threats > 0} />
        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />
        <TelemetryBadge label="Blocked" value={stats.blocked_ips}                icon="⬡" color="#4F6EF7" />
        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />
        <TelemetryBadge label="Packets" value={formatNumber(stats.total_packets)} icon="~" color="#5A6480" />
        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />
        <TelemetryBadge label="Bytes"   value={formatBytes(stats.total_bytes)}   icon="↕" color="#5A6480" />
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
          <span style={{ color: '#5A6480', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Health
          </span>
          <motion.span
            style={{ color: healthColor, fontFamily: "'DM Mono', monospace", fontWeight: 700, fontSize: 11 }}
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
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
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
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid rgba(139,92,246,0.25)',
            background: 'rgba(139,92,246,0.08)',
            color: '#8B5CF6',
            fontSize: 10,
            fontFamily: "'DM Mono', monospace",
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

        {/* Simulate toggle */}
        {onSimulate && (
          <button
            id="topbar-simulate"
            onClick={isSimulating ? onStopSimulate : onSimulate}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '4px 10px',
              borderRadius: 6,
              border: `1px solid ${isSimulating ? 'rgba(232,146,42,0.5)' : 'rgba(255,255,255,0.12)'}`,
              background: isSimulating ? 'rgba(232,146,42,0.12)' : 'rgba(255,255,255,0.05)',
              color: isSimulating ? '#E8922A' : '#8A95B0',
              fontSize: 10,
              fontFamily: "'DM Mono', monospace",
              fontWeight: 500,
              cursor: 'pointer',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              transition: 'all 200ms',
            }}
            title="Simulate an attack sequence"
          >
            <Zap size={10} />
            <span>{isSimulating ? 'Stop Sim' : 'Simulate'}</span>
          </button>
        )}

        {/* Logout */}
        <button
          id="topbar-logout"
          onClick={handleLogout}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '5px',
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.08)',
            background: 'transparent',
            color: '#5A6480',
            cursor: 'pointer',
            transition: 'all 200ms',
          }}
          aria-label="Log out"
          title="Log out"
        >
          <LogOut size={13} />
        </button>
      </div>
    </header>
  )
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
      <span style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 1 }}>
        {icon} {label}
      </span>
      <span
        style={{
          color,
          fontFamily: "'DM Mono', monospace",
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
