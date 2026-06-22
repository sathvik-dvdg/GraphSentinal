// [Windows] GraphSentinel — Susheep
// ── ALL state, effects, callbacks, hooks, and handlers PRESERVED VERBATIM ──
// Redesigned StatsBar: reads connectionMode instead of isMockMode + isConnected separately
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { LogOut, Database, Zap, Activity } from 'lucide-react'
import ConnectionModeBadge from '../ui/ConnectionModeBadge'
import useGraphStore from '../../store/useGraphStore'

export default function StatsBar({ stats, onForensicsClick, onLogout, onSimulate }) {
  // ── Original state — untouched ──
  const [time, setTime] = useState(new Date().toLocaleTimeString())

  // Read connectionMode directly from store for the badge
  const connectionMode = useGraphStore((s) => s.connectionMode)

  // ── Original effect — untouched ──
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(interval)
  }, [])

  // § 4.6: Clamp system_health 0–100 for display (backend can return negatives)
  const healthClamped = Math.max(0, Math.min(100, stats.system_health ?? 0))

  // Health color — functional, not decorative
  const healthColor =
    healthClamped >= 80 ? '#2ECC8A' :
    healthClamped >= 50 ? '#E8922A' : '#E03C3C'
  const healthLabel =
    healthClamped >= 80 ? 'Good' :
    healthClamped >= 50 ? 'Degraded' : 'Critical'

  return (
    <div
      className="flex items-center justify-between px-4 h-12 border-b border-gs-border shrink-0 gap-3"
      style={{ backgroundColor: '#141414' }}
    >
      {/* ── Left: Branding + connection badge ── */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 flex items-center justify-center rounded-md bg-gs-accent-soft border border-gs-accent/25">
            <svg viewBox="0 0 24 24" fill="none" className="w-3.5 h-3.5 text-gs-accent" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
          <span className="font-heading font-semibold text-[13px] text-gs-text tracking-wide hidden sm:block">
            GraphSentinel
          </span>
        </div>

        {/* Connection mode badge — reads from connectionMode, not inferred */}
        <ConnectionModeBadge mode={connectionMode} />
      </div>

      {/* ── Center: Telemetry metrics ── */}
      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar flex-1 justify-center">
        <TelemetryBadge label="Nodes"   value={stats.total_nodes}                icon="●" color="text-gs-text"   />
        <div className="w-px h-5 bg-gs-border mx-1 shrink-0" aria-hidden="true" />
        <TelemetryBadge label="Threats" value={stats.active_threats}             icon="▲" color="text-gs-threat" pulse={stats.active_threats > 0} />
        <div className="w-px h-5 bg-gs-border mx-1 shrink-0" aria-hidden="true" />
        <TelemetryBadge label="Blocked" value={stats.blocked_ips}                icon="⬡" color="text-gs-accent" />
        <div className="w-px h-5 bg-gs-border mx-1 shrink-0 hidden md:block" aria-hidden="true" />
        <TelemetryBadge label="Packets" value={formatNumber(stats.total_packets)} icon="~" color="text-gs-muted" className="hidden md:flex" />
        <div className="w-px h-5 bg-gs-border mx-1 shrink-0 hidden md:block" aria-hidden="true" />
        <TelemetryBadge label="Bytes"   value={formatBytes(stats.total_bytes)}   icon="↕" color="text-gs-muted" className="hidden md:flex" />
      </div>

      {/* ── Right: Health + clock + actions ── */}
      <div className="flex items-center gap-2 shrink-0">
        {/* System health — color + icon + text label */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border"
          style={{
            borderColor: `${healthColor}25`,
            backgroundColor: `${healthColor}08`,
          }}
          title={`System Health: ${healthClamped}%`}
        >
          <Activity size={10} style={{ color: healthColor }} aria-hidden="true" />
          <span className="text-[9px] text-gs-muted font-mono uppercase tracking-wider hidden sm:block">Health</span>
          <motion.span
            style={{ color: healthColor }}
            animate={{ opacity: [1, 0.6, 1] }}
            transition={{ duration: 2.5, repeat: Infinity }}
            className="font-mono font-bold text-[11px] tabular-nums"
            aria-label={`System health: ${healthClamped}% — ${healthLabel}`}
          >
            {healthClamped}%
          </motion.span>
        </div>

        {/* Clock */}
        <div className="px-2 py-1 rounded-md border border-gs-border hidden sm:block">
          <span className="text-gs-muted text-[11px] font-mono tabular-nums">{time}</span>
        </div>

        {/* SIMULATE button — original onClick preserved */}
        {onSimulate && (
          <button
            id="statsbar-simulate"
            onClick={onSimulate}
            className="tac-btn flex items-center gap-1.5 text-gs-warn border border-gs-warn/30 bg-gs-warn-soft hover:border-gs-warn/60 hover:bg-gs-warn/10 transition-all duration-200 px-2.5 py-1 rounded-md font-mono text-[10px] uppercase tracking-wider"
            title="Simulate an attack sequence"
          >
            <Zap size={10} aria-hidden="true" />
            <span className="hidden sm:inline">Simulate</span>
          </button>
        )}

        {/* FORENSICS button — original onClick preserved */}
        <button
          id="statsbar-forensics"
          onClick={onForensicsClick}
          className="tac-btn flex items-center gap-1.5 text-gs-chain border border-gs-chain/25 bg-gs-chain-soft hover:border-gs-chain/50 hover:bg-gs-chain/10 transition-all duration-200 px-2.5 py-1 rounded-md font-mono text-[10px] uppercase tracking-wider"
          title="Open forensics report"
        >
          <Database size={10} aria-hidden="true" />
          <span className="hidden sm:inline">Forensics</span>
        </button>

        {/* Logout — original onClick preserved */}
        <button
          id="statsbar-logout"
          onClick={onLogout}
          className="flex items-center gap-1 text-gs-muted hover:text-gs-threat border border-gs-border hover:border-gs-threat/30 hover:bg-gs-threat-soft transition-all duration-200 p-1.5 rounded-md"
          aria-label="Log out"
          title="Log out"
        >
          <LogOut size={13} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

/* ── Telemetry badge sub-component ── */
function TelemetryBadge({ label, value, icon, color, pulse = false, className = '' }) {
  return (
    <div
      className={`flex flex-col items-center px-2.5 py-0.5 min-w-[44px] shrink-0 ${className}`}
      title={`${label}: ${value}`}
    >
      <span className="text-gs-faint text-[9px] font-mono tracking-widest uppercase mb-0.5 flex items-center gap-1">
        <span aria-hidden="true" className="text-[8px]">{icon}</span>
        {label}
      </span>
      <span
        className={`font-bold text-[13px] font-mono tabular-nums ${color} ${pulse ? 'pulse-threat' : ''}`}
        aria-label={`${label}: ${value ?? 0}`}
      >
        {value ?? 0}
      </span>
    </div>
  )
}

/* ── Original formatters — untouched ── */
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
