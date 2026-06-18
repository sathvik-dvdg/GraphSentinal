// [Windows] GraphSentinel — Susheep
// ── All props, state, effects, and handlers preserved verbatim ──
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { LogOut, Search, Zap, Activity } from 'lucide-react'
import SimBadge from '../shared/SimBadge'

export default function StatsBar({ stats, isMockMode, isConnected, onForensicsClick, onLogout, onSimulate }) {
  // ── Original state — untouched ──
  const [time, setTime] = useState(new Date().toLocaleTimeString())

  // ── Original effect — untouched ──
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(interval)
  }, [])

  // ── Original computed — untouched ──
  const healthColor =
    stats.system_health >= 80 ? '#34d399' : stats.system_health >= 50 ? '#fbbf24' : '#f43f5e'
  const healthRing =
    stats.system_health >= 80
      ? 'border-emerald-500/30 bg-emerald-500/5'
      : stats.system_health >= 50
      ? 'border-amber-500/30 bg-amber-500/5'
      : 'border-rose-500/30 bg-rose-500/5'

  return (
    <div
      className="flex items-center justify-between px-5 h-14 border-b border-outline-variant/30 shrink-0 gap-3"
      style={{ background: 'rgba(13,28,45,0.8)', backdropFilter: 'blur(16px)' }}
    >
      {/* ── Left: Branding + connection status ── */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {/* Shield mark */}
          <div className="w-6 h-6 flex items-center justify-center rounded-md bg-primary-container/10 border border-primary-container/30">
            <svg viewBox="0 0 24 24" fill="none" className="w-3.5 h-3.5 text-primary-container" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
          <span className="font-orbitron text-primary-container font-bold text-sm tracking-widest text-glow">
            GRAPHSENTINEL
          </span>
          <span className="hidden md:block text-on-surface-variant/50 text-xs font-mono">·</span>
          <span className="hidden md:block text-on-surface-variant text-[10px] font-mono tracking-widest uppercase">
            LIVE
          </span>
        </div>

        {/* Connection badge */}
        {isMockMode ? (
          <SimBadge />
        ) : (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-primary-container/25 bg-primary-container/5">
            <motion.div
              className="w-1.5 h-1.5 rounded-full bg-primary-container"
              animate={{ opacity: [1, 0.3, 1], scale: [1, 1.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-primary-container text-[10px] font-mono tracking-wider">CONNECTED</span>
          </div>
        )}
      </div>

      {/* ── Center: Telemetry badges ── */}
      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
        <TelemetryBadge label="NODES"   value={stats.total_nodes}            color="text-on-surface"    ring="border-outline-variant/20"  />
        <div className="w-px h-6 bg-outline-variant/30 mx-1 shrink-0" />
        <TelemetryBadge label="THREATS" value={stats.active_threats}         color="text-error"     ring="border-error/20"   pulse={stats.active_threats > 0} />
        <div className="w-px h-6 bg-outline-variant/30 mx-1 shrink-0" />
        <TelemetryBadge label="BLOCKED" value={stats.blocked_ips}            color="text-primary-container"     ring="border-primary-container/20"   />
        <div className="w-px h-6 bg-outline-variant/30 mx-1 shrink-0" />
        <TelemetryBadge label="PACKETS" value={formatNumber(stats.total_packets)} color="text-on-surface" ring="border-outline-variant/20" />
        <div className="w-px h-6 bg-outline-variant/30 mx-1 shrink-0" />
        <TelemetryBadge label="BYTES"   value={formatBytes(stats.total_bytes)}    color="text-on-surface" ring="border-outline-variant/20" />
      </div>

      {/* ── Right: Health + clock + action buttons ── */}
      <div className="flex items-center gap-2 shrink-0">
        {/* System health pill */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${healthRing} shrink-0`}>
          <Activity size={11} style={{ color: healthColor }} />
          <span className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">Health</span>
          <motion.span
            style={{ color: healthColor }}
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="font-bold text-xs font-mono tabular-nums"
          >
            {stats.system_health}%
          </motion.span>
        </div>

        {/* Clock */}
        <div className="px-2.5 py-1.5 rounded-lg border border-slate-800/60 bg-slate-900/30">
          <span className="text-slate-400 text-xs font-mono tabular-nums">{time}</span>
        </div>

        {/* SIMULATE button */}
        {onSimulate && (
          <button
            onClick={onSimulate}
            className="tac-btn flex items-center gap-1.5 text-amber-400 border border-amber-500/40 bg-amber-500/5 hover:border-amber-400 hover:bg-amber-500/10 hover:shadow-glow-amber transition-all duration-200 px-3 py-1.5 rounded-lg font-mono text-[11px] uppercase tracking-wider"
          >
            <Zap size={11} />
            SIMULATE
          </button>
        )}

        {/* FORENSICS button */}
        <button
          onClick={onForensicsClick}
          className="tac-btn flex items-center gap-1.5 text-purple-400 border border-purple-500/30 bg-purple-500/5 hover:border-purple-400 hover:bg-purple-500/10 transition-all duration-200 px-3 py-1.5 rounded-lg font-mono text-[11px] uppercase tracking-wider"
        >
          <Search size={11} />
          FORENSICS
        </button>

        {/* Logout */}
        <button
          onClick={onLogout}
          className="flex items-center gap-1 text-slate-500 hover:text-rose-400 border border-slate-800 hover:border-rose-500/40 hover:bg-rose-500/5 transition-all duration-200 p-1.5 rounded-lg"
        >
          <LogOut size={13} />
        </button>
      </div>
    </div>
  )
}

/* ── Telemetry badge sub-component ── */
function TelemetryBadge({ label, value, color, ring, pulse = false }) {
  return (
    <div className={`flex flex-col items-center px-3 py-1 rounded-lg border ${ring} bg-surface-container/50 min-w-[52px] shrink-0`}>
      <span className="text-on-surface-variant text-[9px] font-mono tracking-widest uppercase mb-0.5">{label}</span>
      <span className={`font-bold text-sm font-mono tabular-nums ${color} ${pulse ? 'animate-pulse' : ''}`}>
        {value ?? 0}
      </span>
    </div>
  )
}

/* ── Original formatters — untouched ── */
function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n
}

function formatBytes(b) {
  if (b >= 1073741824) return (b / 1073741824).toFixed(1) + 'GB'
  if (b >= 1048576) return (b / 1048576).toFixed(1) + 'MB'
  if (b >= 1024) return (b / 1024).toFixed(1) + 'KB'
  return b + 'B'
}
