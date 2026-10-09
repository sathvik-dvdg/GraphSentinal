// [Windows] GraphSentinel — Susheep
// DashboardPage — stripped to overview only (stat cards + summaries + mini timeline)
// The WebSocket lives in SimulationProvider (live data); attack runs are the /simulation page
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, ShieldAlert, Shield, Network,
  ChevronRight, Cpu, TrendingUp,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import useGraphStore from '../store/useGraphStore'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatEventTimestamp, formatTimelineTick } from '../utils/formatTimestamp'
import { GS } from '../constants/colors'

function LastUpdated({ ts }) {
  // Error.md U4 — a freshness read distinct from the connection badge: shows
  // how long ago real data actually landed, ticking every second.
  const [, force] = useState(0)
  useEffect(() => {
    const id = setInterval(() => force((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [])
  if (!ts) return null
  const secs = Math.max(0, Math.round((Date.now() - ts) / 1000))
  const label = secs < 60 ? `${secs}s ago` : `${Math.round(secs / 60)}m ago`
  const stale = secs > 15
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: stale ? GS.warn : GS.success, fontSize: 11, fontFamily: "var(--font-mono)" }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', animation: stale ? 'none' : 'pulse-threat 2s infinite' }} />
      Updated {label}
    </span>
  )
}

export default function DashboardPage() {
  const { stats = {}, alerts = [], healingEvents = [], timeline = [], dataErrors = {}, lastDataAt = null } = useGraphStore()

  const health = Math.max(0, Math.min(100, stats?.system_health ?? 100))
  const healthColor = health >= 80 ? GS.success : health >= 50 ? GS.warn : GS.danger
  const healthLabel = health >= 80 ? 'Healthy' : health >= 50 ? 'Degraded' : 'Critical'

  const recentThreats = Array.isArray(alerts) ? [...alerts].slice(0, 5) : []
  const recentHealing = Array.isArray(healingEvents) ? [...healingEvents].slice(0, 3) : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Page header */}
      <div>
        <h1 style={{ color: GS.text, fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Dashboard
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <p style={{ color: GS.textSubtle, fontFamily: "var(--font-sans)", fontSize: 14 }}>
            Network overview · Real-time threat summary
          </p>
          <LastUpdated ts={lastDataAt} />
          <DataFreshnessBadge dataErrors={{ stats: dataErrors.stats, alerts: dataErrors.alerts, timeline: dataErrors.timeline }} />
        </div>
      </div>

      {/* ── Row 1: 4 stat cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <StatCard
          title="Network Health"
          value={`${health}%`}
          sub={healthLabel}
          icon={<Activity size={18} style={{ color: healthColor }} />}
          accent={healthColor}
          delay={0}
        />
        <StatCard
          title="Active Nodes"
          value={stats.total_nodes ?? 0}
          sub="Connected endpoints"
          icon={<Network size={18} style={{ color: GS.primary }} />}
          accent={GS.primary}
          delay={0.06}
        />
        <StatCard
          // stats.active_threats counts hosts flagged malicious or suspicious
          // RIGHT NOW, not threats over 24 hours (FE-25).
          title="Active Threats"
          value={stats.active_threats ?? 0}
          sub={stats.active_threats > 0 ? '⚠ Hosts flagged now' : 'None flagged now'}
          icon={<ShieldAlert size={18} style={{ color: GS.danger }} />}
          accent={GS.danger}
          pulse={stats.active_threats > 0}
          delay={0.12}
        />
        <StatCard
          title="Nodes Isolated"
          value={stats.blocked_ips ?? 0}
          sub="Self-healing active"
          icon={<Shield size={18} style={{ color: GS.success }} />}
          accent={GS.success}
          delay={0.18}
        />
      </div>

      {/* ── Row 2: Recent threats + Self-healing activity ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Recent threats */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid rgba(43,42,40,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ShieldAlert size={14} style={{ color: GS.danger }} />
              <span style={{ color: GS.danger, fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600 }}>
                Recent Threats
              </span>
            </div>
            <Link
              to="/threats"
              style={{ display: 'flex', alignItems: 'center', gap: 4, color: GS.primary, fontSize: 11, fontFamily: "var(--font-mono)", textDecoration: 'none' }}
            >
              View all <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recentThreats.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: GS.textFaint, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                No threats detected. Network secure.
              </div>
            ) : (
              recentThreats.map((alert, i) => (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: GS.surfaceRaised,
                    border: `1px solid ${alert.severity === 'critical' ? 'rgba(180,19,46,0.2)' : 'rgba(133,88,8,0.15)'}`,
                    borderLeft: `2px solid ${alert.severity === 'critical' ? GS.danger : GS.warn}`,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--font-sans)", color: alert.severity === 'critical' ? GS.danger : GS.warn }}>
                        {alert.severity}
                      </span>
                      <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: GS.textMuted }}>
                        {alert.attack_type}
                      </span>
                    </div>
                    <div style={{ color: GS.text, fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {alert.source_ip}
                    </div>
                  </div>
                  <div style={{ color: GS.textFaint, fontSize: 10, fontFamily: "var(--font-mono)", whiteSpace: 'nowrap' }}>
                    {formatEventTimestamp(alert.timestamp)}
                  </div>
                  {/* Threat score */}
                  <div
                    style={{
                      width: 36,
                      textAlign: 'right',
                      color: (alert.threat_score ?? 0) >= 0.75 ? GS.danger : GS.warn,
                      fontSize: 11,
                      fontFamily: "var(--font-mono)",
                      fontWeight: 700,
                    }}
                  >
                    {alert.threat_score !== undefined && alert.threat_score !== null
                      ? `${(alert.threat_score * 100).toFixed(0)}%`
                      : '—'}
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </div>

        {/* Self-healing activity */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid rgba(43,42,40,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Cpu size={14} style={{ color: GS.success }} />
              <span style={{ color: GS.success, fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600 }}>
                Self-Healing Activity
              </span>
            </div>
            <Link
              to="/healing"
              style={{ display: 'flex', alignItems: 'center', gap: 4, color: GS.primary, fontSize: 11, fontFamily: "var(--font-mono)", textDecoration: 'none' }}
            >
              View all <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recentHealing.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: GS.textFaint, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                No healing events. System stable.
              </div>
            ) : (
              recentHealing.map((ev, i) => (
                <motion.div
                  key={ev.id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: GS.surfaceRaised,
                    border: '1px solid rgba(52,99,72,0.15)',
                    borderLeft: '2px solid rgba(52,99,72,0.5)',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--font-sans)", color: GS.success }}>
                        {ev.action}
                      </span>
                      <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: GS.textSubtle }}>
                        {ev.edges_severed || 0} edges cut
                      </span>
                    </div>
                    <div style={{ color: GS.text, fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {ev.ip}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: GS.success, fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {ev.network_stability_before != null && ev.network_stability_after != null
                        ? `${ev.network_stability_before}%→${ev.network_stability_after}%`
                        : (ev.network_stability_after != null ? `${ev.network_stability_after}%` : '—')}
                    </div>
                    <div style={{ color: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)" }}>
                      {ev.duration_ms != null ? `${ev.duration_ms}ms` : (ev.responseTimeMs != null ? `${ev.responseTimeMs}ms` : '—')}
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Row 3: Mini timeline ── */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid rgba(43,42,40,0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={14} style={{ color: GS.primary }} />
            <span style={{ color: GS.primary, fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600 }}>
              Threat Timeline
            </span>
          </div>
          <Link
            to="/timeline"
            style={{ display: 'flex', alignItems: 'center', gap: 4, color: GS.primary, fontSize: 11, fontFamily: "var(--font-mono)", textDecoration: 'none' }}
          >
            View full timeline <ChevronRight size={12} />
          </Link>
        </div>
        <div style={{ height: 180, padding: '8px 8px 4px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeline} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="dash-threats-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={GS.danger} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={GS.danger} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="dash-blocked-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={GS.success} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={GS.success} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(211,206,195,0.9)" vertical={false} />
              <XAxis dataKey="time" tickFormatter={formatTimelineTick} tick={{ fill: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <Tooltip
                labelFormatter={formatTimelineTick}
                contentStyle={{ background: GS.surfaceRaised, border: `1px solid ${GS.border}`, borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 10, color: GS.text }}
                itemStyle={{ color: GS.textMuted }}
              />
              <Area type="monotone" dataKey="threats" stroke={GS.danger} fill="url(#dash-threats-grad)" strokeWidth={1.5} dot={false} name="Threats" />
              <Area type="monotone" dataKey="blocked" stroke={GS.success} fill="url(#dash-blocked-grad)" strokeWidth={1.5} dot={false} name="Blocked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function StatCard({ title, value, sub, icon, accent, pulse = false, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className="gs-panel"
      style={{ padding: '18px 20px', position: 'relative', overflow: 'hidden' }}
    >
      {/* Accent glow */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: `${accent}08`,
          filter: 'blur(30px)',
          pointerEvents: 'none',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ color: GS.textSubtle, fontSize: 12, fontFamily: "var(--font-sans)" }}>
          {title}
        </span>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: `${accent}12`,
            border: `1px solid ${accent}25`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </div>
      </div>
      <div
        style={{
          color: accent,
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: 28,
          lineHeight: 1,
          marginBottom: 6,
        }}
        className={pulse ? 'pulse-threat' : ''}
      >
        {value}
      </div>
      <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "var(--font-mono)" }}>
        {sub}
      </div>
    </motion.div>
  )
}
