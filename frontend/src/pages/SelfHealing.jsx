// [Windows] GraphSentinel — Susheep
// SelfHealing — full-page self-healing engine: event feed + stability gauge + log table
import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, ShieldCheck, Zap } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import StatTile from '../components/ui/StatTile'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatEventTimestamp } from '../utils/formatTimestamp'

export default function SelfHealing() {
  const { healingEvents, stats, dataErrors } = useGraphStore()

  const stability = Math.max(0, Math.min(100, stats.system_health ?? 100))
  const avgResponseMs = useMemo(() => {
    if (healingEvents.length === 0) return 0
    const total = healingEvents.reduce((s, e) => s + (e.duration_ms || e.responseTimeMs || 0), 0)
    return Math.round(total / healingEvents.length)
  }, [healingEvents])
  const totalIsolations = healingEvents.filter((e) => e.action === 'ISOLATED').length

  const stabilityColor =
    stability >= 80 ? '#12a672' :
    stability >= 50 ? '#b7791f' : '#E03C3C'

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
        <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Self-Healing Engine
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
            Autonomous threat response · Network stability monitoring
          </p>
          <DataFreshnessBadge dataErrors={{ stats: dataErrors.stats }} />
        </div>
      </div>

      {/* Stat cards row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <StatTile
          label="Total Isolations Today"
          value={totalIsolations}
          color="#E03C3C"
          icon={<Zap size={16} style={{ color: '#E03C3C' }} />}
          valueFontSize={26}
        />
        <StatTile
          label="Avg Response Time"
          value={`${avgResponseMs}ms`}
          color="#3b56d9"
          icon={<Cpu size={16} style={{ color: '#3b56d9' }} />}
          valueFontSize={26}
        />
        <StatTile
          label="Network Stability"
          value={`${stability}%`}
          color={stabilityColor}
          icon={<ShieldCheck size={16} style={{ color: stabilityColor }} />}
          valueFontSize={26}
        />
      </div>

      {/* Main content: event feed + gauge */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
        {/* Live event feed (60%) */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(17,20,26,0.08)', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <Cpu size={14} style={{ color: '#12a672' }} />
            <span style={{ color: '#12a672', fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Live Response Events
            </span>
            <span style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>
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
                    background: '#f0f2f5',
                    border: '1px solid rgba(46,204,138,0.12)',
                    borderLeft: '2px solid rgba(46,204,138,0.5)',
                    padding: '12px 14px',
                  }}
                >
                  {/* Row 1: IP + action + time */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <motion.div
                      style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }}
                      animate={{ backgroundColor: ['#E03C3C', '#3b56d9', '#12a672'] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                    <span style={{ color: '#1b1f27', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                      {event.ip}
                    </span>
                    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {event.action}
                    </span>
                    <span style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>
                      {formatEventTimestamp(event.timestamp)}
                    </span>
                  </div>

                  {/* Row 2: detail chips */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {event.attack_type}
                    </span>
                    <span style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                      {event.edges_severed || 0} edges cut
                    </span>
                    <span style={{ color: '#3b56d9', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                      {event.duration_ms || event.responseTimeMs || 0}ms
                    </span>
                  </div>

                  {/* Stability bar */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Network Stability
                      </span>
                      <span style={{ color: '#12a672', fontSize: 9, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                        {event.network_stability_before}% → {event.network_stability_after}%
                      </span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(17,20,26,0.08)', borderRadius: 99, overflow: 'hidden', position: 'relative' }}>
                      <div style={{ position: 'absolute', top: 0, height: '100%', width: `${event.network_stability_before}%`, background: 'rgba(232,146,42,0.3)', borderRadius: 99 }} />
                      <motion.div
                        style={{ position: 'absolute', top: 0, height: '100%', background: 'linear-gradient(90deg, #3b56d9, #12a672)', borderRadius: 99 }}
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
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, padding: '60px 0', color: '#9aa1ad', textAlign: 'center' }}>
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
          <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Network Stability
          </div>

          {/* SVG Circular gauge */}
          <div style={{ position: 'relative', width: 180, height: 180 }}>
            <svg width={180} height={180} viewBox="0 0 180 180">
              {/* Background track */}
              <circle cx={90} cy={90} r={R} fill="none" stroke="rgba(17,20,26,0.08)" strokeWidth={12} />
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
              <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>
                {stabilityTrend}
              </div>
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
            <LegendRow label="Healthy" value="≥ 80%" color="#12a672" active={stability >= 80} />
            <LegendRow label="Degraded" value="50–79%" color="#b7791f" active={stability >= 50 && stability < 80} />
            <LegendRow label="Critical" value="< 50%" color="#E03C3C" active={stability < 50} />
          </div>
        </div>
      </div>

      {/* Full response log table */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(17,20,26,0.08)' }}>
          <span style={{ color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Full Response Log
          </span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="gs-table" style={{ width: '100%' }}>
            <thead style={{ background: '#eef1f5' }}>
              <tr>
                {['Time', 'Node IP', 'Action', 'Edges Cut', 'Response (ms)', 'Stability', 'Triggered By'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {healingEvents.map((ev, i) => (
                <tr key={ev.id || i}>
                  <td style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                    {formatEventTimestamp(ev.timestamp)}
                  </td>
                  <td style={{ color: '#1b1f27', fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{ev.ip}</td>
                  <td>
                    <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.2)', fontFamily: "'DM Mono', monospace" }}>
                      {ev.action}
                    </span>
                  </td>
                  <td style={{ color: '#5a616e', fontFamily: "'DM Mono', monospace" }}>{ev.edges_severed || 0}</td>
                  <td style={{ color: '#3b56d9', fontFamily: "'DM Mono', monospace" }}>{ev.duration_ms || ev.responseTimeMs || 0}</td>
                  <td style={{ color: '#12a672', fontFamily: "'DM Mono', monospace" }}>
                    {ev.network_stability_before}% → {ev.network_stability_after}%
                  </td>
                  <td style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                    {ev.attack_type || ev.triggeredBy || '—'}
                  </td>
                </tr>
              ))}
              {healingEvents.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '32px 0', color: '#9aa1ad', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
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
        <span style={{ color: active ? color : '#9aa1ad', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{label}</span>
      </div>
      <span style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>{value}</span>
    </div>
  )
}
