// [Windows] GraphSentinel — Susheep
// AlertCentre — unified notification hub with acknowledge/resolve workflow
import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, ChevronRight, Filter } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAlerts } from '../hooks/useAlerts'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import useGraphStore from '../store/useGraphStore'
import StatTile from '../components/ui/StatTile'
import FilterPill from '../components/ui/FilterPill'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatEventTimestamp } from '../utils/formatTimestamp'

const SEVERITY_COLORS = { critical: '#E03C3C', warning: '#b7791f', info: '#3b56d9' }
const SOURCE_LABELS = {
  threat_feed: 'THREAT FEED',
  self_healing: 'SELF-HEALING',
  blockchain: 'BLOCKCHAIN',
  system: 'SYSTEM',
}
const SOURCE_COLORS = {
  threat_feed: '#E03C3C',
  self_healing: '#12a672',
  blockchain: '#7c3aed',
  system: '#727a86',
}

const STATUS_CYCLE = { open: 'acknowledged', acknowledged: 'resolved', resolved: 'open' }

export default function AlertCentre() {
  const navigate = useNavigate()
  const { alerts: unified, stats } = useAlerts()
  const { timeline, dataErrors } = useGraphStore()

  const [localStatuses, setLocalStatuses] = useState({})
  const [filterSeverity, setFilterSeverity] = useState('All')
  const [filterStatus, setFilterStatus] = useState('All')
  const [filterSource, setFilterSource] = useState('All')

  // Merge local overrides
  const alertsWithLocal = useMemo(() =>
    unified.map((a) => ({ ...a, status: localStatuses[a.id] || a.status })),
    [unified, localStatuses]
  )

  const filtered = useMemo(() =>
    alertsWithLocal.filter((a) => {
      if (filterSeverity !== 'All' && a.severity !== filterSeverity) return false
      if (filterStatus !== 'All' && a.status !== filterStatus) return false
      if (filterSource !== 'All' && a.source !== filterSource) return false
      return true
    }),
    [alertsWithLocal, filterSeverity, filterStatus, filterSource]
  )

  const cycleStatus = (id) => {
    setLocalStatuses((prev) => {
      const cur = prev[id] || unified.find((a) => a.id === id)?.status || 'open'
      return { ...prev, [id]: STATUS_CYCLE[cur] || 'open' }
    })
  }

  // Donut data
  const donutData = [
    { name: 'Critical', value: stats.open, color: '#E03C3C' },
    { name: 'Warning', value: stats.acked, color: '#b7791f' },
    { name: 'Resolved', value: stats.resolved, color: '#12a672' },
  ].filter((d) => d.value > 0)

  // Last 6h sparkline — reuse timeline data
  const sparkData = timeline.slice(-12)

  // Error.md #37 pattern: a relative label past ~1 day is ambiguous ("29h
  // ago" doesn't say which day) — fall back to a real date+time.
  const relativeTime = (ts) => {
    const diff = Date.now() - ts
    if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return formatEventTimestamp(ts)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 108px)' }}>
      {/* Header */}
      <div>
        <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Alert Centre
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
            Unified incident hub · Acknowledge and resolve alerts
          </p>
          <DataFreshnessBadge dataErrors={{ alerts: dataErrors.alerts, timeline: dataErrors.timeline }} />
        </div>
      </div>

      {/* Stats bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, flexShrink: 0 }}>
        <StatTile layout="row" label="Open" value={stats.open} color="#E03C3C" />
        <StatTile layout="row" label="Acknowledged" value={stats.acked} color="#b7791f" />
        <StatTile layout="row" label="Resolved" value={stats.resolved} color="#12a672" />
        <StatTile layout="row" label="MTTA" value={`${stats.mttaMin}m`} color="#3b56d9" />
      </div>

      {/* Filter bar */}
      <div className="gs-panel" style={{ padding: '10px 14px', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Filter size={13} style={{ color: '#727a86' }} />
        {['All', 'critical', 'warning', 'info'].map((s) => (
          <FilterPill key={s} label={s} active={filterSeverity === s} onClick={() => setFilterSeverity(s)}
            color={SEVERITY_COLORS[s] || '#727a86'} />
        ))}
        <Sep />
        {['All', 'open', 'acknowledged', 'resolved'].map((s) => (
          <FilterPill key={s} label={s} active={filterStatus === s} onClick={() => setFilterStatus(s)} color="#5a616e" />
        ))}
        <Sep />
        {['All', 'threat_feed', 'self_healing', 'blockchain', 'system'].map((s) => (
          <FilterPill key={s} label={s === 'All' ? 'All' : SOURCE_LABELS[s] || s} active={filterSource === s}
            onClick={() => setFilterSource(s)} color={SOURCE_COLORS[s] || '#727a86'} />
        ))}
      </div>

      {/* Content: alerts list + right sidebar */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16, overflow: 'hidden', minHeight: 0 }}>
        {/* Alert list */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <AnimatePresence initial={false}>
            {filtered.map((alert, i) => {
              const sevColor = SEVERITY_COLORS[alert.severity] || '#727a86'
              const srcColor = SOURCE_COLORS[alert.source] || '#727a86'
              const status = alert.status

              return (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2, delay: i * 0.025 }}
                  className="gs-panel"
                  style={{ padding: '14px 16px', borderLeft: `3px solid ${sevColor}`, flexShrink: 0 }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                    {/* Left content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Row 1: source badge + title */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                        <span style={{
                          fontSize: 9, fontFamily: "'DM Mono', monospace", fontWeight: 700,
                          padding: '2px 6px', borderRadius: 4, letterSpacing: '0.06em',
                          background: `${srcColor}15`, color: srcColor, border: `1px solid ${srcColor}30`,
                        }}>
                          {SOURCE_LABELS[alert.source] || alert.source}
                        </span>
                        <span style={{ color: '#1b1f27', fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 600 }}>
                          {alert.title}
                        </span>
                      </div>

                      {/* Row 2: IP + relative time */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        {alert.nodeIp && (
                          <span style={{ color: '#3b56d9', fontSize: 11, fontFamily: "'DM Mono', monospace', cursor: 'pointer'" }}>
                            {alert.nodeIp}
                          </span>
                        )}
                        <span style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                          {relativeTime(alert.createdAt)}
                        </span>
                      </div>
                    </div>

                    {/* Right: status + action */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, flexShrink: 0 }}>
                      {/* Cycle status button */}
                      <button
                        onClick={() => cycleStatus(alert.id)}
                        style={{
                          fontSize: 9, fontFamily: "'DM Mono', monospace", fontWeight: 700,
                          padding: '3px 8px', borderRadius: 4, cursor: 'pointer',
                          letterSpacing: '0.06em', textTransform: 'uppercase', border: '1px solid',
                          ...(status === 'open'
                            ? { background: 'rgba(224,60,60,0.1)', color: '#E03C3C', borderColor: 'rgba(224,60,60,0.3)' }
                            : status === 'acknowledged'
                            ? { background: 'rgba(232,146,42,0.1)', color: '#b7791f', borderColor: 'rgba(232,146,42,0.3)' }
                            : { background: 'rgba(46,204,138,0.1)', color: '#12a672', borderColor: 'rgba(46,204,138,0.3)' }),
                        }}
                        title="Click to cycle status"
                      >
                        {status}
                      </button>

                      {/* View details */}
                      <button
                        onClick={() => navigate(alert.relatedRoute)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          background: 'none', border: 'none',
                          color: '#3b56d9', fontSize: 11, fontFamily: "'DM Mono', monospace",
                          cursor: 'pointer',
                        }}
                      >
                        View <ChevronRight size={11} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: '#9aa1ad' }}>
              <Bell size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
              <div style={{ fontSize: 12, fontFamily: "'DM Mono', monospace" }}>No alerts match the current filter</div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          {/* Donut chart */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Open by Severity
            </div>
            {donutData.length > 0 ? (
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={donutData} cx="50%" cy="50%" innerRadius={40} outerRadius={60} paddingAngle={3} dataKey="value">
                    {donutData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#f0f2f5', border: '1px solid #e2e5ea', borderRadius: 8, fontFamily: "'DM Mono', monospace", fontSize: 10 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9aa1ad', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                All clear
              </div>
            )}
          </div>

          {/* Sparkline: alerts per hour */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Alerts / Hour (last 6h)
            </div>
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={sparkData} margin={{ top: 4, right: 4, left: -30, bottom: 0 }}>
                <XAxis dataKey="time" tick={{ fill: '#9aa1ad', fontSize: 8, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
                <YAxis tick={false} axisLine={false} />
                <Line type="monotone" dataKey="threats" stroke="#E03C3C" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* MTTA card */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
              Mean Time To Acknowledge
            </div>
            <div style={{ color: '#3b56d9', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 28 }}>
              {stats.mttaMin}m
            </div>
            <div style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>
              Based on {stats.acked} acknowledged alerts
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


function Sep() {
  return <div style={{ width: 1, height: 18, background: 'rgba(17,20,26,0.10)', flexShrink: 0 }} />
}
