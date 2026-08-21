// [Windows] GraphSentinel — Susheep
// Forensics — full-page version of ForensicsModal content (no modal wrapper)
// Reuses getForensics() API and same data bindings as the original modal
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Database, Link2, RefreshCw, ShieldAlert, ChevronRight } from 'lucide-react'
import { getForensics } from '../services/api'
import useGraphStore from '../store/useGraphStore'
import CopyableHash from '../components/ui/CopyableHash'
import { formatEventTimestamp } from '../utils/formatTimestamp'

export default function Forensics() {
  const [tab, setTab] = useState('incidents')
  const [data, setData] = useState({
    incidents: [],
    blockchain_records: [],
    total_incidents: 0,
    total_on_chain: 0,
    contract_address: null,
    chain_id: null,
    blockchain_error: null,
  })
  const [loading, setLoading] = useState(false)
  const [selectedIncident, setSelectedIncident] = useState(null)
  const intervalRef = useRef(null)

  const resolvedIncidentIds = useGraphStore((s) => s.resolvedIncidentIds)
  const resolveIncident = useGraphStore((s) => s.resolveIncident)

  const activeIncidents = data.incidents.filter((inc) => !resolvedIncidentIds.includes(inc.id))

  useEffect(() => {
    let isMounted = true
    const doRefresh = () => {
      if (!isMounted) return
      setLoading(true)
      getForensics()
        .then((res) => { if (isMounted) setData(res) })
        .catch(() => {})
        .finally(() => { if (isMounted) setLoading(false) })
    }
    doRefresh()
    intervalRef.current = setInterval(doRefresh, 5000)
    return () => {
      isMounted = false
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const handleManualRefresh = () => {
    setLoading(true)
    getForensics()
      .then((res) => setData(res))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Forensics
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: '#8B5CF6', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
              Chain ID: {data.chain_id ?? '—'}
            </span>
            {data.contract_address && (
              <span style={{ fontSize: 11, color: '#8B5CF6', fontFamily: "'DM Mono', monospace", background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)', padding: '2px 8px', borderRadius: 4 }}>
                {data.contract_address.slice(0, 14)}…
              </span>
            )}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <RefreshCw size={11} style={{ color: '#4F6EF7' }} className="spin-slow" />
                <span style={{ color: '#4F6EF7', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>SYNCING</span>
              </div>
            )}
          </div>
        </div>
        <button
          id="forensics-refresh"
          onClick={handleManualRefresh}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)',
            color: '#8A95B0', fontSize: 11, fontFamily: "'DM Mono', monospace",
            cursor: 'pointer', transition: 'all 150ms',
          }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Stat summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatCard label="Total Incidents" value={data.total_incidents} color="#4F6EF7" />
        <StatCard label="On-Chain Records" value={data.total_on_chain} color="#8B5CF6" />
        <StatCard label="Active Incidents" value={activeIncidents.length} color="#E03C3C" />
        <StatCard label="Blockchain Records" value={data.blockchain_records.length} color="#2ECC8A" />
      </div>

      {/* Main content: case list + detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
        {/* Left: Case list */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden', height: 'fit-content', maxHeight: 600 }}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldAlert size={13} style={{ color: '#E03C3C' }} />
            <span style={{ color: '#E03C3C', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Incidents ({activeIncidents.length})
            </span>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: 540 }}>
            {activeIncidents.map((inc, i) => (
              <div
                key={inc.id}
                onClick={() => setSelectedIncident(inc)}
                style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  cursor: 'pointer',
                  background: selectedIncident?.id === inc.id ? 'rgba(79,110,247,0.08)' : 'transparent',
                  borderLeft: selectedIncident?.id === inc.id ? '2px solid #4F6EF7' : '2px solid transparent',
                  transition: 'all 150ms',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, fontFamily: "'DM Mono', monospace", letterSpacing: '0.08em',
                    color: inc.severity >= 8 ? '#E03C3C' : inc.severity >= 5 ? '#E8922A' : '#4F6EF7',
                    textTransform: 'uppercase',
                  }}>
                    {inc.severity >= 8 ? 'CRITICAL' : inc.severity >= 5 ? 'WARNING' : 'INFO'}
                  </span>
                  <span style={{ color: '#8A95B0', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                    {inc.attack_type}
                  </span>
                </div>
                <div style={{ color: '#E8EDF5', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, marginBottom: 2 }}>
                  {inc.source_ip}
                </div>
                <div style={{ color: '#3D4560', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                  {formatEventTimestamp(inc.created_at)}
                </div>
              </div>
            ))}
            {activeIncidents.length === 0 && (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                No incidents logged
              </div>
            )}
          </div>
        </div>

        {/* Right: Case detail */}
        <div>
          {selectedIncident ? (
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedIncident.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
              >
                {/* Incident summary card */}
                <div className="gs-panel" style={{ padding: '16px 18px', borderLeft: '3px solid #4F6EF7' }}>
                  <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
                    Incident Summary
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <DetailRow label="Attack Type" value={selectedIncident.attack_type} />
                    <DetailRow label="Source IP" value={selectedIncident.source_ip} />
                    <DetailRow label="Threat Score" value={`${(selectedIncident.threat_score * 100).toFixed(0)}%`} />
                    <DetailRow label="Severity" value={`${selectedIncident.severity}/10`} />
                    <DetailRow label="Time" value={formatEventTimestamp(selectedIncident.created_at)} />
                    <div>
                      <div style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>TX Hash</div>
                      <div style={{ color: '#8B5CF6', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                        <CopyableHash value={selectedIncident.blockchain_tx} prefixLen={16} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Attack timeline */}
                <div className="gs-panel" style={{ padding: '14px 18px' }}>
                  <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
                    Attack Timeline
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    {[
                      { step: 'Scan detected', detail: `Port scan from ${selectedIncident.source_ip}`, color: '#E8922A' },
                      { step: 'Connection attempted', detail: 'SYN flood initiated', color: '#E8922A' },
                      { step: 'GraphSAGE classified', detail: `Threat score: ${(selectedIncident.threat_score * 100).toFixed(0)}%`, color: '#E03C3C' },
                      { step: selectedIncident.blockchain_tx ? 'Logged on-chain' : 'Self-healing fired', detail: selectedIncident.blockchain_tx ? 'Blockchain record created' : 'Node isolated automatically', color: '#2ECC8A' },
                    ].map((item, i) => (
                      <div key={i} style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: 14 }}>
                        {/* Line */}
                        {i < 3 && <div style={{ position: 'absolute', left: 7, top: 16, width: 1, height: 'calc(100% - 4px)', background: 'rgba(255,255,255,0.06)' }} />}
                        <div style={{ width: 15, height: 15, borderRadius: '50%', background: `${item.color}20`, border: `1.5px solid ${item.color}`, flexShrink: 0, marginTop: 2 }} />
                        <div>
                          <div style={{ color: '#E8EDF5', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600, marginBottom: 2 }}>{item.step}</div>
                          <div style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{item.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidence */}
                <div className="gs-panel" style={{ padding: '14px 18px' }}>
                  <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
                    Evidence
                  </div>
                  {selectedIncident.blockchain_tx ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 6, background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)' }}>
                      <Link2 size={12} style={{ color: '#8B5CF6' }} />
                      <span style={{ color: '#8B5CF6', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                        <CopyableHash value={selectedIncident.blockchain_tx} prefixLen={selectedIncident.blockchain_tx.length} />
                      </span>
                      <span style={{ color: '#2ECC8A', fontSize: 10, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>✓ on-chain</span>
                    </div>
                  ) : (
                    <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>No blockchain evidence</div>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 10 }}>
                  <ActionBtn label="Export PDF Report" color="#4F6EF7" onClick={() => window.print()} />
                  <ActionBtn 
                    label="Mark Resolved" 
                    color="#2ECC8A" 
                    onClick={() => {
                      resolveIncident(selectedIncident.id)
                      setSelectedIncident(null)
                    }} 
                  />
                </div>
              </motion.div>
            </AnimatePresence>
          ) : (
            <div className="gs-panel" style={{ padding: '60px 0', textAlign: 'center' }}>
              <Database size={32} style={{ color: '#3D4560', margin: '0 auto 12px', display: 'block' }} />
              <div style={{ color: '#3D4560', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
                Select an incident from the left panel to view details
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Blockchain records table */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link2 size={13} style={{ color: '#8B5CF6' }} />
          <span style={{ color: '#8B5CF6', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Blockchain Records
          </span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="gs-table" style={{ width: '100%' }}>
            <thead style={{ background: '#1E2436' }}>
              <tr>
                {['ID', 'TX Hash', 'Block #', 'Attack', 'Severity', 'Gas', 'Status'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.blockchain_records.map((rec, i) => (
                <tr key={i}>
                  <td style={{ color: '#3D4560', fontFamily: "'DM Mono', monospace" }}>{rec.id}</td>
                  <td style={{ color: '#8B5CF6', fontFamily: "'DM Mono', monospace", fontSize: 10 }}><CopyableHash value={rec.tx_hash} iconSize={9} /></td>
                  <td style={{ color: '#4F6EF7', fontFamily: "'DM Mono', monospace" }}>#{rec.block_number}</td>
                  <td><span style={{ fontSize: 10, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.2)', padding: '2px 7px', borderRadius: 4, fontFamily: "'DM Mono', monospace" }}>{rec.attack_type}</span></td>
                  <td style={{ color: rec.severity >= 8 ? '#E03C3C' : '#E8922A', fontFamily: "'DM Mono', monospace" }}>{rec.severity}/10</td>
                  <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace" }}>{rec.gas_used?.toLocaleString()}</td>
                  <td><span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#2ECC8A', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>● Confirmed</span></td>
                </tr>
              ))}
              {data.blockchain_records.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '32px 0', color: '#3D4560', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
                    {data.blockchain_error
                      ? `No blockchain records — ${data.blockchain_error}`
                      : 'No blockchain records.'}
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

function StatCard({ label, value, color }) {
  return (
    <div className="gs-panel" style={{ padding: '14px 16px' }}>
      <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>{label}</div>
      <div style={{ color, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 24 }}>{value}</div>
    </div>
  )
}

function DetailRow({ label, value, color = '#8A95B0' }) {
  return (
    <div>
      <div style={{ color: '#3D4560', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>{label}</div>
      <div style={{ color, fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function ActionBtn({ label, color, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
        border: `1px solid ${color}30`, background: `${color}10`, color,
        fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 500, transition: 'all 150ms',
      }}
    >
      {label}
    </button>
  )
}
