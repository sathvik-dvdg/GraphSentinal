// [Windows] GraphSentinel — Susheep
// SelfHealing — full-page self-healing engine: event feed + stability gauge + log table
import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, ShieldCheck, Zap } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { formatEventTimestamp } from '../utils/formatTimestamp'

export default function SelfHealing() {
  const { healingEvents, stats } = useGraphStore()

  const stability = Math.max(0, Math.min(100, stats.system_health ?? 100))
  const avgResponseMs = useMemo(() => {
    if (healingEvents.length === 0) return 0
    const total = healingEvents.reduce((s, e) => s + (e.duration_ms || e.responseTimeMs || 0), 0)
    return Math.round(total / healingEvents.length)
  }, [healingEvents])
  const totalIsolations = healingEvents.filter((e) => e.action === 'ISOLATED').length

  const stabilityColor =
    stability >= 80 ? '#2ECC8A' :
    stability >= 50 ? '#E8922A' : '#E03C3C'

  const stabilityTrend =
    stability >= 75 ? '↑ Recovering' :
    stability >= 50 ? '→ Stable' : '↓ Degrading'

  // SVG gauge arc helpers
  const R = 72
  const CIRC = 2 * Math.PI * R
  const filled = CIRC * (stability / 100)
  const gap = CIRC - filled

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div>
        <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Self-Healing Engine
        </h1>
        <p style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          Autonomous threat response · Network stability monitoring
        </p>
      </div>

      {/* Stat cards row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <StatCard
          label="Total Isolations Today"
          value={totalIsolations}
          color="#E03C3C"
          icon={<Zap size={16} style={{ color: '#E03C3C' }} />}
        />
        <StatCard
          label="Avg Response Time"
          value={`${avgResponseMs}ms`}
          color="#4F6EF7"
          icon={<Cpu size={16} style={{ color: '#4F6EF7' }} />}
        />
        <StatCard
          label="Network Stability"
          value={`${stability}%`}
          color={stabilityColor}
          icon={<ShieldCheck size={16} style={{ color: stabilityColor }} />}
        />
      </div>

      {/* Main content: event feed + gauge */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
        {/* Live event feed (60%) */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <Cpu size={14} style={{ color: '#2ECC8A' }} />
            <span style={{ color: '#2ECC8A', fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Live Response Events
            </span>
            <span style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>
              {healingEvents.length} event{healingEvents.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <AnimatePresence initial={false}>
              {healingEvents.map((event, i) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.25, delay: i * 0.04 }}
                  style={{
                    borderRadius: 10,
                    background: '#1E1E1E',
                    border: '1px solid rgba(46,204,138,0.12)',
                    borderLeft: '2px solid rgba(46,204,138,0.5)',
                    padding: '12px 14px',
                  }}
                >
                  {/* Row 1: IP + action + time */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <motion.div
                      style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }}
                      animate={{ backgroundColor: ['#E03C3C', '#4F6EF7', '#2ECC8A'] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                    <span style={{ color: '#E8EDF5', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                      {event.ip}
                    </span>
                    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#2ECC8A', border: '1px solid rgba(46,204,138,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {event.action}
                    </span>
                    <span style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>
                      {formatEventTimestamp(event.timestamp)}
                    </span>
                  </div>

                  {/* Row 2: detail chips */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {event.attack_type}
                    </span>
                    <span style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                      {event.edges_severed || 0} edges cut
                    </span>
                    <span style={{ color: '#4F6EF7', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                      {event.duration_ms || event.responseTimeMs || 0}ms
                    </span>
                  </div>

                  {/* Stability bar */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Network Stability
                      </span>
                      <span style={{ color: '#2ECC8A', fontSize: 9, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                        {event.network_stability_before}% → {event.network_stability_after}%
                      </span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden', position: 'relative' }}>
                      <div style={{ position: 'absolute', top: 0, height: '100%', width: `${event.network_stability_before}%`, background: 'rgba(232,146,42,0.3)', borderRadius: 99 }} />
                      <motion.div
                        style={{ position: 'absolute', top: 0, height: '100%', background: 'linear-gradient(90deg, #4F6EF7, #2ECC8A)', borderRadius: 99 }}
                        initial={{ width: `${event.network_stability_before}%` }}
                        animate={{ width: `${event.network_stability_after}%` }}
                        transition={{ duration: 1.5, ease: 'easeOut' }}
                        className="motion-functional"
                      />
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {healingEvents.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, padding: '60px 0', color: '#3D4560', textAlign: 'center' }}>
                <ShieldCheck size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                <div style={{ fontSize: 12, fontFamily: "'DM Mono', monospace" }}>No healing events.</div>
                <div style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 4, opacity: 0.6 }}>
                  Malicious nodes are auto-isolated here.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Stability gauge (40%) */}
        <div className="gs-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
          <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Network Stability
          </div>

          {/* SVG Circular gauge */}
          <div style={{ position: 'relative', width: 180, height: 180 }}>
            <svg width={180} height={180} viewBox="0 0 180 180">
              {/* Background track */}
              <circle cx={90} cy={90} r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={12} />
              {/* Colored arc */}
              <circle
                cx={90} cy={90} r={R}
                fill="none"
                stroke={stabilityColor}
                strokeWidth={12}
                strokeDasharray={`${filled} ${gap}`}
                strokeDashoffset={CIRC * 0.25}
                strokeLinecap="round"
                style={{ transition: 'stroke-dasharray 800ms ease, stroke 400ms' }}
              />
            </svg>

            {/* Centre text */}
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center',
            }}>
              <div style={{
                color: stabilityColor,
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                fontSize: 32,
                lineHeight: 1,
              }}>
                {stability}%
              </div>
              <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>
                {stabilityTrend}
              </div>
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
            <LegendRow label="Healthy" value="≥ 80%" color="#2ECC8A" active={stability >= 80} />
            <LegendRow label="Degraded" value="50–79%" color="#E8922A" active={stability >= 50 && stability < 80} />
            <LegendRow label="Critical" value="< 50%" color="#E03C3C" active={stability < 50} />
          </div>
        </div>
      </div>

      {/* Full response log table */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <span style={{ color: '#8A95B0', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Full Response Log
          </span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="gs-table" style={{ width: '100%' }}>
            <thead style={{ background: '#1E2436' }}>
              <tr>
                {['Time', 'Node IP', 'Action', 'Edges Cut', 'Response (ms)', 'Stability', 'Triggered By'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {healingEvents.map((ev, i) => (
                <tr key={ev.id || i}>
                  <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                    {formatEventTimestamp(ev.timestamp)}
                  </td>
                  <td style={{ color: '#E8EDF5', fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{ev.ip}</td>
                  <td>
                    <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#2ECC8A', border: '1px solid rgba(46,204,138,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {ev.action}
                    </span>
                  </td>
                  <td style={{ color: '#8A95B0', fontFamily: "'DM Mono', monospace" }}>{ev.edges_severed || 0}</td>
                  <td style={{ color: '#4F6EF7', fontFamily: "'DM Mono', monospace" }}>{ev.duration_ms || ev.responseTimeMs || 0}</td>
                  <td style={{ color: '#2ECC8A', fontFamily: "'DM Mono', monospace" }}>
                    {ev.network_stability_before}% → {ev.network_stability_after}%
                  </td>
                  <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                    {ev.attack_type || ev.triggeredBy || '—'}
                  </td>
                </tr>
              ))}
              {healingEvents.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '32px 0', color: '#3D4560', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
                    No healing events recorded
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color, icon }) {
  return (
    <div className="gs-panel" style={{ padding: '16px 20px', position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: 0, right: 0, width: 60, height: 60,
        background: `${color}08`, filter: 'blur(20px)',
      }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {label}
        </span>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: `${color}12`, border: `1px solid ${color}25`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {icon}
        </div>
      </div>
      <div style={{ color, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 26 }}>
        {value}
      </div>
    </div>
  )
}

function LegendRow({ label, value, color, active }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '6px 10px', borderRadius: 6,
      background: active ? `${color}0E` : 'transparent',
      border: `1px solid ${active ? `${color}25` : 'transparent'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, opacity: active ? 1 : 0.3 }} />
        <span style={{ color: active ? color : '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{label}</span>
      </div>
      <span style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>{value}</span>
    </div>
  )
}
