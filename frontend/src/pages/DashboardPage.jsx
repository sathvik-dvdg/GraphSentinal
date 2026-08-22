// [Windows] GraphSentinel — Susheep
// DashboardPage — stripped to overview only (stat cards + summaries + mini timeline)
// WebSocket / simulation logic has moved to AppShell
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

export default function DashboardPage() {
  const { stats, alerts, healingEvents, timeline, dataErrors } = useGraphStore()

  const health = Math.max(0, Math.min(100, stats.system_health ?? 100))
  const healthColor = health >= 80 ? '#2ECC8A' : health >= 50 ? '#E8922A' : '#E03C3C'
  const healthLabel = health >= 80 ? 'Healthy' : health >= 50 ? 'Degraded' : 'Critical'

  const recentThreats = [...alerts].slice(0, 5)
  const recentHealing = [...healingEvents].slice(0, 3)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Page header */}
      <div>
        <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Dashboard
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <p style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
            Network overview · Real-time threat summary
          </p>
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
          icon={<Network size={18} style={{ color: '#4F6EF7' }} />}
          accent="#4F6EF7"
          delay={0.06}
        />
        <StatCard
          title="Threats (24h)"
          value={stats.active_threats ?? 0}
          sub={stats.active_threats > 0 ? '⚠ Action required' : 'All clear'}
          icon={<ShieldAlert size={18} style={{ color: '#E03C3C' }} />}
          accent="#E03C3C"
          pulse={stats.active_threats > 0}
          delay={0.12}
        />
        <StatCard
          title="Nodes Isolated"
          value={stats.blocked_ips ?? 0}
          sub="Self-healing active"
          icon={<Shield size={18} style={{ color: '#2ECC8A' }} />}
          accent="#2ECC8A"
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
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ShieldAlert size={14} style={{ color: '#E03C3C' }} />
              <span style={{ color: '#E03C3C', fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Recent Threats
              </span>
            </div>
            <Link
              to="/threats"
              style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#4F6EF7', fontSize: 11, fontFamily: "'DM Mono', monospace", textDecoration: 'none' }}
            >
              View all <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recentThreats.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: '#3D4560', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
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
                    background: '#1E1E1E',
                    border: `1px solid ${alert.severity === 'critical' ? 'rgba(224,60,60,0.2)' : 'rgba(232,146,42,0.15)'}`,
                    borderLeft: `2px solid ${alert.severity === 'critical' ? '#E03C3C' : '#E8922A'}`,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ fontSize: 9, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: alert.severity === 'critical' ? '#E03C3C' : '#E8922A', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {alert.severity}
                      </span>
                      <span style={{ fontSize: 10, fontFamily: "'DM Mono', monospace", color: '#8A95B0' }}>
                        {alert.attack_type}
                      </span>
                    </div>
                    <div style={{ color: '#E8EDF5', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                      {alert.source_ip}
                    </div>
                  </div>
                  <div style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace", whiteSpace: 'nowrap' }}>
                    {formatEventTimestamp(alert.timestamp)}
                  </div>
                  {/* Threat score */}
                  <div
                    style={{
                      width: 36,
                      textAlign: 'right',
                      color: alert.threat_score >= 0.75 ? '#E03C3C' : '#E8922A',
                      fontSize: 11,
                      fontFamily: "'DM Mono', monospace",
                      fontWeight: 700,
                    }}
                  >
                    {(alert.threat_score * 100).toFixed(0)}%
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
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Cpu size={14} style={{ color: '#2ECC8A' }} />
              <span style={{ color: '#2ECC8A', fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Self-Healing Activity
              </span>
            </div>
            <Link
              to="/healing"
              style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#4F6EF7', fontSize: 11, fontFamily: "'DM Mono', monospace", textDecoration: 'none' }}
            >
              View all <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recentHealing.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: '#3D4560', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
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
                    background: '#1E1E1E',
                    border: '1px solid rgba(46,204,138,0.15)',
                    borderLeft: '2px solid rgba(46,204,138,0.5)',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ fontSize: 9, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: '#2ECC8A', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {ev.action}
                      </span>
                      <span style={{ fontSize: 10, fontFamily: "'DM Mono', monospace", color: '#5A6480' }}>
                        {ev.edges_severed} edges cut
                      </span>
                    </div>
                    <div style={{ color: '#E8EDF5', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                      {ev.ip}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: '#2ECC8A', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                      {ev.network_stability_before}%→{ev.network_stability_after}%
                    </div>
                    <div style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace" }}>
                      {ev.duration_ms}ms
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
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={14} style={{ color: '#4F6EF7' }} />
            <span style={{ color: '#4F6EF7', fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Threat Timeline
            </span>
          </div>
          <Link
            to="/timeline"
            style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#4F6EF7', fontSize: 11, fontFamily: "'DM Mono', monospace", textDecoration: 'none' }}
          >
            View full timeline <ChevronRight size={12} />
          </Link>
        </div>
        <div style={{ height: 180, padding: '8px 8px 4px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeline} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="dash-threats-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#E03C3C" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#E03C3C" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="dash-blocked-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#2ECC8A" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2ECC8A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(38,45,63,0.8)" vertical={false} />
              <XAxis dataKey="time" tickFormatter={formatTimelineTick} tick={{ fill: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
              <Tooltip
                labelFormatter={formatTimelineTick}
                contentStyle={{ background: '#1E1E1E', border: '1px solid #262D3F', borderRadius: 8, fontFamily: "'DM Mono', monospace", fontSize: 10, color: '#E8EDF5' }}
                itemStyle={{ color: '#8A95B0' }}
              />
              <Area type="monotone" dataKey="threats" stroke="#E03C3C" fill="url(#dash-threats-grad)" strokeWidth={1.5} dot={false} name="Threats" />
              <Area type="monotone" dataKey="blocked" stroke="#2ECC8A" fill="url(#dash-blocked-grad)" strokeWidth={1.5} dot={false} name="Blocked" />
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
        <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace", letterSpacing: '0.08em', textTransform: 'uppercase' }}>
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
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 700,
          fontSize: 28,
          lineHeight: 1,
          marginBottom: 6,
        }}
        className={pulse ? 'pulse-threat' : ''}
      >
        {value}
      </div>
      <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
        {sub}
      </div>
    </motion.div>
  )
}
