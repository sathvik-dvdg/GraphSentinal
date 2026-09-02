// [Windows] GraphSentinel — Susheep
// ForensicsModal — redesigned with new token system
// § 4.6: blockchain_records: [] renders explicit empty state
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, RefreshCw, Database, Link2 } from 'lucide-react'
import { useForensicsData } from '../../hooks/useForensicsData'
import { formatEventTimestamp } from '../../utils/formatTimestamp'
import BlockchainRecordsTable from '../forensics/BlockchainRecordsTable'

export default function ForensicsModal({ isOpen, onClose }) {
  const [tab, setTab] = useState('incidents')
  // Error.md #39: fetch/poll/refresh/error logic now shared with Forensics.jsx
  // via useForensicsData — this also fixes a real bug: the modal previously
  // swallowed fetch failures silently (`.catch(() => {})`), unlike the full
  // page, which already surfaces a fetchError banner (see #26).
  const { data, loading, fetchError, refresh } = useForensicsData(isOpen, 3000)

  if (!isOpen) return null

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex justify-end"
        style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)' }}
        onClick={onClose}
        role="dialog"
        aria-label="Forensics Report"
        aria-modal="true"
      >
        {/* Drawer panel */}
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 24, stiffness: 200 }}
          className="w-full max-w-2xl h-screen flex flex-col border-l border-gs-border"
          style={{
            background: '#141414',
            boxShadow: '-10px 0 30px rgba(0,0,0,0.5)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Top accent line */}
          <div className="h-px w-full shrink-0" style={{ background: 'linear-gradient(90deg, transparent, #8B5CF660, transparent)' }} />

          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gs-border shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Database size={14} className="text-gs-chain" aria-hidden="true" />
                <h2 className="font-heading font-semibold text-sm text-gs-text tracking-wide">
                  Forensics Report
                </h2>
              </div>

              {data.contract_address && (
                <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded-md border border-gs-chain/20 bg-gs-chain-soft">
                  <Link2 size={10} className="text-gs-chain" aria-hidden="true" />
                  <span className="text-[10px] text-gs-chain font-mono tabular-nums">
                    {data.contract_address.slice(0, 10)}…
                  </span>
                </div>
              )}

              <span className="text-[10px] text-gs-faint font-mono">Chain ID: {data.chain_id ?? '—'}</span>

              {loading && (
                <div className="flex items-center gap-1.5">
                  <RefreshCw size={10} className="text-gs-accent spin-slow" aria-hidden="true" />
                  <span className="text-[10px] text-gs-accent font-mono">SYNCING</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Refresh button — original handler preserved */}
              <button
                id="forensics-refresh"
                onClick={refresh}
                className="tac-btn flex items-center gap-1.5 text-gs-muted hover:text-gs-accent border border-gs-border hover:border-gs-accent/40 hover:bg-gs-accent-soft text-[10px] font-mono px-2.5 py-1.5 rounded-lg transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-accent"
              >
                <RefreshCw size={10} aria-hidden="true" />
                Refresh
              </button>
              {/* Close button — original handler preserved */}
              <button
                id="forensics-close"
                onClick={onClose}
                className="w-7 h-7 flex items-center justify-center rounded-lg border border-gs-border text-gs-muted hover:text-gs-text hover:border-gs-muted transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-accent"
                aria-label="Close forensics modal"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          </div>

          {fetchError && (
            <div role="alert" className="mx-5 mt-3 flex items-center gap-2 px-3 py-2 rounded-lg border border-gs-threat/30 bg-gs-threat-soft text-gs-threat text-[11px] font-mono shrink-0">
              Failed to refresh: {fetchError}
            </div>
          )}

          {/* Stat summary row */}
          <div className="flex items-center border-b border-gs-border shrink-0">
            <div className="flex items-center gap-3 px-5 py-2 border-r border-gs-border">
              <span className="text-sm font-heading font-bold text-gs-text tabular-nums">{data.total_incidents}</span>
              <span className="text-[10px] text-gs-muted font-mono uppercase tracking-wider">Total Incidents</span>
            </div>
            <div className="flex items-center gap-3 px-5 py-2">
              <span className="text-sm font-heading font-bold text-gs-heal tabular-nums">{data.total_on_chain}</span>
              <span className="text-[10px] text-gs-muted font-mono uppercase tracking-wider">On-Chain Records</span>
            </div>
          </div>

          {/* Tabs — original onClick setTab preserved */}
          <div className="flex items-center border-b border-gs-border px-5 shrink-0">
            <TabBtn
              label={`Incidents (${data.total_incidents})`}
              active={tab === 'incidents'}
              color="accent"
              onClick={() => setTab('incidents')}
              id="forensics-tab-incidents"
            />
            <TabBtn
              label={`Blockchain (${data.total_on_chain})`}
              active={tab === 'blockchain'}
              color="chain"
              onClick={() => setTab('blockchain')}
              id="forensics-tab-blockchain"
            />
          </div>

          {/* Table content — all original data binding keys preserved */}
          <div className="flex-1 overflow-auto">
            {tab === 'incidents' ? (
              <table className="gs-table w-full">
                <thead className="sticky top-0" style={{ background: '#1E2436' }}>
                  <tr>
                    {['ID', 'Source IP', 'Attack', 'Threat %', 'Severity', 'Time', 'TX Hash'].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.incidents.map((inc) => (
                    <tr key={inc.id}>
                      <td className="text-gs-faint">{inc.id}</td>
                      <td className="text-gs-text font-semibold tabular-nums">{inc.source_ip}</td>
                      <td>
                        <span className="px-1.5 py-0.5 rounded-md bg-gs-threat-soft text-gs-threat border border-gs-threat/20 text-[10px]">
                          {inc.attack_type}
                        </span>
                      </td>
                      <td className="text-gs-muted tabular-nums">{(inc.threat_score * 100).toFixed(0)}%</td>
                      <td>
                        <span className={inc.severity >= 8 ? 'text-gs-threat' : inc.severity >= 5 ? 'text-gs-warn' : 'text-gs-accent'}>
                          {inc.severity}/10
                        </span>
                      </td>
                      <td className="text-gs-muted tabular-nums">{formatEventTimestamp(inc.created_at)}</td>
                      <td className="text-gs-chain tabular-nums">
                        {inc.blockchain_tx?.slice(0, 12) || '—'}{inc.blockchain_tx ? '…' : ''}
                      </td>
                    </tr>
                  ))}
                  {data.incidents.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-gs-faint font-mono text-xs">
                        No incidents logged yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : (
              <BlockchainRecordsTable
                records={data.blockchain_records}
                blockchainError={data.blockchain_error}
                stickyHeader
              />
            )}
          </div>

          {/* Footer explainer */}
          <div className="px-5 py-3 border-t border-gs-border shrink-0" style={{ background: '#171B26' }}>
            <p className="text-[10px] text-gs-faint font-mono leading-relaxed">
              <span className="text-gs-accent/60">ℹ</span>{' '}
              Each <span className="text-gs-chain">keccak256</span> hash fingerprints the incident.
              If the SQLite record is modified, the hash will no longer match the on-chain record — proving tampering has occurred.
            </p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

/* ── Tab button sub-component ── */
function TabBtn({ label, active, color, onClick, id }) {
  const colors = {
    accent: 'text-gs-accent border-b-2 border-gs-accent',
    chain:  'text-gs-chain border-b-2 border-gs-chain',
  }
  return (
    <button
      id={id}
      onClick={onClick}
      className={`px-4 py-2.5 text-[11px] font-mono tracking-wider transition-all duration-200 focus-visible:ring-2 focus-visible:ring-gs-accent focus-visible:ring-inset ${
        active ? colors[color] : 'text-gs-faint hover:text-gs-muted'
      }`}
    >
      {label}
    </button>
  )
}
