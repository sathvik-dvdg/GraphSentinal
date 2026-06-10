// [Windows] GraphSentinel — Susheep
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { LogOut, Search, Zap } from 'lucide-react'
import SimBadge from '../shared/SimBadge'

export default function StatsBar({ stats, isMockMode, isConnected, onForensicsClick, onLogout, onSimulate }) {
  const [time, setTime] = useState(new Date().toLocaleTimeString())

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(interval)
  }, [])

  const healthColor =
    stats.system_health >= 80 ? '#00ff88' : stats.system_health >= 50 ? '#ffaa00' : '#ff4444'

  return (
    <div className="flex items-center justify-between px-4 py-2.5 bg-gs-card border-b border-gs-border text-xs font-mono shrink-0">
      {/* Left: Logo + mode */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="text-gs-accent font-bold text-sm tracking-wide">🛡️ GRAPHSENTINEL</span>
        {isMockMode ? (
          <SimBadge />
        ) : (
          <span className="flex items-center gap-1.5 text-gs-accent text-xs">
            <motion.div
              className="w-2 h-2 rounded-full bg-gs-accent"
              animate={{ opacity: [1, 0.4, 1], scale: [1, 1.3, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            LIVE
          </span>
        )}
      </div>

      {/* Center: Stats — with separators for clarity */}
      <div className="flex items-center gap-1">
        <Stat label="NODES" value={stats.total_nodes} color="#e2e8f0" />
        <Divider />
        <Stat label="THREATS" value={stats.active_threats} color="#ff4444" />
        <Divider />
        <Stat label="BLOCKED" value={stats.blocked_ips} color="#0066ff" />
        <Divider />
        <Stat label="PACKETS" value={formatNumber(stats.total_packets)} color="#e2e8f0" />
        <Divider />
        <Stat label="BYTES" value={formatBytes(stats.total_bytes)} color="#e2e8f0" />
      </div>

      {/* Right: Health + time + actions */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Health indicator */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-gs-border bg-gs-bg/50">
          <span className="text-gray-500 text-xs">HEALTH</span>
          <motion.span
            style={{ color: healthColor }}
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="font-bold"
          >
            {stats.system_health}%
          </motion.span>
        </div>

        {/* Clock */}
        <span className="text-gray-500 tabular-nums">{time}</span>

        {/* Action buttons */}
        {onSimulate && (
          <button
            onClick={onSimulate}
            className="flex items-center gap-1.5 text-yellow-400 border border-yellow-500/40 hover:border-yellow-400 hover:bg-yellow-500/10 transition-all px-2.5 py-1 rounded font-mono"
          >
            <Zap size={11} />
            SIMULATE
          </button>
        )}
        <button
          onClick={onForensicsClick}
          className="flex items-center gap-1.5 text-purple-400 hover:text-purple-300 transition-colors px-2.5 py-1 rounded border border-purple-500/30 hover:border-purple-400 hover:bg-purple-500/10"
        >
          <Search size={11} />
          FORENSICS
        </button>
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 text-gray-500 hover:text-red-400 transition-colors px-2 py-1 rounded border border-gs-border hover:border-red-500/50 hover:bg-red-500/10"
        >
          <LogOut size={11} />
        </button>
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div className="flex flex-col items-center px-3 py-0.5 min-w-[56px]">
      <span className="text-gray-600 text-[10px] tracking-wider">{label}</span>
      <span className="font-bold text-sm" style={{ color }}>
        {value}
      </span>
    </div>
  )
}

function Divider() {
  return <div className="w-px h-6 bg-gs-border/60" />
}

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
