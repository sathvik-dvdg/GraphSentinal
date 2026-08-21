// [Windows] GraphSentinel — Susheep
// ThreatFeed — full-page version of AlertPanel with filters and stats sidebar
import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldAlert, Search, Filter } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import SeverityBadge from '../components/ui/SeverityBadge'
import ThreatBar from '../components/ui/ThreatBar'
import CopyableHash from '../components/ui/CopyableHash'
import { formatEventTimestamp as formatAlertTimestamp } from '../utils/formatTimestamp'

const SEVERITIES = ['All', 'critical', 'warning', 'info']
const TYPES = ['All', 'DDoS', 'SSHBrute', 'PortScan', 'Botnet']
const TIME_RANGES = ['1h', '6h', '24h', '7d']

export default function ThreatFeed() {
  const { alerts } = useGraphStore()

  const [severity, setSeverity] = useState('All')
  const [attackType, setAttackType] = useState('All')
  const [ipSearch, setIpSearch] = useState('')
  const [timeRange, setTimeRange] = useState('24h')

  const timeRangeMs = { '1h': 3.6e6, '6h': 2.16e7, '24h': 8.64e7, '7d': 6.048e8 }
  const cutoff = Date.now() - (timeRangeMs[timeRange] || timeRangeMs['24h'])

  const filtered = useMemo(() => {
    return alerts.filter((a) => {
      if (severity !== 'All' && a.severity !== severity) return false
      if (attackType !== 'All' && a.attack_type !== attackType) return false
      if (ipSearch && !a.source_ip?.includes(ipSearch)) return false
      if (new Date(a.timestamp).getTime() < cutoff) return false
      return true
    })
  }, [alerts, severity, attackType, ipSearch, cutoff])

  // Stats for right sidebar
  const criticalCount = alerts.filter((a) => a.severity === 'critical').length
  const blockedCount = alerts.filter((a) => a.is_blocked).length
  const topIPs = useMemo(() => {
    const ipCount = {}
    alerts.forEach((a) => { ipCount[a.source_ip] = (ipCount[a.source_ip] || 0) + 1 })
    return Object.entries(ipCount).sort(([, a], [, b]) => b - a).slice(0, 5)
  }, [alerts])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 108px)' }}>
      {/* Page header */}
      <div style={{ flexShrink: 0 }}>
        <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Threat Feed
        </h1>
        <p style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          {filtered.length} event{filtered.length !== 1 ? 's' : ''} · Real-time threat intelligence
        </p>
      </div>

      {/* Filter bar */}
      <div
        className="gs-panel"
        style={{ padding: '12px 16px', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}
      >
        <Filter size={13} style={{ color: '#5A6480' }} />

        {/* Severity pills */}
        <div style={{ display: 'flex', gap: 4 }}>
          {SEVERITIES.map((s) => (
            <Pill key={s} label={s} active={severity === s} onClick={() => setSeverity(s)}
              color={s === 'critical' ? '#E03C3C' : s === 'warning' ? '#E8922A' : s === 'info' ? '#4F6EF7' : '#5A6480'} />
          ))}
        </div>

        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)' }} />

        {/* Type pills */}
        <div style={{ display: 'flex', gap: 4 }}>
          {TYPES.map((t) => (
            <Pill key={t} label={t} active={attackType === t} onClick={() => setAttackType(t)} color="#8B5CF6" />
          ))}
        </div>

        <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)' }} />

        {/* IP search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#1E1E1E', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 6, padding: '4px 10px' }}>
          <Search size={12} style={{ color: '#5A6480' }} />
          <input
            value={ipSearch}
            onChange={(e) => setIpSearch(e.target.value)}
            placeholder="Search IP..."
            style={{ background: 'none', border: 'none', outline: 'none', color: '#E8EDF5', fontSize: 12, fontFamily: "'DM Mono', monospace", width: 120 }}
          />
        </div>

        {/* Time range */}
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
          {TIME_RANGES.map((t) => (
            <Pill key={t} label={t} active={timeRange === t} onClick={() => setTimeRange(t)} color="#4F6EF7" />
          ))}
        </div>
      </div>

      {/* Main content + sidebar */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16, overflow: 'hidden', minHeight: 0 }}>
        {/* Threat list */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <AnimatePresence initial={false}>
            {filtered.map((alert, i) => (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2, delay: i * 0.02 }}
                className="gs-panel"
                style={{
                  padding: '14px 16px',
                  borderLeft: `3px solid ${alert.severity === 'critical' ? '#E03C3C' : alert.severity === 'warning' ? '#E8922A' : '#4F6EF7'}`,
                  flexShrink: 0,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Row 1 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                      <SeverityBadge severity={alert.severity} />
                      <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: '#8A95B0', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: 4 }}>
                        {alert.attack_type}
                      </span>
                      <span style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                        {formatAlertTimestamp(alert.timestamp)}
                      </span>
                    </div>
                    {/* Source IP */}
                    <div style={{ color: '#E8EDF5', fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700, marginBottom: 8 }}>
                      {alert.source_ip}
                    </div>
                    {/* Threat score bar */}
                    <ThreatBar score={alert.threat_score} delay={i * 0.03} />
                    {/* TX hash */}
                    {alert.blockchain_tx && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                        <span style={{ color: '#8B5CF6' }}>⛓</span>
                        <CopyableHash value={alert.blockchain_tx} style={{ color: '#8B5CF6' }} iconSize={9} />
                        <span style={{ color: '#2ECC8A', marginLeft: 4 }}>✓ on-chain</span>
                      </div>
                    )}
                  </div>
                  {/* Status tag */}
                  <div style={{ flexShrink: 0 }}>
                    <span style={{
                      fontSize: 9,
                      fontFamily: "'DM Mono', monospace",
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: 4,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      background: alert.is_blocked ? 'rgba(46,204,138,0.12)' : 'rgba(224,60,60,0.12)',
                      color: alert.is_blocked ? '#2ECC8A' : '#E03C3C',
                      border: `1px solid ${alert.is_blocked ? 'rgba(46,204,138,0.25)' : 'rgba(224,60,60,0.25)'}`,
                    }}>
                      {alert.is_blocked ? 'ISOLATED' : 'ACTIVE'}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: '#3D4560', fontSize: 13, fontFamily: "'DM Mono', monospace" }}>
              <ShieldAlert size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
              <div>No threats matching current filters</div>
            </div>
          )}
        </div>

        {/* Right sidebar stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          {/* Mini stat cards */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Live Stats
            </div>
            <StatRow label="Total alerts" value={alerts.length} color="#8A95B0" />
            <StatRow label="Critical" value={criticalCount} color="#E03C3C" />
            <StatRow label="Isolated" value={blockedCount} color="#2ECC8A" />
          </div>

          {/* Top attacking IPs */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Top Attacking IPs
            </div>
            {topIPs.map(([ip, count]) => (
              <div key={ip} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ color: '#E8EDF5', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{ip}</span>
                <span style={{ color: '#E03C3C', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{count}</span>
              </div>
            ))}
            {topIPs.length === 0 && (
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>No data</div>
            )}
          </div>

          {/* Attack type distribution */}
          <div className="gs-panel" style={{ padding: '14px 16px' }}>
            <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Attack Types
            </div>
            {TYPES.filter((t) => t !== 'All').map((type) => {
              const count = alerts.filter((a) => a.attack_type === type).length
              const pct = alerts.length > 0 ? Math.round((count / alerts.length) * 100) : 0
              return (
                <div key={type} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ color: '#8A95B0', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>{type}</span>
                    <span style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>{count}</span>
                  </div>
                  <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: '#E03C3C', borderRadius: 99 }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function Pill({ label, active, onClick, color }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 10px',
        borderRadius: 6,
        border: `1px solid ${active ? color : 'rgba(255,255,255,0.08)'}`,
        background: active ? `${color}18` : 'transparent',
        color: active ? color : '#5A6480',
        fontSize: 10,
        fontFamily: "'DM Mono', monospace",
        cursor: 'pointer',
        transition: 'all 150ms',
        fontWeight: active ? 600 : 400,
        textTransform: 'capitalize',
      }}
    >
      {label}
    </button>
  )
}

function StatRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{label}</span>
      <span style={{ color, fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{value}</span>
    </div>
  )
}
