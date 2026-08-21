// [Windows] GraphSentinel — Susheep
// BlockchainLedger — full-page blockchain audit table with filters and export
import { Fragment, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link2, CheckCircle, Loader2, Download, ChevronDown } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import CopyableHash from '../components/ui/CopyableHash'
import { formatEventTimestamp } from '../utils/formatTimestamp'

const STATUSES = ['All', 'confirmed', 'pending']
const ATTACK_TYPES = ['All', 'DDoS', 'SSHBrute', 'PortScan', 'Botnet']

export default function BlockchainLedger() {
  const { chainTxs, connectionMode, chainId } = useGraphStore()
  const [statusFilter, setStatusFilter] = useState('All')
  const [typeFilter, setTypeFilter] = useState('All')
  const [expandedRow, setExpandedRow] = useState(null)

  const isConnected = connectionMode === 'live'

  const filtered = useMemo(() => {
    return chainTxs.filter((tx) => {
      if (statusFilter !== 'All' && tx.status !== statusFilter) return false
      if (typeFilter !== 'All' && tx.attack_type !== typeFilter) return false
      return true
    })
  }, [chainTxs, statusFilter, typeFilter])

  const totalGas = chainTxs.reduce((sum, tx) => sum + (tx.gas_used || 0), 0)
  const confirmedCount = chainTxs.filter((tx) => tx.status === 'confirmed').length
  const lastBlock = chainTxs.length > 0
    ? Math.max(...chainTxs.map((tx) => tx.block_number || 0))
    : '—'

  const exportCSV = () => {
    const rows = [
      ['TX Hash', 'Attack Type', 'Source IP', 'Block #', 'Gas Used', 'Status', 'Timestamp'],
      ...chainTxs.map((tx) => [
        tx.tx_hash, tx.attack_type, tx.source_ip, tx.block_number,
        tx.gas_used, tx.status, tx.timestamp,
      ]),
    ]
    const csv = rows.map((r) => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'blockchain_ledger.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(chainTxs, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'blockchain_ledger.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Blockchain Ledger
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: '#8B5CF6', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>Ganache · Chain {chainId ?? '—'}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: isConnected ? '#2ECC8A' : '#5A6480',
              }} />
              <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                {isConnected ? 'Connected' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
        {/* Export buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={exportCSV} style={exportBtnStyle('#2ECC8A')}>
            <Download size={12} /> CSV
          </button>
          <button onClick={exportJSON} style={exportBtnStyle('#4F6EF7')}>
            <Download size={12} /> JSON
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MiniStat label="Total Records" value={chainTxs.length} color="#8B5CF6" />
        <MiniStat label="Confirmed" value={confirmedCount} color="#2ECC8A" />
        <MiniStat label="Gas Used Today" value={formatGas(totalGas)} color="#E8922A" />
        <MiniStat label="Last Block" value={lastBlock} color="#4F6EF7" />
      </div>

      {/* Filters */}
      <div className="gs-panel" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>Filter:</span>
        {STATUSES.map((s) => (
          <Pill key={s} label={s} active={statusFilter === s} onClick={() => setStatusFilter(s)} color="#2ECC8A" />
        ))}
        <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,0.08)' }} />
        {ATTACK_TYPES.map((t) => (
          <Pill key={t} label={t} active={typeFilter === t} onClick={() => setTypeFilter(t)} color="#E03C3C" />
        ))}
      </div>

      {/* Table */}
      <div className="gs-panel" style={{ overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="gs-table" style={{ width: '100%' }}>
            <thead style={{ background: '#1E2436' }}>
              <tr>
                {['TX Hash', 'Attack Type', 'Source IP', 'Block #', 'Gas Used', 'Severity', 'Status', 'Time'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((tx, i) => (
                <Fragment key={tx.id || i}>
                  <motion.tr
                    key={tx.id || i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setExpandedRow(expandedRow === (tx.id || i) ? null : (tx.id || i))}
                  >
                    <td style={{ color: '#8B5CF6', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Link2 size={10} style={{ flexShrink: 0 }} />
                        <CopyableHash value={tx.tx_hash} iconSize={9} />
                        <ChevronDown size={10} style={{
                          marginLeft: 4,
                          transform: expandedRow === (tx.id || i) ? 'rotate(180deg)' : 'rotate(0)',
                          transition: 'transform 200ms',
                          color: '#5A6480',
                        }} />
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 10, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.2)', padding: '2px 7px', borderRadius: 4, fontFamily: "'DM Mono', monospace" }}>
                        {tx.attack_type}
                      </span>
                    </td>
                    <td style={{ color: '#E8EDF5', fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{tx.source_ip}</td>
                    <td style={{ color: '#4F6EF7', fontFamily: "'DM Mono', monospace" }}>#{tx.block_number}</td>
                    <td style={{ color: '#8A95B0', fontFamily: "'DM Mono', monospace" }}>{tx.gas_used?.toLocaleString()}</td>
                    <td>
                      <span style={{ color: tx.severity >= 8 ? '#E03C3C' : tx.severity >= 5 ? '#E8922A' : '#4F6EF7', fontFamily: "'DM Mono', monospace" }}>
                        {tx.severity}/10
                      </span>
                    </td>
                    <td>
                      {tx.status === 'confirmed' ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#2ECC8A', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                          <CheckCircle size={10} /> Confirmed
                        </span>
                      ) : (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#E8922A', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                          <Loader2 size={10} className="spin-slow" /> Pending
                        </span>
                      )}
                    </td>
                    <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                      {formatEventTimestamp(tx.timestamp)}
                    </td>
                  </motion.tr>

                  {/* Expanded row */}
                  <AnimatePresence>
                    {expandedRow === (tx.id || i) && (
                      <tr key={`exp-${tx.id || i}`}>
                        <td colSpan={8} style={{ padding: 0 }}>
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            style={{ overflow: 'hidden', background: 'rgba(79,110,247,0.04)', borderTop: '1px solid rgba(255,255,255,0.04)' }}
                          >
                            <div style={{ padding: '12px 16px', fontFamily: "'DM Mono', monospace", fontSize: 11 }}>
                              <div style={{ marginBottom: 6 }}>
                                <span style={{ color: '#3D4560' }}>Full TX Hash: </span>
                                <span style={{ color: '#8B5CF6' }}>{tx.tx_hash || '—'}</span>
                              </div>
                              <div style={{ marginBottom: 6 }}>
                                <span style={{ color: '#3D4560' }}>Incident Hash: </span>
                                <span style={{ color: '#5A6480' }}>{tx.incident_hash}</span>
                              </div>
                              <div>
                                <span style={{ color: '#3D4560' }}>Forensics URI: </span>
                                <span style={{ color: '#4F6EF7' }}>{tx.forensics_uri}</span>
                              </div>
                            </div>
                          </motion.div>
                        </td>
                      </tr>
                    )}
                  </AnimatePresence>
                </Fragment>
              ))}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '48px 0', color: '#3D4560', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
                    No blockchain records match the current filter.
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

function MiniStat({ label, value, color }) {
  return (
    <div className="gs-panel" style={{ padding: '14px 16px' }}>
      <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ color, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22 }}>
        {value}
      </div>
    </div>
  )
}

function Pill({ label, active, onClick, color }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '3px 10px', borderRadius: 5,
        border: `1px solid ${active ? color : 'rgba(255,255,255,0.08)'}`,
        background: active ? `${color}15` : 'transparent',
        color: active ? color : '#5A6480',
        fontSize: 10, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
        transition: 'all 150ms', textTransform: 'capitalize',
      }}
    >
      {label}
    </button>
  )
}

function exportBtnStyle(color) {
  return {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '6px 14px', borderRadius: 6,
    border: `1px solid ${color}30`, background: `${color}10`, color,
    fontSize: 12, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
    fontWeight: 500, transition: 'all 150ms',
  }
}

function formatGas(gas) {
  if (gas >= 1000000) return (gas / 1000000).toFixed(1) + 'M'
  if (gas >= 1000) return Math.round(gas / 1000) + 'K'
  return gas
}
