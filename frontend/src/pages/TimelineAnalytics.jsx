// [Windows] GraphSentinel — Susheep
// TimelineAnalytics — full-page timeline chart with controls and breakdowns
import { useState, useMemo, useRef } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { TrendingUp, Pause, Play } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatTimelineTick } from '../utils/formatTimestamp'

const TIME_RANGES = ['1h', '6h', '24h', '7d']
const ATTACK_COLORS_MAP = { DDoS: '#E03C3C', SSHBrute: '#b7791f', PortScan: '#3b56d9', Botnet: '#7c3aed' }

export default function TimelineAnalytics() {
  const { timeline, alerts, dataErrors } = useGraphStore()
  const [timeRange, setTimeRange] = useState('24h')
  const [paused, setPaused] = useState(false)
  const [threshold, setThreshold] = useState(3)

  // Error.md H4 — "Pause" now actually freezes the chart: when paused we keep
  // rendering the snapshot captured at the moment the button was pressed
  // instead of the live `timeline` from the store.
  const frozenRef = useRef(timeline)
  if (!paused) frozenRef.current = timeline
  const chartData = paused ? frozenRef.current : timeline

  // Hourly breakdown from alerts
  const hourlyBreakdown = useMemo(() => {
    const buckets = {}
    alerts.forEach((a) => {
      const d = new Date(a.timestamp)
      const key = `${d.getHours().toString().padStart(2, '0')}:00`
      if (!buckets[key]) buckets[key] = { hour: key, threats: 0, blocked: 0 }
      buckets[key].threats += 1
      if (a.is_blocked) buckets[key].blocked += 1
    })
    return Object.values(buckets).sort((a, b) => a.hour.localeCompare(b.hour))
  }, [alerts])

  // Attack type over time (stacked bar — group by hour + type)
  const typeOverTime = useMemo(() => {
    const buckets = {}
    alerts.forEach((a) => {
      const d = new Date(a.timestamp)
      const key = `${d.getHours().toString().padStart(2, '0')}:00`
      if (!buckets[key]) buckets[key] = { time: key }
      buckets[key][a.attack_type] = (buckets[key][a.attack_type] || 0) + 1
    })
    return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time))
  }, [alerts])

  // Find anomaly spikes (>= threshold)
  const anomalyPeaks = chartData.filter((d) => d.threats >= threshold)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Timeline Analytics
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
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
              padding: '6px 14px', borderRadius: 6,
              border: `1px solid ${paused ? 'rgba(232,146,42,0.4)' : 'rgba(46,204,138,0.3)'}`,
              background: paused ? 'rgba(232,146,42,0.1)' : 'rgba(46,204,138,0.08)',
              color: paused ? '#b7791f' : '#12a672',
              fontSize: 11, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
            }}
          >
            {paused ? <Play size={12} /> : <Pause size={12} />}
            {paused ? 'Paused' : 'Live'}
          </button>

          {/* Time range pills */}
          <div style={{ display: 'flex', gap: 4, background: '#f0f2f5', border: '1px solid rgba(17,20,26,0.10)', borderRadius: 8, padding: 3 }}>
            {TIME_RANGES.map((t) => (
              <button
                key={t}
                onClick={() => setTimeRange(t)}
                style={{
                  padding: '4px 12px', borderRadius: 6, border: 'none',
                  background: timeRange === t ? 'rgba(79,110,247,0.2)' : 'transparent',
                  color: timeRange === t ? '#3b56d9' : '#727a86',
                  fontSize: 11, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
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
        <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(17,20,26,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={14} style={{ color: '#3b56d9' }} />
            <span style={{ color: '#3b56d9', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Threat Activity
            </span>
          </div>
          {/* Threshold control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#727a86', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>Anomaly threshold:</span>
            <input
              type="range" min={1} max={10} value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              style={{ accentColor: '#b7791f', width: 80 }}
            />
            <span style={{ color: '#b7791f', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 700, minWidth: 16 }}>
              {threshold}
            </span>
          </div>
        </div>

        <div style={{ height: 320, padding: '12px 8px 8px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="full-threats-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#E03C3C" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#E03C3C" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="full-blocked-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#12a672" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#12a672" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,229,234,0.9)" vertical={false} />
              <XAxis dataKey="time" tickFormatter={formatTimelineTick} tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
              <Tooltip
                labelFormatter={formatTimelineTick}
                contentStyle={{ background: '#f0f2f5', border: '1px solid #e2e5ea', borderRadius: 8, fontFamily: "'DM Mono', monospace", fontSize: 10, color: '#1b1f27' }}
                itemStyle={{ color: '#5a616e' }}
              />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 10, fontFamily: "'DM Mono', monospace", color: '#727a86', paddingTop: 8 }} />

              {/* Threshold reference line */}
              <ReferenceLine y={threshold} stroke="#b7791f" strokeDasharray="6 3" strokeOpacity={0.7}
                label={{ value: `Threshold: ${threshold}`, fill: '#b7791f', fontSize: 10, fontFamily: "'DM Mono', monospace", position: 'insideTopRight' }} />

              {/* Anomaly spike markers */}
              {anomalyPeaks.map((peak) => (
                <ReferenceLine key={peak.time} x={peak.time} stroke="#E03C3C" strokeDasharray="4 2" strokeOpacity={0.4} />
              ))}

              <Area type="monotone" dataKey="threats" stroke="#E03C3C" fill="url(#full-threats-grad)" strokeWidth={1.5} dot={false} name="Threats" />
              <Area type="monotone" dataKey="blocked" stroke="#12a672" fill="url(#full-blocked-grad)" strokeWidth={1.5} dot={false} name="Blocked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Below chart: 2 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Hourly breakdown table */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(17,20,26,0.08)' }}>
            <span style={{ color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Hourly Breakdown
            </span>
          </div>
          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            {hourlyBreakdown.length > 0 ? (
              <table className="gs-table" style={{ width: '100%' }}>
                <thead style={{ background: '#eef1f5' }}>
                  <tr>
                    <th>Hour</th>
                    <th>Threats</th>
                    <th>Blocked</th>
                  </tr>
                </thead>
                <tbody>
                  {hourlyBreakdown.map((row) => (
                    <tr key={row.hour}>
                      <td style={{ color: '#727a86', fontFamily: "'DM Mono', monospace" }}>{row.hour}</td>
                      <td style={{ color: '#E03C3C', fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{row.threats}</td>
                      <td style={{ color: '#12a672', fontFamily: "'DM Mono', monospace" }}>{row.blocked}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 0', color: '#9aa1ad', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
                No hourly data yet
              </div>
            )}
          </div>
        </div>

        {/* Attack type over time */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(17,20,26,0.08)' }}>
            <span style={{ color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Attack Types Over Time
            </span>
          </div>
          <div style={{ height: 280, padding: '12px 8px 8px' }}>
            {typeOverTime.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeOverTime} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,229,234,0.8)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#f0f2f5', border: '1px solid #e2e5ea', borderRadius: 8, fontFamily: "'DM Mono', monospace", fontSize: 10, color: '#1b1f27' }} />
                  {Object.entries(ATTACK_COLORS_MAP).map(([type, color]) => (
                    <Bar key={type} dataKey={type} stackId="a" fill={color} fillOpacity={0.8} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9aa1ad', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
                No attack type data yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
