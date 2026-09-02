import { Fragment, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link2, CheckCircle, Loader2, Download, ChevronDown, ShieldCheck, XCircle } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import CopyableHash from '../components/ui/CopyableHash'
import BlockchainStatusBadge from '../components/ui/BlockchainStatusBadge'
import StatTile from '../components/ui/StatTile'
import FilterPill from '../components/ui/FilterPill'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { formatEventTimestamp } from '../utils/formatTimestamp'

const STATUSES = ['All', 'confirmed', 'pending', 'failed']
const ATTACK_TYPES = ['All', 'DDoS', 'SSHBrute', 'PortScan', 'Botnet']

export default function BlockchainLedger() {
  const { chainTxs, enforcementActions, connectionMode, chainId, dataErrors } = useGraphStore()
  const [tab, setTab] = useState('blockchain') // 'blockchain' | 'enforcement'

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
    if (tab === 'blockchain') {
      const rows = [
        ['TX Hash', 'Attack Type', 'Source IP', 'Block #', 'Gas Used', 'Status', 'Timestamp'],
        ...chainTxs.map((tx) => [
          tx.tx_hash, tx.attack_type, tx.source_ip, tx.block_number,
          tx.gas_used, tx.status, tx.timestamp,
        ]),
      ]
      downloadCSV(rows, 'blockchain_ledger.csv')
    } else {
      const rows = [
        ['ID', 'IP Address', 'Action', 'Reason', 'Status', 'Error', 'Incident ID', 'Blockchain TX', 'Timestamp'],
        ...enforcementActions.map((a) => [
          a.id, a.ip_address, a.action, a.reason, a.status, a.error || '', a.incident_id || '', a.blockchain_tx || '', a.created_at,
        ]),
      ]
      downloadCSV(rows, 'enforcement_audit.csv')
    }
  }

  const exportJSON = () => {
    const data = tab === 'blockchain' ? chainTxs : enforcementActions
    const filename = tab === 'blockchain' ? 'blockchain_ledger.json' : 'enforcement_audit.json'
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Audit & Ledger
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {tab === 'blockchain' && (
              <span style={{ color: '#8B5CF6', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>Ganache · Chain {chainId ?? '—'}</span>
            )}
            <DataFreshnessBadge dataErrors={{ forensics: dataErrors.forensics, enforcement: dataErrors.enforcement }} />
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

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 12, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <TabButton label="Blockchain Records" active={tab === 'blockchain'} onClick={() => setTab('blockchain')} />
        <TabButton label="Enforcement Log" active={tab === 'enforcement'} onClick={() => setTab('enforcement')} />
      </div>

      {tab === 'blockchain' && (
        <>
          {/* Stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <StatTile label="Total Records" value={chainTxs.length} color="#8B5CF6" valueFontSize={22} />
            <StatTile label="Confirmed" value={confirmedCount} color="#2ECC8A" valueFontSize={22} />
            <StatTile label="Gas Used Today" value={formatGas(totalGas)} color="#E8922A" valueFontSize={22} />
            <StatTile label="Last Block" value={lastBlock} color="#4F6EF7" valueFontSize={22} />
          </div>

          {/* Filters */}
          <div className="gs-panel" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>Filter:</span>
            {STATUSES.map((s) => (
              <FilterPill key={s} label={s} active={statusFilter === s} onClick={() => setStatusFilter(s)} color="#2ECC8A" />
            ))}
            <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,0.08)' }} />
            {ATTACK_TYPES.map((t) => (
              <FilterPill key={t} label={t} active={typeFilter === t} onClick={() => setTypeFilter(t)} color="#E03C3C" />
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
                          <BlockchainStatusBadge status={tx.status} />
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
        </>
      )}

      {tab === 'enforcement' && (
        <EnforcementTable actions={enforcementActions} />
      )}
    </div>
  )
}

function EnforcementTable({ actions }) {
  if (!actions || actions.length === 0) {
    return (
      <div className="gs-panel" style={{ padding: '48px 0', textAlign: 'center' }}>
        <ShieldCheck size={32} style={{ color: '#3D4560', margin: '0 auto 12px' }} />
        <div style={{ color: '#3D4560', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          No enforcement actions have been logged yet.
        </div>
      </div>
    )
  }

  return (
    <div className="gs-panel" style={{ overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table className="gs-table" style={{ width: '100%' }}>
          <thead style={{ background: '#1E2436' }}>
            <tr>
              {['ID', 'IP Address', 'Action', 'Reason', 'Status', 'Blockchain TX', 'Time'].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {actions.map((act, i) => (
              <motion.tr
                key={act.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
              >
                <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>#{act.id}</td>
                <td style={{ color: '#E8EDF5', fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{act.ip_address}</td>
                <td>
                  <span style={{
                    fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase',
                    color: act.action === 'block' ? '#E03C3C' : '#4F6EF7',
                    background: act.action === 'block' ? 'rgba(224,60,60,0.1)' : 'rgba(79,110,247,0.1)',
                    border: `1px solid ${act.action === 'block' ? 'rgba(224,60,60,0.2)' : 'rgba(79,110,247,0.2)'}`,
                    padding: '2px 7px', borderRadius: 4,
                  }}>
                    {act.action}
                  </span>
                </td>
                <td style={{ color: '#8A95B0', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>{act.reason}</td>
                <td>
                  <EnforcementStatusBadge status={act.status} error={act.error} />
                </td>
                <td style={{ color: '#8B5CF6', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                  {act.blockchain_tx ? <CopyableHash value={act.blockchain_tx} iconSize={9} /> : <span style={{ color: '#5A6480' }}>—</span>}
                </td>
                <td style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                  {formatEventTimestamp(act.created_at)}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EnforcementStatusBadge({ status, error }) {
  let color = '#5A6480'
  let bg = 'rgba(255,255,255,0.05)'
  
  if (status === 'enforced' || status === 'removed') {
    color = '#2ECC8A'
    bg = 'rgba(46,204,138,0.1)'
  } else if (status === 'simulated') {
    color = '#4F6EF7'
    bg = 'rgba(79,110,247,0.1)'
  } else if (status === 'pending_enforcement' || status === 'pending_unblock') {
    color = '#E8922A'
    bg = 'rgba(232,146,42,0.1)'
  } else if (status === 'failed') {
    color = '#E03C3C'
    bg = 'rgba(224,60,60,0.1)'
  }

  return (
    <span
      title={error || undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        color, background: bg, border: `1px solid ${color}30`,
        padding: '2px 6px', borderRadius: 4, fontSize: 10, fontFamily: "'DM Mono', monospace",
        textTransform: 'uppercase', cursor: error ? 'help' : 'default'
      }}
    >
      {status === 'failed' && <XCircle size={10} />}
      {(status === 'enforced' || status === 'removed') && <CheckCircle size={10} />}
      {(status === 'pending_enforcement' || status === 'pending_unblock') && <Loader2 size={10} className="spin-slow" />}
      {status}
    </span>
  )
}

function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '10px 16px',
        background: 'transparent',
        border: 'none',
        borderBottom: active ? '2px solid #4F6EF7' : '2px solid transparent',
        color: active ? '#4F6EF7' : '#5A6480',
        fontFamily: "'DM Mono', monospace",
        fontSize: 12,
        cursor: 'pointer',
        transition: 'all 150ms',
      }}
    >
      {label}
    </button>
  )
}

function downloadCSV(rows, filename) {
  const csv = rows.map((r) => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
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
