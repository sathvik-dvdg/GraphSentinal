// [Windows] GraphSentinel — Susheep
// TimelineAnalytics — full-page timeline chart with controls and breakdowns
import { useState, useMemo, useRef, useEffect } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { TrendingUp, Pause, Play } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { getTimeline } from '../services/api'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatTimelineTick } from '../utils/formatTimestamp'
import { GS } from '../constants/colors'

// No "All": the backend serves at most 30 days and reads `all` as `30d`, so the
// pill duplicated 30d under a name that claimed more (FE-26).
const TIME_RANGES = ['1h', '6h', '24h', '7d', '14d', '30d']
const RANGE_MS = { '1h': 3.6e6, '6h': 2.16e7, '24h': 8.64e7, '7d': 6.048e8, '14d': 1.2096e9, '30d': 2.592e9 }
// One colour per label the backend can send (utils/attackTypes); DoSHulk and
// Unknown had none, so those incidents were not drawn (FE-26).
const ATTACK_COLORS_MAP = {
  Manual: GS.success,
  DoSHulk: GS.attackDosHulk,
  Unknown: GS.textSubtle,
  DDoS: GS.danger,
  SSHBrute: GS.warn,
  PortScan: GS.primary,
  Botnet: GS.chain,
  Heuristic: GS.statusSuspicious,
}

export default function TimelineAnalytics() {
  const { timeline, alerts, dataErrors } = useGraphStore()
  const [timeRange, setTimeRange] = useState('7d')
  const [timelineData, setTimelineData] = useState([])
  const [paused, setPaused] = useState(false)
  const [threshold, setThreshold] = useState(3)
  // "Now" for the range cut-off, refreshed with each timeline fetch: reading
  // the clock during render is impure (react-hooks/purity).
  const [now, setNow] = useState(() => Date.now())

  // Fetch timeline data whenever timeRange changes
  useEffect(() => {
    let active = true
    const fetchTimeline = async () => {
      try {
        const res = await getTimeline(timeRange)
        if (active && res?.data_points) {
          setTimelineData(res.data_points)
          setNow(Date.now())
        }
      } catch (err) {
        console.error('[TimelineAnalytics] Failed to fetch timeline for', timeRange, err)
      }
    }
    fetchTimeline()
    const interval = setInterval(() => {
      if (!paused) fetchTimeline()
    }, 10000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [timeRange, paused])

  // Error.md H4 — "Pause" freezes the chart: keep rendering snapshot captured at pause time
  const activeData = timelineData.length > 0 ? timelineData : timeline
  const frozenRef = useRef(activeData)
  if (!paused) frozenRef.current = activeData
  const chartData = paused ? frozenRef.current : activeData

  const isMultiDay = timeRange === '7d' || timeRange === '14d' || timeRange === '30d'

  // FE-26 — the breakdown and the type chart follow the selected range too. They
  // are built from the store's alerts, which hold the newest 50, so a long range
  // can show fewer than happened; the table heading says so.
  const alertsInRange = useMemo(() => {
    const cutoff = now - (RANGE_MS[timeRange] ?? RANGE_MS['7d'])
    return alerts.filter((a) => new Date(a.timestamp).getTime() >= cutoff)
  }, [alerts, timeRange, now])

  // Time breakdown from alerts (hourly for <=24h, daily for multi-day)
  const timeBreakdown = useMemo(() => {
    const buckets = {}
    alertsInRange.forEach((a) => {
      const d = new Date(a.timestamp)
      const key = isMultiDay
        ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : `${d.getHours().toString().padStart(2, '0')}:00`
      if (!buckets[key]) buckets[key] = { time: key, threats: 0, blocked: 0 }
      buckets[key].threats += 1
      if (a.is_blocked) buckets[key].blocked += 1
    })
    return Object.values(buckets)
  }, [alertsInRange, isMultiDay])

  // Attack type over time (stacked bar — grouped by hour or day + type)
  const typeOverTime = useMemo(() => {
    const buckets = {}
    alertsInRange.forEach((a) => {
      const d = new Date(a.timestamp)
      const key = isMultiDay
        ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : `${d.getHours().toString().padStart(2, '0')}:00`
      if (!buckets[key]) {
        buckets[key] = { time: key }
        Object.keys(ATTACK_COLORS_MAP).forEach((k) => { buckets[key][k] = 0 })
      }
      const t = ATTACK_COLORS_MAP[a.attack_type] ? a.attack_type : 'Unknown'
      buckets[key][t] = (buckets[key][t] || 0) + 1
    })
    return Object.values(buckets)
  }, [alertsInRange, isMultiDay])

  // Find anomaly spikes (>= threshold)
  const anomalyPeaks = chartData.filter((d) => d.threats >= threshold)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: GS.text, fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Timeline
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <p style={{ color: GS.textSubtle, fontFamily: "var(--font-sans)", fontSize: 14 }}>
              Threat patterns over time · Anomaly detection
            </p>
            <DataFreshnessBadge dataErrors={{ timeline: dataErrors.timeline, alerts: dataErrors.alerts }} />
          </div>
        </div>
        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => setPaused((p) => !p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 999,
              border: `1px solid ${paused ? 'rgba(133,88,8,0.4)' : 'rgba(52,99,72,0.3)'}`,
              background: paused ? 'rgba(133,88,8,0.1)' : 'rgba(52,99,72,0.08)',
              color: paused ? GS.warn : GS.success,
              fontSize: 12, fontFamily: "var(--font-sans)", cursor: 'pointer',
            }}
          >
            {paused ? <Play size={12} /> : <Pause size={12} />}
            {paused ? 'Paused' : 'Live'}
          </button>

          {/* Time range pills */}
          <div style={{ display: 'flex', gap: 4, background: GS.surfaceRaised, border: '1px solid rgba(43,42,40,0.10)', borderRadius: 8, padding: 3 }}>
            {TIME_RANGES.map((t) => (
              <button
                key={t}
                onClick={() => setTimeRange(t)}
                style={{
                  padding: '4px 12px', borderRadius: 999, border: 'none',
                  background: timeRange === t ? 'rgba(43,42,40,0.2)' : 'transparent',
                  color: timeRange === t ? GS.primary : GS.textSubtle,
                  fontSize: 12, fontFamily: "var(--font-sans)", cursor: 'pointer',
                  fontWeight: timeRange === t ? 700 : 400,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main chart */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(43,42,40,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={14} style={{ color: GS.primary }} />
            <span style={{ color: GS.primary, fontSize: 12, fontFamily: "var(--font-sans)", fontWeight: 600 }}>
              Threat Activity ({timeRange})
            </span>
          </div>
          {/* Threshold control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: GS.textSubtle, fontSize: 11, fontFamily: "var(--font-mono)" }}>Anomaly threshold:</span>
            <input
              type="range" min={1} max={10} value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              style={{ accentColor: GS.warn, width: 80 }}
            />
            <span style={{ color: GS.warn, fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 700, minWidth: 16 }}>
              {threshold}
            </span>
          </div>
        </div>

        <div style={{ height: 320, padding: '16px 16px 8px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="full-threats-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={GS.danger} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={GS.danger} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="full-blocked-grad" x1="0" y1="0" x2="0" y2="1">
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
              <Legend iconType="circle" wrapperStyle={{ fontSize: 10, fontFamily: "var(--font-mono)", color: GS.textSubtle, paddingTop: 8 }} />

              {/* Threshold reference line */}
              <ReferenceLine y={threshold} stroke={GS.warn} strokeDasharray="6 3" strokeOpacity={0.7}
                label={{ value: `Threshold: ${threshold}`, fill: GS.warn, fontSize: 10, fontFamily: "var(--font-mono)", position: 'insideTopRight' }} />

              {/* Anomaly spike markers */}
              {anomalyPeaks.map((peak) => (
                <ReferenceLine key={peak.time} x={peak.time} stroke={GS.danger} strokeDasharray="4 2" strokeOpacity={0.4} />
              ))}

              <Area type="monotone" dataKey="threats" stroke={GS.danger} fill="url(#full-threats-grad)" strokeWidth={1.5} dot={false} name="Threats" />
              <Area type="monotone" dataKey="blocked" stroke={GS.success} fill="url(#full-blocked-grad)" strokeWidth={1.5} dot={false} name="Blocked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Below chart: 2 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Breakdown table */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(43,42,40,0.08)' }}>
            <span style={{ color: GS.textMuted, fontSize: 12, fontFamily: "var(--font-sans)", fontWeight: 600 }}>
              {isMultiDay ? 'Daily Breakdown' : 'Hourly Breakdown'} · newest 50 alerts
            </span>
          </div>
          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            {timeBreakdown.length > 0 ? (
              <table className="gs-table" style={{ width: '100%' }}>
                <thead style={{ background: GS.surfaceHeader }}>
                  <tr>
                    <th>{isMultiDay ? 'Date' : 'Hour'}</th>
                    <th>Threats</th>
                    <th>Blocked</th>
                  </tr>
                </thead>
                <tbody>
                  {timeBreakdown.map((row) => (
                    <tr key={row.time}>
                      <td style={{ color: GS.textSubtle, fontFamily: "var(--font-mono)" }}>{row.time}</td>
                      <td style={{ color: GS.danger, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{row.threats}</td>
                      <td style={{ color: GS.success, fontFamily: "var(--font-mono)" }}>{row.blocked}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 0', color: GS.textFaint, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                No breakdown data yet
              </div>
            )}
          </div>
        </div>

        {/* Attack type over time */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(43,42,40,0.08)' }}>
            <span style={{ color: GS.textMuted, fontSize: 12, fontFamily: "var(--font-sans)", fontWeight: 600 }}>
              Attack Types Over Time
            </span>
          </div>
          <div style={{ height: 280, padding: '12px 8px 8px' }}>
            {typeOverTime.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeOverTime} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(211,206,195,0.8)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: GS.textFaint, fontSize: 9, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: GS.surfaceRaised, border: `1px solid ${GS.border}`, borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 10, color: GS.text }} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 10, fontFamily: "var(--font-mono)", color: GS.textSubtle }} />
                  {Object.entries(ATTACK_COLORS_MAP).map(([type, color]) => (
                    <Bar key={type} dataKey={type} stackId="a" fill={color} fillOpacity={0.8} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: GS.textFaint, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                No attack type data yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
