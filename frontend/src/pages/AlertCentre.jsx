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
import { formatEventTimestamp, formatTimelineTick } from '../utils/formatTimestamp'
import { loadAlertStatuses, setAlertStatus, clearAlertStatus } from '../utils/alertStatus'
import { updateIncidentStatus } from '../services/api'
import useSessionUser from '../hooks/useSessionUser'
import { canTriage, triageFailureMessage, TRIAGE_DENIED_REASON } from '../utils/triage'
import { GS } from '../constants/colors'

const SEVERITY_COLORS = { critical: GS.danger, warning: GS.warn, info: GS.primary }
const SOURCE_LABELS = {
  threat_feed: 'Threat feed',
  self_healing: 'Self-healing',
  blockchain: 'Blockchain',
  system: 'System',
}
const SOURCE_COLORS = {
  threat_feed: GS.danger,
  self_healing: GS.success,
  blockchain: GS.chain,
  system: GS.textSubtle,
}

const STATUS_CYCLE = { open: 'acknowledged', acknowledged: 'resolved', resolved: 'open' }

export default function AlertCentre() {
  const navigate = useNavigate()
  const { alerts: unified, stats } = useAlerts()
  const { timeline, dataErrors } = useGraphStore()
  const applyAlertStatus = useGraphStore((s) => s.applyAlertStatus)
  const mayTriage = canTriage(useSessionUser().role)
  // Why the last triage change did not save (FE-24): shown, never only logged.
  const [triageError, setTriageError] = useState(null)

  // Error.md H5 — triage is server-authoritative (PATCH /api/v1/incidents/{id}
  // /status). localStorage is only an optimistic layer while the PATCH is in
  // flight: cleared when the server confirms AND when it refuses or does not
  // answer (FE-24) -- a kept entry used to override the server for ever.
  const [localStatuses, setLocalStatuses] = useState(() => loadAlertStatuses())
  const [filterSeverity, setFilterSeverity] = useState('All')
  const [filterStatus, setFilterStatus] = useState('All')
  const [filterSource, setFilterSource] = useState('All')

  // Merge local overrides ({status, at} shape from utils/alertStatus)
  const alertsWithLocal = useMemo(() =>
    unified.map((a) => ({ ...a, status: localStatuses[a.id]?.status || a.status })),
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
    const alert = unified.find((a) => a.id === id)
    // Only incidents have a server row to save to; healing notices are records.
    if (!mayTriage || alert?.incidentId == null) return
    setTriageError(null)
    const cur = localStatuses[id]?.status || alert?.status || 'open'
    const next = STATUS_CYCLE[cur] || 'open'
    // Optimistic local write for instant feedback.
    setLocalStatuses((prev) => setAlertStatus(prev, id, next))
    updateIncidentStatus(alert.incidentId, next)
      .then((res) => {
        // Audit B18 — the store takes the confirmed status BEFORE the
        // optimistic entry is dropped, so the row never shows the old one.
        applyAlertStatus(
          alert.raw?.id, res?.alert_status ?? next,
          res?.acknowledged_at ?? (next === 'acknowledged' ? new Date().toISOString() : undefined),
        )
        setLocalStatuses((prev) => clearAlertStatus(prev, id))
      })
      .catch((err) => {
        // The server's status stands: drop the optimistic value and say why.
        setLocalStatuses((prev) => clearAlertStatus(prev, id))
        setTriageError(`${alert.title}: ${triageFailureMessage(err)}`)
      })
  }

  // Donut data
  const donutData = [
    // FE-25 — these are triage states, not severities.
    { name: 'Open', value: stats.open, color: GS.danger },
    { name: 'Acknowledged', value: stats.acked, color: GS.warn },
    { name: 'Resolved', value: stats.resolved, color: GS.success },
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
        <h1 style={{ color: GS.text, fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Alert Centre
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <p style={{ color: GS.textSubtle, fontFamily: "var(--font-sans)", fontSize: 14 }}>
            Unified incident hub · Acknowledge / resolve state is saved on the server
          </p>
          <DataFreshnessBadge dataErrors={{ alerts: dataErrors.alerts, timeline: dataErrors.timeline }} />
        </div>
        {!mayTriage && (
          <p role="note" style={{ color: GS.textMuted, fontFamily: "var(--font-mono)", fontSize: 11, marginTop: 6 }}>
            {TRIAGE_DENIED_REASON}
          </p>
        )}
        {triageError && (
          <div
            role="alert"
            style={{
              marginTop: 8, padding: '8px 12px', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 10,
              border: '1px solid rgba(180,19,46,0.3)', background: 'rgba(180,19,46,0.08)',
              color: GS.danger, fontFamily: "var(--font-mono)", fontSize: 11,
            }}
          >
            <span style={{ flex: 1 }}>{triageError}</span>
            <button
              onClick={() => setTriageError(null)}
              style={{ background: 'none', border: 'none', color: GS.danger, cursor: 'pointer', fontSize: 12, fontFamily: "var(--font-sans)" }}
              aria-label="Dismiss"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Stats bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, flexShrink: 0 }}>
        <StatTile layout="row" label="Open" value={stats.open} color={GS.danger} />
        <StatTile layout="row" label="Acknowledged" value={stats.acked} color={GS.warn} />
        <StatTile layout="row" label="Resolved" value={stats.resolved} color={GS.success} />
        <StatTile layout="row" label="MTTA" value={stats.mttaSamples > 0 ? `${stats.mttaMin}m` : '—'} color={GS.primary} />
      </div>

      {/* Filter bar */}
      <div className="gs-panel" style={{ padding: '10px 14px', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Filter size={13} style={{ color: GS.textSubtle }} />
        {['All', 'critical', 'warning', 'info'].map((s) => (
          <FilterPill key={s} label={s} active={filterSeverity === s} onClick={() => setFilterSeverity(s)}
            color={SEVERITY_COLORS[s] || GS.textSubtle} />
        ))}
        <Sep />
        {['All', 'open', 'acknowledged', 'resolved'].map((s) => (
          <FilterPill key={s} label={s} active={filterStatus === s} onClick={() => setFilterStatus(s)} color={GS.textMuted} />
        ))}
        <Sep />
        {['All', 'threat_feed', 'self_healing', 'blockchain', 'system'].map((s) => (
          <FilterPill key={s} label={s === 'All' ? 'All' : SOURCE_LABELS[s] || s} active={filterSource === s}
            onClick={() => setFilterSource(s)} color={SOURCE_COLORS[s] || GS.textSubtle} />
        ))}
      </div>

      {/* Content: alerts list + right sidebar */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16, overflow: 'hidden', minHeight: 0 }}>
        {/* Alert list */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <AnimatePresence initial={false}>
            {filtered.map((alert, i) => {
              const sevColor = SEVERITY_COLORS[alert.severity] || GS.textSubtle
              const srcColor = SOURCE_COLORS[alert.source] || GS.textSubtle
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
                          fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700,
                          padding: '2px 6px', borderRadius: 4, background: `${srcColor}15`, color: srcColor, border: `1px solid ${srcColor}30`,
                        }}>
                          {SOURCE_LABELS[alert.source] || alert.source}
                        </span>
                        <span style={{ color: GS.text, fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600 }}>
                          {alert.title}
                        </span>
                      </div>

                      {/* Row 2: IP + relative time */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        {alert.nodeIp && (
                          <span style={{ color: GS.primary, fontSize: 11, fontFamily: "var(--font-mono)" }}>
                            {alert.nodeIp}
                          </span>
                        )}
                        <span style={{ color: GS.textFaint, fontSize: 10, fontFamily: "var(--font-mono)" }}>
                          {relativeTime(alert.createdAt)}
                        </span>
                      </div>
                    </div>

                    {/* Right: status + action */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, flexShrink: 0 }}>
                      {/* Audit B17 — enforcement state, shown beside triage, never instead of it */}
                      {alert.isBlocked && (
                        <span
                          title="The source host is blocked. That is an enforcement state; this alert stays open until someone acknowledges or resolves it."
                          style={{
                            fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700,
                            padding: '3px 8px', borderRadius: 4, background: 'rgba(43,42,40,0.08)', color: GS.primary,
                          }}
                        >
                          Host blocked
                        </span>
                      )}
                      {/* Cycle status button. Healing notices have no server row to
                          save to, and a read-only role may not triage: both disabled. */}
                      <button
                        onClick={() => cycleStatus(alert.id)}
                        disabled={!mayTriage || alert.incidentId == null}
                        style={{
                          fontSize: 12, fontFamily: "var(--font-sans)", fontWeight: 600,
                          padding: '3px 8px', borderRadius: 999,
                          cursor: !mayTriage || alert.incidentId == null ? 'not-allowed' : 'pointer',
                          opacity: !mayTriage || alert.incidentId == null ? 0.6 : 1,
                          border: '1px solid',
                          ...(status === 'open'
                            ? { background: 'rgba(180,19,46,0.1)', color: GS.danger, borderColor: 'rgba(180,19,46,0.3)' }
                            : status === 'acknowledged'
                            ? { background: 'rgba(133,88,8,0.1)', color: GS.warn, borderColor: 'rgba(133,88,8,0.3)' }
                            : { background: 'rgba(52,99,72,0.1)', color: GS.success, borderColor: 'rgba(52,99,72,0.3)' }),
                        }}
                        title={alert.incidentId == null
                          ? 'A self-healing notice is a record, not an incident: it has no status to change.'
                          : mayTriage ? 'Click to cycle status' : TRIAGE_DENIED_REASON}
                      >
                        {status}
                      </button>

                      {/* View details */}
                      <button
                        onClick={() => navigate(alert.relatedRoute)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          background: 'none', border: 'none',
                          color: GS.primary, fontSize: 12, fontFamily: "var(--font-sans)",
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
            <div style={{ textAlign: 'center', padding: '60px 0', color: GS.textFaint }}>
              <Bell size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
              <div style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>No alerts match the current filter</div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          {/* Donut chart */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: GS.textSubtle, fontSize: 12, fontFamily: "var(--font-sans)", marginBottom: 12 }}>
              Alerts by Status
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
                    contentStyle={{ background: GS.surfaceRaised, border: `1px solid ${GS.border}`, borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 10 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', color: GS.textFaint, fontSize: 11, fontFamily: "var(--font-mono)" }}>
                All clear
              </div>
            )}
          </div>

          {/* Sparkline: alerts per hour */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: GS.textSubtle, fontSize: 12, fontFamily: "var(--font-sans)", marginBottom: 12 }}>
              Threats per 5 min (last hour)
            </div>
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={sparkData} margin={{ top: 4, right: 4, left: -30, bottom: 0 }}>
                {/* Error.md U5 — timeline points are ISO datetimes; without a
                    tickFormatter the x-axis rendered the raw full ISO string. */}
                <XAxis
                  dataKey="time"
                  tickFormatter={formatTimelineTick}
                  minTickGap={32}
                  tick={{ fill: GS.textFaint, fontSize: 8, fontFamily: "var(--font-mono)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis tick={false} axisLine={false} />
                <Tooltip
                  labelFormatter={formatTimelineTick}
                  contentStyle={{ background: GS.surfaceRaised, border: `1px solid ${GS.border}`, borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 10 }}
                />
                <Line type="monotone" dataKey="threats" stroke={GS.danger} strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* MTTA card */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: GS.textSubtle, fontSize: 12, fontFamily: "var(--font-sans)", marginBottom: 8 }}>
              Mean Time To Acknowledge
            </div>
            <div style={{ color: GS.primary, fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 28 }}>
              {stats.mttaSamples > 0 ? `${stats.mttaMin}m` : '—'}
            </div>
            <div style={{ color: GS.textFaint, fontSize: 10, fontFamily: "var(--font-mono)", marginTop: 4 }}>
              {stats.mttaSamples > 0
                ? `Based on ${stats.mttaSamples} acknowledged alert${stats.mttaSamples === 1 ? '' : 's'} (this device)`
                : 'No alerts acknowledged yet'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


function Sep() {
  return <div style={{ width: 1, height: 18, background: 'rgba(43,42,40,0.10)', flexShrink: 0 }} />
}
